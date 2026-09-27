"""Semantic persistence contract for governed LIVE order evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Optional

from psycopg2.extras import Json

from core.execution.live_order_models import LiveOrderIntent
from core.persistence.persistence_coordinator import PersistenceCoordinator
from core.persistence.transaction_context import (
    ImmutablePage,
    ImmutableRow,
    InvalidCapabilityRequest,
    Predicate,
    PredicateOperator,
    ResourceScope,
    ResourceSpec,
)


LIVE_SCHEMA = "handa_live"


def live_order_resource_scope() -> ResourceScope:
    """Return the exact structured resource scope for the published schema."""

    order_intent = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="order_intent",
        readable_columns=frozenset(
            {
                "intent_id", "venue", "account_scope", "client_order_id",
                "slot_id", "symbol", "side", "requested_quote_amount",
                "requested_base_qty", "policy_context",
                "submission_lifecycle_state", "execution_certainty",
                "reconciliation_state", "exchange_order_id",
                "current_version", "recorded_at",
            }
        ),
        writable_columns=frozenset(
            {
                "intent_id", "venue", "account_scope", "client_order_id",
                "slot_id", "symbol", "side", "requested_quote_amount",
                "requested_base_qty", "policy_context",
                "submission_lifecycle_state", "execution_certainty",
                "reconciliation_state", "exchange_order_id",
                "current_version",
            }
        ),
        key_columns=frozenset({"intent_id"}),
        ordering_columns=("intent_id",),
        version_column="current_version",
    )
    submission_attempt = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="submission_attempt",
        readable_columns=frozenset(
            {
                "attempt_id", "intent_id", "attempt_sequence", "venue",
                "account_scope", "client_order_id",
                "submission_lifecycle_state", "exchange_order_id",
                "transport_status", "transport_error", "recorded_at",
                "observed_at", "exchange_event_time",
            }
        ),
        writable_columns=frozenset(
            {
                "attempt_id", "intent_id", "attempt_sequence", "venue",
                "account_scope", "client_order_id",
                "submission_lifecycle_state", "exchange_order_id",
                "transport_status", "transport_error", "observed_at",
                "exchange_event_time",
            }
        ),
        key_columns=frozenset({"attempt_id"}),
        ordering_columns=("attempt_sequence", "attempt_id"),
    )
    exchange_evidence = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="exchange_evidence",
        readable_columns=frozenset(
            {
                "evidence_id", "intent_id", "attempt_id", "evidence_sequence",
                "symbol", "exchange_order_id", "exchange_status",
                "raw_snapshot", "recorded_at", "observed_at",
                "exchange_event_time",
            }
        ),
        writable_columns=frozenset(
            {
                "evidence_id", "intent_id", "attempt_id", "evidence_sequence",
                "symbol", "exchange_order_id", "exchange_status",
                "raw_snapshot", "observed_at", "exchange_event_time",
            }
        ),
        key_columns=frozenset({"evidence_id"}),
        ordering_columns=("evidence_sequence", "evidence_id"),
    )
    trade_effect = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="trade_effect",
        readable_columns=frozenset(
            {
                "symbol", "exchange_order_id", "exchange_trade_id",
                "evidence_id", "intent_id", "price", "gross_base_qty",
                "quote_qty", "commission_amount", "commission_asset",
                "recorded_at", "exchange_event_time",
            }
        ),
        writable_columns=frozenset(
            {
                "symbol", "exchange_order_id", "exchange_trade_id",
                "evidence_id", "intent_id", "price", "gross_base_qty",
                "quote_qty", "commission_amount", "commission_asset",
                "exchange_event_time",
            }
        ),
        key_columns=frozenset(
            {"symbol", "exchange_order_id", "exchange_trade_id"}
        ),
        ordering_columns=(
            "recorded_at", "symbol", "exchange_order_id", "exchange_trade_id"
        ),
    )
    normalized_evidence = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="normalized_evidence",
        readable_columns=frozenset(
            {
                "normalized_revision_id", "evidence_id", "intent_id",
                "revision_sequence", "exchange_status", "normalized_status",
                "provenance", "normalized_payload", "recorded_at",
            }
        ),
        writable_columns=frozenset(
            {
                "normalized_revision_id", "evidence_id", "intent_id",
                "revision_sequence", "exchange_status", "normalized_status",
                "provenance", "normalized_payload",
            }
        ),
        key_columns=frozenset({"normalized_revision_id"}),
        ordering_columns=("revision_sequence", "normalized_revision_id"),
    )
    reconciliation = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="reconciliation",
        readable_columns=frozenset(
            {
                "reconciliation_id", "intent_id", "decision_sequence",
                "reconciliation_state", "execution_certainty",
                "decision_reason", "recorded_at", "resolved_at",
            }
        ),
        writable_columns=frozenset(
            {
                "reconciliation_id", "intent_id", "decision_sequence",
                "reconciliation_state", "execution_certainty",
                "decision_reason", "resolved_at",
            }
        ),
        key_columns=frozenset({"reconciliation_id"}),
        ordering_columns=("decision_sequence", "reconciliation_id"),
    )
    return ResourceScope(
        (
            order_intent,
            submission_attempt,
            exchange_evidence,
            trade_effect,
            normalized_evidence,
            reconciliation,
        )
    )


class LiveOrderStore:
    """Semantic Store using coordinator-owned structured transactions only."""

    def __init__(self, coordinator: PersistenceCoordinator):
        self._coordinator = coordinator

    def create_intent(
        self, intent: LiveOrderIntent, *, venue: str, account_scope: str
    ) -> ImmutableRow:
        values = {
            "intent_id": intent.intent_id,
            "venue": venue,
            "account_scope": account_scope,
            "client_order_id": intent.client_order_id,
            "slot_id": intent.slot_id,
            "symbol": intent.symbol,
            "side": intent.side.value,
            "requested_quote_amount": intent.requested_quote_amount,
            "requested_base_qty": intent.requested_base_qty,
            "policy_context": intent.policy_context,
            "submission_lifecycle_state": "READY_TO_SUBMIT",
            "execution_certainty": None,
            "reconciliation_state": None,
        }
        return self._run(
            lambda context: context.insert_returning(
                "order_intent", values, _ORDER_COLUMNS
            )
        )

    def record_submission_preparation(
        self,
        *,
        intent_id: str,
        attempt_id: str,
        attempt_sequence: int,
        venue: str,
        account_scope: str,
        client_order_id: str,
        expected_version: int,
    ) -> ImmutableRow:
        def operation(context):
            current = context.read_by_key(
                "order_intent", {"intent_id": intent_id}, _ORDER_COLUMNS
            )
            if current is None or current["submission_lifecycle_state"] != "READY_TO_SUBMIT":
                raise ValueError("submission preparation requires READY_TO_SUBMIT")
            if current["execution_certainty"] is not None:
                raise ValueError("submission preparation requires NULL execution certainty")
            if (
                current["venue"] != venue
                or current["account_scope"] != account_scope
                or current["client_order_id"] != client_order_id
            ):
                raise ValueError(
                    "submission preparation identity does not match persisted intent"
                )
            context.insert(
                "submission_attempt",
                {
                    "attempt_id": attempt_id,
                    "intent_id": intent_id,
                    "attempt_sequence": attempt_sequence,
                    "venue": venue,
                    "account_scope": account_scope,
                    "client_order_id": client_order_id,
                    "submission_lifecycle_state": "SUBMISSION_ATTEMPTED",
                },
            )
            return context.update_if_version(
                "order_intent",
                {"intent_id": intent_id},
                expected_version,
                {
                    "submission_lifecycle_state": "SUBMISSION_ATTEMPTED",
                    "execution_certainty": None,
                    "reconciliation_state": None,
                },
                _ORDER_COLUMNS,
            )

        return self._run(operation)

    def record_external_handoff(
        self,
        *,
        intent_id: str,
        expected_version: int,
        reconciliation_state: str = "PENDING",
    ) -> ImmutableRow:
        if reconciliation_state not in {"PENDING", "BLOCKED"}:
            raise InvalidCapabilityRequest(
                "external handoff requires PENDING or BLOCKED reconciliation"
            )

        def operation(context):
            current = context.read_by_key(
                "order_intent", {"intent_id": intent_id}, _ORDER_COLUMNS
            )
            if current is None or current["submission_lifecycle_state"] != "SUBMISSION_ATTEMPTED":
                raise ValueError("external handoff requires submission preparation")
            if current["execution_certainty"] is not None:
                raise ValueError("external handoff requires NULL execution certainty")
            return context.update_if_version(
                "order_intent",
                {"intent_id": intent_id},
                expected_version,
                {
                    "submission_lifecycle_state": "MAY_HAVE_BEEN_SUBMITTED",
                    "execution_certainty": "UNKNOWN",
                    "reconciliation_state": reconciliation_state,
                },
                _ORDER_COLUMNS,
            )

        return self._run(operation)

    def record_exchange_observation(
        self,
        *,
        evidence_id: str,
        intent_id: str,
        evidence_sequence: int,
        symbol: str,
        raw_snapshot: Mapping[str, Any],
        observed_at: Any,
        attempt_id: Optional[str] = None,
        exchange_order_id: Optional[str] = None,
        exchange_status: Optional[str] = None,
        exchange_event_time: Any = None,
        normalized_revision: Optional[Mapping[str, Any]] = None,
        trade_effects: Sequence[Mapping[str, Any]] = (),
        expected_version: Optional[int] = None,
    ) -> None:
        def operation(context):
            context.insert(
                "exchange_evidence",
                {
                    "evidence_id": evidence_id,
                    "intent_id": intent_id,
                    "attempt_id": attempt_id,
                    "evidence_sequence": evidence_sequence,
                    "symbol": symbol,
                    "exchange_order_id": exchange_order_id,
                    "exchange_status": exchange_status,
                    "raw_snapshot": Json(dict(raw_snapshot)),
                    "observed_at": observed_at,
                    "exchange_event_time": exchange_event_time,
                },
            )
            for effect in trade_effects:
                context.insert(
                    "trade_effect",
                    _trade_effect_values(effect, evidence_id, intent_id),
                )
            if normalized_revision is not None:
                context.insert(
                    "normalized_evidence",
                    _normalized_values(normalized_revision, evidence_id, intent_id),
                )
            if exchange_order_id is not None:
                if expected_version is None:
                    raise InvalidCapabilityRequest(
                        "expected_version is required when associating exchange order"
                    )
                current = context.read_by_key(
                    "order_intent", {"intent_id": intent_id}, _ORDER_COLUMNS
                )
                if current is None:
                    raise ValueError("exchange observation requires an existing intent")
                if (
                    current["exchange_order_id"] is not None
                    and current["exchange_order_id"] != exchange_order_id
                ):
                    raise ValueError("exchange order correlation conflict")
                context.update_if_version(
                    "order_intent",
                    {"intent_id": intent_id},
                    expected_version,
                    {"exchange_order_id": exchange_order_id},
                    _ORDER_COLUMNS,
                )

        self._run(operation)

    def append_normalized_revision(
        self, *, evidence_id: str, intent_id: str, revision: Mapping[str, Any]
    ) -> None:
        self._run(
            lambda context: context.insert(
                "normalized_evidence",
                _normalized_values(revision, evidence_id, intent_id),
            )
        )

    def append_trade_effects(
        self,
        *,
        evidence_id: str,
        intent_id: str,
        effects: Sequence[Mapping[str, Any]],
    ) -> None:
        def operation(context):
            for effect in effects:
                context.insert(
                    "trade_effect",
                    _trade_effect_values(effect, evidence_id, intent_id),
                )

        self._run(operation)

    def associate_exchange_order(
        self,
        *,
        intent_id: str,
        exchange_order_id: str,
        expected_version: int,
    ) -> ImmutableRow:
        def operation(context):
            current = context.read_by_key(
                "order_intent", {"intent_id": intent_id}, _ORDER_COLUMNS
            )
            if current is None:
                raise ValueError("exchange order association requires an existing intent")
            if (
                current["exchange_order_id"] is not None
                and current["exchange_order_id"] != exchange_order_id
            ):
                raise ValueError("exchange order correlation conflict")
            return context.update_if_version(
                "order_intent",
                {"intent_id": intent_id},
                expected_version,
                {"exchange_order_id": exchange_order_id},
                _ORDER_COLUMNS,
            )

        return self._run(operation)

    def append_reconciliation_decision(
        self,
        *,
        reconciliation_id: str,
        intent_id: str,
        decision_sequence: int,
        reconciliation_state: str,
        execution_certainty: str,
        expected_version: int,
        decision_reason: Optional[str] = None,
        resolved_at: Any = None,
    ) -> ImmutableRow:
        _validate_reconciliation_boundary(
            reconciliation_state, execution_certainty
        )

        def operation(context):
            context.insert(
                "reconciliation",
                {
                    "reconciliation_id": reconciliation_id,
                    "intent_id": intent_id,
                    "decision_sequence": decision_sequence,
                    "reconciliation_state": reconciliation_state,
                    "execution_certainty": execution_certainty,
                    "decision_reason": decision_reason,
                    "resolved_at": resolved_at,
                },
            )
            return context.update_if_version(
                "order_intent",
                {"intent_id": intent_id},
                expected_version,
                {
                    "execution_certainty": execution_certainty,
                    "reconciliation_state": reconciliation_state,
                },
                _ORDER_COLUMNS,
            )

        return self._run(operation)

    def find_unresolved(self, *, limit: int, cursor: Optional[str] = None) -> ImmutablePage:
        return self._find_order_page(
            [Predicate("execution_certainty", PredicateOperator.EQ, "UNKNOWN")],
            limit,
            cursor,
        )

    def find_unresolved_by_symbol(
        self, *, symbol: str, limit: int, cursor: Optional[str] = None
    ) -> ImmutablePage:
        return self._find_order_page(
            [
                Predicate("symbol", PredicateOperator.EQ, symbol),
                Predicate("execution_certainty", PredicateOperator.EQ, "UNKNOWN"),
            ],
            limit,
            cursor,
        )

    def find_by_client_namespace(
        self, *, venue: str, account_scope: str, client_order_id: str
    ) -> Optional[ImmutableRow]:
        page = self._find_order_page(
            [
                Predicate("venue", PredicateOperator.EQ, venue),
                Predicate("account_scope", PredicateOperator.EQ, account_scope),
                Predicate("client_order_id", PredicateOperator.EQ, client_order_id),
            ],
            1,
        )
        return page.rows[0] if page.rows else None

    def find_by_exchange_correlation(
        self, *, symbol: str, exchange_order_id: str, limit: int = 100
    ) -> ImmutablePage:
        return self._find_order_page(
            [
                Predicate("symbol", PredicateOperator.EQ, symbol),
                Predicate("exchange_order_id", PredicateOperator.EQ, exchange_order_id),
            ],
            limit,
        )

    def enumerate_evidence(
        self, *, intent_id: str, limit: int, cursor: Optional[str] = None
    ) -> ImmutablePage:
        return self._run(
            lambda context: context.enumerate(
                "exchange_evidence",
                [Predicate("intent_id", PredicateOperator.EQ, intent_id)],
                _EVIDENCE_COLUMNS,
                limit,
                cursor,
            )
        )

    def _find_order_page(
        self,
        predicates: Sequence[Predicate],
        limit: int,
        cursor: Optional[str] = None,
    ) -> ImmutablePage:
        return self._run(
            lambda context: context.enumerate(
                "order_intent", predicates, _ORDER_COLUMNS, limit, cursor
            )
        )

    def _run(self, operation):
        with self._coordinator.transaction() as context:
            return operation(context)


_ORDER_COLUMNS = (
    "intent_id", "venue", "account_scope", "client_order_id", "slot_id",
    "symbol", "side", "requested_quote_amount", "requested_base_qty",
    "policy_context", "submission_lifecycle_state", "execution_certainty",
    "reconciliation_state", "exchange_order_id", "current_version",
    "recorded_at",
)

_EVIDENCE_COLUMNS = (
    "evidence_id", "intent_id", "attempt_id", "evidence_sequence", "symbol",
    "exchange_order_id", "exchange_status", "raw_snapshot", "recorded_at",
    "observed_at", "exchange_event_time",
)


def _trade_effect_values(effect, evidence_id: str, intent_id: str):
    required = (
        "symbol", "exchange_order_id", "exchange_trade_id", "price",
        "gross_base_qty", "quote_qty", "commission_amount", "commission_asset",
    )
    missing = [name for name in required if name not in effect]
    if missing:
        raise InvalidCapabilityRequest(
            f"trade effect requires {', '.join(missing)}"
        )
    values = {name: effect[name] for name in required}
    values.update(
        {
            "evidence_id": evidence_id,
            "intent_id": intent_id,
            "exchange_event_time": effect.get("exchange_event_time"),
        }
    )
    return values


def _normalized_values(revision, evidence_id: str, intent_id: str):
    for name in ("normalized_revision_id", "revision_sequence", "normalized_status"):
        if name not in revision:
            raise InvalidCapabilityRequest(f"normalized revision requires {name}")
    return {
        "normalized_revision_id": revision["normalized_revision_id"],
        "evidence_id": evidence_id,
        "intent_id": intent_id,
        "revision_sequence": revision["revision_sequence"],
        "exchange_status": revision.get("exchange_status"),
        "normalized_status": revision["normalized_status"],
        "provenance": Json(dict(revision.get("provenance", {}))),
        "normalized_payload": Json(dict(revision.get("normalized_payload", {}))),
    }


def _validate_reconciliation_boundary(state: str, certainty: str) -> None:
    if certainty == "UNKNOWN" and state not in {"PENDING", "BLOCKED"}:
        raise InvalidCapabilityRequest(
            "UNKNOWN requires PENDING or BLOCKED reconciliation"
        )
    if certainty == "NO_EFFECT_CONFIRMED" and state != "RESOLVED":
        raise InvalidCapabilityRequest(
            "NO_EFFECT_CONFIRMED requires RESOLVED reconciliation"
        )
    if certainty == "EXECUTION_CONFIRMED" and state != "RESOLVED":
        raise InvalidCapabilityRequest(
            "EXECUTION_CONFIRMED requires RESOLVED reconciliation"
        )
    if certainty not in {
        "UNKNOWN", "NO_EFFECT_CONFIRMED", "EXECUTION_CONFIRMED"
    }:
        raise InvalidCapabilityRequest("unsupported execution certainty")
    if state not in {"NOT_REQUIRED", "PENDING", "RESOLVED", "BLOCKED"}:
        raise InvalidCapabilityRequest("unsupported reconciliation state")
