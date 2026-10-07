"""Least-authority durable store for post-claim governed transport."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Optional
from uuid import uuid4

from psycopg2.extras import Json

from core.execution.submission_authority import (
    ClaimedSubmissionCapability,
    is_valid_claimed_submission_capability,
    submission_fingerprint,
)
from core.persistence.persistence_coordinator import PersistenceCoordinator
from core.persistence.submission_authorization_issuer_store import (
    AUTHORIZATION_COLUMNS,
    LIVE_SCHEMA,
)
from core.persistence.transaction_context import (
    ImmutablePage,
    ImmutableRow,
    Predicate,
    PredicateOperator,
    ResourceScope,
    ResourceSpec,
)


TRANSPORT_ACTOR_ID = "handa-governed-mock-transport-gateway"
TRANSPORT_COLUMNS = (
    "submission_authorization_id", "intent_id", "submission_attempt_id",
    "client_order_id", "venue", "account_scope", "symbol", "side",
    "requested_quote_amount", "requested_base_qty", "submission_fingerprint",
    "transport_state", "current_version", "handoff_committed_at",
    "last_event_sequence", "external_order_id", "last_error", "updated_at",
)
EVENT_COLUMNS = (
    "event_id", "submission_authorization_id", "event_sequence", "event_type",
    "transport_state_after", "actor_id", "external_order_id",
    "observation_identity", "event_detail", "recorded_at",
)
INTENT_COLUMNS = (
    "intent_id", "venue", "account_scope", "client_order_id", "symbol", "side",
    "requested_quote_amount", "requested_base_qty", "exchange_order_id",
)
ATTEMPT_COLUMNS = (
    "attempt_id", "intent_id", "attempt_sequence", "venue", "account_scope",
    "client_order_id", "exchange_order_id", "transport_status", "transport_error",
    "observed_at", "exchange_event_time",
)
EVIDENCE_COLUMNS = ("evidence_id", "attempt_id")

PERSISTED_STATES = frozenset({
    "HANDOFF_COMMITTED", "OUTCOME_UNKNOWN", "OBSERVED_ACCEPTED",
    "OBSERVED_REJECTED", "NO_EFFECT_CONFIRMED",
})
TERMINAL_STATES = frozenset({
    "OBSERVED_ACCEPTED", "OBSERVED_REJECTED", "NO_EFFECT_CONFIRMED",
})


class TransportValidationError(ValueError):
    """A capability or durable lineage failed closed."""


class TransportConflict(TransportValidationError):
    """The capability does not match durable transport lineage."""


@dataclass(frozen=True)
class HandoffPreparation:
    projection: ImmutableRow
    created: bool


def governed_transport_resource_scope() -> ResourceScope:
    """Expose only transport writes and the read/lock lineage they require."""

    intent = ResourceSpec(
        LIVE_SCHEMA, "order_intent", frozenset(INTENT_COLUMNS), frozenset(),
        frozenset({"intent_id"}), ("intent_id",),
    )
    attempt = ResourceSpec(
        LIVE_SCHEMA, "submission_attempt", frozenset(ATTEMPT_COLUMNS), frozenset(),
        frozenset({"attempt_id"}), ("attempt_id",),
    )
    evidence = ResourceSpec(
        LIVE_SCHEMA, "exchange_evidence", frozenset(EVIDENCE_COLUMNS), frozenset(),
        frozenset({"evidence_id"}), ("evidence_id",),
    )
    authorization = ResourceSpec(
        LIVE_SCHEMA, "submission_authorization", frozenset(AUTHORIZATION_COLUMNS),
        frozenset(), frozenset({"submission_authorization_id"}),
        ("submission_authorization_id",),
    )
    projection = ResourceSpec(
        LIVE_SCHEMA, "transport_submission", frozenset(TRANSPORT_COLUMNS),
        frozenset(set(TRANSPORT_COLUMNS) - {"handoff_committed_at", "updated_at"}),
        frozenset({"submission_authorization_id"}),
        ("submission_authorization_id",), version_column="current_version",
    )
    event = ResourceSpec(
        LIVE_SCHEMA, "transport_event", frozenset(EVENT_COLUMNS),
        frozenset(set(EVENT_COLUMNS) - {"recorded_at"}),
        frozenset({"event_id"}), ("submission_authorization_id", "event_sequence", "event_id"),
    )
    return ResourceScope((authorization, attempt, intent, evidence, projection, event))


class GovernedTransportStore:
    """Store that can write only transport projection and transport history."""

    def __init__(self, coordinator: PersistenceCoordinator):
        self._coordinator = coordinator

    def transaction(self) -> AbstractContextManager[Any]:
        return self._coordinator.transaction()

    @staticmethod
    def get_projection(context, authorization_id: str, *, for_update: bool = False) -> Optional[ImmutableRow]:
        reader = context.read_by_key_for_update if for_update else context.read_by_key
        return reader("transport_submission", {"submission_authorization_id": authorization_id}, TRANSPORT_COLUMNS)

    @staticmethod
    def get_events(context, authorization_id: str) -> ImmutablePage:
        return context.enumerate(
            "transport_event",
            (Predicate("submission_authorization_id", PredicateOperator.EQ, authorization_id),),
            EVENT_COLUMNS,
            1000,
        )

    @staticmethod
    def _require_capability(capability: Any) -> ClaimedSubmissionCapability:
        if not is_valid_claimed_submission_capability(capability):
            raise TransportValidationError("INVALID_CAPABILITY")
        if capability.side != "BUY":
            raise TransportValidationError("UNSUPPORTED_SIDE")
        if capability.venue != "MOCK":
            raise TransportValidationError("UNSUPPORTED_VENUE")
        return capability

    @staticmethod
    def _same_amount(left: Any, right: Any) -> bool:
        return left == right

    @classmethod
    def _validate_binding(cls, capability, authorization, intent, attempt) -> None:
        if authorization is None or intent is None or attempt is None:
            raise TransportConflict("durable lineage is incomplete")
        required = {
            "authorization_state": "CLAIMED",
            "current_version": 1,
            "claimed_by": "handa-submission-authorization-claimer",
            "issuer_id": "handa-submission-authorization-issuer",
            "authority_contract_version": "submission-authority-v1",
        }
        for field, expected in required.items():
            if authorization[field] != expected:
                raise TransportConflict(f"authorization {field} is not canonical")
        if authorization["claimed_at"] is None:
            raise TransportConflict("authorization claim timestamp is missing")

        exact_fields = (
            "submission_authorization_id", "intent_id", "submission_attempt_id",
            "client_order_id", "venue", "account_scope", "symbol", "side",
            "requested_quote_amount", "requested_base_qty", "submission_fingerprint",
            "issuer_id", "authority_reference_id", "authority_contract_version",
            "claimed_by", "claimed_at",
        )
        for field in exact_fields:
            if field in {"claimed_at"}:
                equal = getattr(capability, field) == authorization[field]
            else:
                equal = getattr(capability, field) == authorization[field]
            if not equal:
                raise TransportConflict(f"capability binding mismatch: {field}")
        if capability.claimed_version != authorization["current_version"]:
            raise TransportConflict("capability claim version mismatch")

        expected_fingerprint = submission_fingerprint(
            intent_id=authorization["intent_id"],
            submission_attempt_id=authorization["submission_attempt_id"],
            client_order_id=authorization["client_order_id"],
            venue=authorization["venue"],
            account_scope=authorization["account_scope"],
            symbol=authorization["symbol"],
            side=authorization["side"],
            requested_quote_amount=authorization["requested_quote_amount"],
            requested_base_qty=authorization["requested_base_qty"],
        )
        if authorization["submission_fingerprint"] != expected_fingerprint:
            raise TransportConflict("durable submission fingerprint mismatch")

        if attempt["intent_id"] != intent["intent_id"] or authorization["intent_id"] != intent["intent_id"]:
            raise TransportConflict("intent lineage mismatch")
        if attempt["attempt_sequence"] != authorization["authorization_sequence"]:
            raise TransportConflict("attempt sequence mismatch")
        for field in ("venue", "account_scope", "client_order_id"):
            if not (authorization[field] == intent[field] == attempt[field]):
                raise TransportConflict(f"lineage mismatch: {field}")
        for field in ("symbol", "side", "requested_quote_amount", "requested_base_qty"):
            if authorization[field] != intent[field]:
                raise TransportConflict(f"intent binding mismatch: {field}")

    @staticmethod
    def _validate_no_legacy_handling(context, intent, attempt) -> None:
        if intent["exchange_order_id"] is not None:
            raise TransportConflict("legacy intent already has external handling")
        if any(attempt[field] is not None for field in (
            "exchange_order_id", "transport_status", "transport_error",
            "observed_at", "exchange_event_time",
        )):
            raise TransportConflict("legacy attempt already has external handling")
        evidence = context.enumerate(
            "exchange_evidence",
            (Predicate("attempt_id", PredicateOperator.EQ, attempt["attempt_id"]),),
            EVIDENCE_COLUMNS,
            1,
        )
        if evidence.rows:
            raise TransportConflict("legacy exchange evidence already exists")

    @classmethod
    def prepare_handoff(cls, context, capability: Any) -> HandoffPreparation:
        capability = cls._require_capability(capability)

        # The fixed order is part of the transport boundary: attempt, intent,
        # authorization.  No venue interaction is possible in this method.
        attempt = context.read_by_key_for_update(
            "submission_attempt", {"attempt_id": capability.submission_attempt_id}, ATTEMPT_COLUMNS
        )
        intent = context.read_by_key_for_update(
            "order_intent", {"intent_id": capability.intent_id}, INTENT_COLUMNS
        )
        authorization = context.read_by_key_for_update(
            "submission_authorization",
            {"submission_authorization_id": capability.submission_authorization_id},
            AUTHORIZATION_COLUMNS,
        )
        cls._validate_binding(capability, authorization, intent, attempt)

        existing = cls.get_projection(context, capability.submission_authorization_id)
        if existing is not None:
            return HandoffPreparation(existing, False)

        cls._validate_no_legacy_handling(context, intent, attempt)

        projection = context.insert_returning(
            "transport_submission",
            {
                "submission_authorization_id": authorization["submission_authorization_id"],
                "intent_id": authorization["intent_id"],
                "submission_attempt_id": authorization["submission_attempt_id"],
                "client_order_id": authorization["client_order_id"],
                "venue": authorization["venue"],
                "account_scope": authorization["account_scope"],
                "symbol": authorization["symbol"],
                "side": authorization["side"],
                "requested_quote_amount": authorization["requested_quote_amount"],
                "requested_base_qty": authorization["requested_base_qty"],
                "submission_fingerprint": authorization["submission_fingerprint"],
                "transport_state": "HANDOFF_COMMITTED",
                "current_version": 0,
                "last_event_sequence": 1,
            },
            TRANSPORT_COLUMNS,
        )
        cls._insert_event(
            context,
            projection,
            event_type="HANDOFF_COMMITTED",
            state_after="HANDOFF_COMMITTED",
            detail={"reason": "durable pre-network handoff"},
        )
        return HandoffPreparation(projection, True)

    @staticmethod
    def _insert_event(
        context,
        projection: ImmutableRow,
        *,
        event_type: str,
        state_after: str,
        external_order_id: Optional[str] = None,
        observation_identity: Optional[str] = None,
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        context.insert(
            "transport_event",
            {
                "event_id": f"transport-event-{uuid4().hex}",
                "submission_authorization_id": projection["submission_authorization_id"],
                "event_sequence": projection["last_event_sequence"],
                "event_type": event_type,
                "transport_state_after": state_after,
                "actor_id": TRANSPORT_ACTOR_ID,
                "external_order_id": external_order_id,
                "observation_identity": observation_identity,
                "event_detail": Json(detail or {}),
            },
        )

    @classmethod
    def transition(
        cls,
        context,
        projection: ImmutableRow,
        *,
        event_type: str,
        state_after: str,
        external_order_id: Optional[str] = None,
        observation_identity: Optional[str] = None,
        detail: Optional[dict[str, Any]] = None,
    ) -> ImmutableRow:
        if projection["transport_state"] in TERMINAL_STATES:
            raise TransportConflict("terminal transport projection cannot transition")
        updated = context.update_if_version(
            "transport_submission",
            {"submission_authorization_id": projection["submission_authorization_id"]},
            projection["current_version"],
            {
                "transport_state": state_after,
                "last_event_sequence": projection["last_event_sequence"] + 1,
                "external_order_id": external_order_id,
                "last_error": Json(detail) if state_after == "OUTCOME_UNKNOWN" and detail is not None else None,
            },
            TRANSPORT_COLUMNS,
        )
        cls._insert_event(
            context,
            updated,
            event_type=event_type,
            state_after=state_after,
            external_order_id=external_order_id,
            observation_identity=observation_identity,
            detail=detail,
        )
        return updated


__all__ = [
    "GovernedTransportStore", "HandoffPreparation", "TRANSPORT_ACTOR_ID",
    "TRANSPORT_COLUMNS", "EVENT_COLUMNS", "TERMINAL_STATES",
    "governed_transport_resource_scope", "TransportValidationError",
    "TransportConflict",
]
