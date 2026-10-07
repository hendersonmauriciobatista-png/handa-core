"""Least-authority persistence boundary for submission authorization issuance."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Optional

from core.persistence.persistence_coordinator import PersistenceCoordinator
from core.persistence.pre_execution_decision_store import PRE_EXECUTION_DECISION_COLUMNS
from core.persistence.transaction_context import (
    ImmutablePage,
    ImmutableRow,
    Predicate,
    PredicateOperator,
    ResourceScope,
    ResourceSpec,
)


LIVE_SCHEMA = "handa_live"

STATE_COLUMNS = (
    "state_id", "operational_mode", "active_authority_envelope_id",
    "global_safety_epoch", "runtime_generation", "current_version",
    "last_event_id", "changed_by", "change_reason", "updated_at",
)
ENVELOPE_COLUMNS = (
    "authority_envelope_id", "envelope_version", "runtime_mode", "venue",
    "account_scope", "allowed_sides", "strategy_version",
    "decision_contract_version", "policy_version", "risk_policy_version",
    "valid_from", "valid_until", "configuration_digest",
    "authority_contract_version", "approved_by", "approved_at",
    "approval_reason", "created_at",
)
INTENT_COLUMNS = (
    "intent_id", "venue", "account_scope", "client_order_id", "slot_id",
    "symbol", "side", "requested_quote_amount", "requested_base_qty",
    "policy_context", "submission_lifecycle_state", "execution_certainty",
    "reconciliation_state", "exchange_order_id", "current_version",
    "current_context_id", "current_decision_id", "recorded_at",
)
ATTEMPT_COLUMNS = (
    "attempt_id", "intent_id", "attempt_sequence", "venue", "context_id",
    "account_scope", "client_order_id", "submission_lifecycle_state",
    "exchange_order_id", "transport_status", "transport_error", "recorded_at",
    "observed_at", "exchange_event_time",
)
EXCHANGE_EVIDENCE_COLUMNS = (
    "evidence_id", "intent_id", "attempt_id", "evidence_sequence", "symbol",
    "exchange_order_id", "exchange_status", "raw_snapshot", "recorded_at",
    "observed_at", "exchange_event_time",
)
AUTHORIZATION_COLUMNS = (
    "submission_authorization_id", "intent_id", "submission_attempt_id",
    "client_order_id", "venue", "account_scope", "symbol", "side",
    "requested_quote_amount", "requested_base_qty", "authority_reference_id",
    "issuer_id", "authority_contract_version", "authorization_sequence",
    "submission_fingerprint", "authorization_state", "current_version",
    "claimed_by", "claimed_at", "created_at",
)
AUTHORIZATION_INSERT_COLUMNS = frozenset({
    "submission_authorization_id", "intent_id", "submission_attempt_id",
    "client_order_id", "venue", "account_scope", "symbol", "side",
    "requested_quote_amount", "requested_base_qty", "authority_reference_id",
    "issuer_id", "authority_contract_version", "authorization_sequence",
    "submission_fingerprint", "authorization_state",
})


def submission_authorization_issuer_resource_scope() -> ResourceScope:
    """Return the issuer scope; claims and all other mutations remain absent."""

    state = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="operational_authority_state",
        readable_columns=frozenset(STATE_COLUMNS),
        writable_columns=frozenset(),
        key_columns=frozenset({"state_id"}),
        ordering_columns=("state_id",),
    )
    envelope = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="authority_envelope",
        readable_columns=frozenset(ENVELOPE_COLUMNS),
        writable_columns=frozenset(),
        key_columns=frozenset({"authority_envelope_id"}),
        ordering_columns=("authority_envelope_id",),
    )
    intent = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="order_intent",
        readable_columns=frozenset(INTENT_COLUMNS),
        writable_columns=frozenset(),
        key_columns=frozenset({"intent_id"}),
        ordering_columns=("intent_id",),
    )
    attempt = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="submission_attempt",
        readable_columns=frozenset(ATTEMPT_COLUMNS),
        writable_columns=frozenset(),
        key_columns=frozenset({"attempt_id"}),
        ordering_columns=("attempt_id",),
    )
    decision = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="pre_execution_decision",
        readable_columns=frozenset(PRE_EXECUTION_DECISION_COLUMNS),
        writable_columns=frozenset(),
        key_columns=frozenset({"pre_execution_decision_id"}),
        ordering_columns=(
            "submission_attempt_id", "decision_sequence",
            "pre_execution_decision_id",
        ),
    )
    evidence = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="exchange_evidence",
        readable_columns=frozenset(EXCHANGE_EVIDENCE_COLUMNS),
        writable_columns=frozenset(),
        key_columns=frozenset({"evidence_id"}),
        ordering_columns=("attempt_id", "evidence_sequence", "evidence_id"),
    )
    authorization = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="submission_authorization",
        readable_columns=frozenset(AUTHORIZATION_COLUMNS),
        writable_columns=AUTHORIZATION_INSERT_COLUMNS,
        key_columns=frozenset({"submission_authorization_id"}),
        ordering_columns=("submission_attempt_id", "submission_authorization_id"),
    )
    return ResourceScope((state, envelope, intent, attempt, decision, evidence, authorization))


class SubmissionAuthorizationIssuerPersistence:
    """Internal issuer capability; it has no claim/update operation."""

    def __init__(self, coordinator: PersistenceCoordinator):
        self._coordinator = coordinator

    def _transaction(self) -> AbstractContextManager[Any]:
        return self._coordinator.transaction()

    @staticmethod
    def get_state_for_update(context) -> Optional[ImmutableRow]:
        return context.read_by_key_for_update(
            "operational_authority_state", {"state_id": True}, STATE_COLUMNS
        )

    @staticmethod
    def get_envelope(context, envelope_id: str) -> Optional[ImmutableRow]:
        return context.read_by_key("authority_envelope", {"authority_envelope_id": envelope_id}, ENVELOPE_COLUMNS)

    @staticmethod
    def get_intent(context, intent_id: str, *, for_update: bool = False) -> Optional[ImmutableRow]:
        reader = context.read_by_key_for_update if for_update else context.read_by_key
        return reader("order_intent", {"intent_id": intent_id}, INTENT_COLUMNS)

    @staticmethod
    def get_attempt(context, attempt_id: str, *, for_update: bool = False) -> Optional[ImmutableRow]:
        reader = context.read_by_key_for_update if for_update else context.read_by_key
        return reader("submission_attempt", {"attempt_id": attempt_id}, ATTEMPT_COLUMNS)

    @staticmethod
    def find_authorization(context, attempt_id: str) -> Optional[ImmutableRow]:
        page: ImmutablePage = context.enumerate(
            "submission_authorization",
            (Predicate("submission_attempt_id", PredicateOperator.EQ, attempt_id),),
            AUTHORIZATION_COLUMNS,
            1,
        )
        return page.rows[0] if page.rows else None

    @staticmethod
    def get_decision(context, decision_id: str) -> Optional[ImmutableRow]:
        return context.read_by_key(
            "pre_execution_decision", {"pre_execution_decision_id": decision_id},
            PRE_EXECUTION_DECISION_COLUMNS,
        )

    @staticmethod
    def latest_decision(context, attempt_id: str) -> Optional[ImmutableRow]:
        cursor = None
        latest: Optional[ImmutableRow] = None
        while True:
            page: ImmutablePage = context.enumerate(
                "pre_execution_decision",
                (Predicate("submission_attempt_id", PredicateOperator.EQ, attempt_id),),
                PRE_EXECUTION_DECISION_COLUMNS,
                100,
                cursor,
            )
            for row in page.rows:
                if latest is None or (
                    row["decision_sequence"], row["pre_execution_decision_id"]
                ) > (
                    latest["decision_sequence"], latest["pre_execution_decision_id"]
                ):
                    latest = row
            if page.next_cursor is None:
                return latest
            cursor = page.next_cursor

    @staticmethod
    def has_exchange_evidence(context, attempt_id: str) -> bool:
        page: ImmutablePage = context.enumerate(
            "exchange_evidence",
            (Predicate("attempt_id", PredicateOperator.EQ, attempt_id),),
            ("evidence_id",),
            1,
        )
        return bool(page.rows)

    @staticmethod
    def _insert_authorized(
        context,
        *,
        submission_authorization_id: str,
        intent_id: str,
        submission_attempt_id: str,
        client_order_id: str,
        venue: str,
        account_scope: str,
        symbol: str,
        side: str,
        requested_quote_amount: Any,
        requested_base_qty: Any,
        authority_reference_id: str,
        issuer_id: str,
        authority_contract_version: str,
        authorization_sequence: int,
        submission_fingerprint: str,
    ) -> ImmutableRow:
        values = {
            "submission_authorization_id": submission_authorization_id,
            "intent_id": intent_id,
            "submission_attempt_id": submission_attempt_id,
            "client_order_id": client_order_id,
            "venue": venue,
            "account_scope": account_scope,
            "symbol": symbol,
            "side": side,
            "requested_quote_amount": requested_quote_amount,
            "requested_base_qty": requested_base_qty,
            "authority_reference_id": authority_reference_id,
            "issuer_id": issuer_id,
            "authority_contract_version": authority_contract_version,
            "authorization_sequence": authorization_sequence,
            "submission_fingerprint": submission_fingerprint,
            "authorization_state": "AUTHORIZED",
        }
        return context.insert_returning(
            "submission_authorization", values, AUTHORIZATION_COLUMNS
        )
