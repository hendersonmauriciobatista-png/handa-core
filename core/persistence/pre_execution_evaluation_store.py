"""Evaluator-owned, least-authority persistence boundary."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Optional

from core.persistence.authority_envelope_store import authority_envelope_resource_scope
from core.persistence.operational_authority_state_store import (
    operational_authority_state_resource_scope,
)
from core.persistence.persistence_coordinator import PersistenceCoordinator
from core.persistence.pre_execution_decision_store import (
    PRE_EXECUTION_DECISION_COLUMNS,
)
from core.persistence.transaction_context import (
    ImmutablePage,
    ImmutableRow,
    Predicate,
    PredicateOperator,
    ResourceScope,
    ResourceSpec,
)


LIVE_SCHEMA = "handa_live"

ORDER_INTENT_COLUMNS = (
    "intent_id", "venue", "account_scope", "client_order_id", "slot_id",
    "symbol", "side", "requested_quote_amount", "requested_base_qty",
    "policy_context", "submission_lifecycle_state", "execution_certainty",
    "reconciliation_state", "exchange_order_id", "current_version",
    "current_context_id", "current_decision_id", "recorded_at",
)

SUBMISSION_ATTEMPT_COLUMNS = (
    "attempt_id", "intent_id", "attempt_sequence", "venue", "context_id",
    "account_scope", "client_order_id", "submission_lifecycle_state",
    "exchange_order_id", "transport_status", "transport_error", "recorded_at",
    "observed_at", "exchange_event_time",
)

EVALUATION_DECISION_COLUMNS = (
    *PRE_EXECUTION_DECISION_COLUMNS,
    "evaluation_request_id",
    "evaluation_request_digest",
)


def pre_execution_evaluation_resource_scope() -> ResourceScope:
    """Return only resources needed by one evaluator transaction."""

    order_intent = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="order_intent",
        readable_columns=frozenset(ORDER_INTENT_COLUMNS),
        writable_columns=frozenset(),
        key_columns=frozenset({"intent_id"}),
        ordering_columns=("intent_id",),
    )
    submission_attempt = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="submission_attempt",
        readable_columns=frozenset(SUBMISSION_ATTEMPT_COLUMNS),
        writable_columns=frozenset(),
        key_columns=frozenset({"attempt_id"}),
        ordering_columns=("attempt_sequence", "attempt_id"),
    )
    decision = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="pre_execution_decision",
        readable_columns=frozenset(EVALUATION_DECISION_COLUMNS),
        writable_columns=frozenset(
            column for column in EVALUATION_DECISION_COLUMNS if column != "recorded_at"
        ),
        key_columns=frozenset({"pre_execution_decision_id"}),
        ordering_columns=(
            "evaluation_request_id", "decision_sequence", "pre_execution_decision_id"
        ),
    )
    resources = (
        *operational_authority_state_resource_scope().resources,
        *authority_envelope_resource_scope().resources,
        order_intent,
        submission_attempt,
        decision,
    )
    return ResourceScope(resources)


class PreExecutionEvaluationPersistence:
    """Internal persistence capability owned by the evaluator only."""

    def __init__(self, coordinator: PersistenceCoordinator):
        self._coordinator = coordinator

    def transaction(self) -> AbstractContextManager[Any]:
        return self._coordinator.transaction()

    @staticmethod
    def get_state(context) -> Optional[ImmutableRow]:
        return context.read_by_key(
            "operational_authority_state", {"state_id": True},
            (
                "state_id", "operational_mode", "active_authority_envelope_id",
                "global_safety_epoch", "runtime_generation", "current_version",
                "last_event_id", "changed_by", "change_reason", "updated_at",
            ),
        )

    @staticmethod
    def get_envelope(context, authority_envelope_id: str) -> Optional[ImmutableRow]:
        return context.read_by_key(
            "authority_envelope", {"authority_envelope_id": authority_envelope_id},
            (
                "authority_envelope_id", "envelope_version", "runtime_mode", "venue",
                "account_scope", "allowed_sides", "strategy_version",
                "decision_contract_version", "policy_version", "risk_policy_version",
                "valid_from", "valid_until", "configuration_digest",
                "authority_contract_version", "approved_by", "approved_at",
                "approval_reason", "created_at",
            ),
        )

    @staticmethod
    def get_intent(context, intent_id: str) -> Optional[ImmutableRow]:
        return context.read_by_key("order_intent", {"intent_id": intent_id}, ORDER_INTENT_COLUMNS)

    @staticmethod
    def get_attempt(context, attempt_id: str) -> Optional[ImmutableRow]:
        return context.read_by_key(
            "submission_attempt", {"attempt_id": attempt_id}, SUBMISSION_ATTEMPT_COLUMNS
        )

    @staticmethod
    def find_request(context, evaluation_request_id: str) -> Optional[ImmutableRow]:
        page: ImmutablePage = context.enumerate(
            "pre_execution_decision",
            (
                Predicate(
                    "evaluation_request_id",
                    PredicateOperator.EQ,
                    evaluation_request_id,
                ),
            ),
            EVALUATION_DECISION_COLUMNS,
            1,
        )
        return page.rows[0] if page.rows else None

    @staticmethod
    def allocate_sequence(context, submission_attempt_id: str) -> int:
        return context.allocate_next_sequence(
            "pre_execution_decision",
            "submission_attempt_id",
            submission_attempt_id,
            "decision_sequence",
            "submission_attempt",
            lock_owner_column="attempt_id",
        )

    @staticmethod
    def _insert_block(context, values: dict[str, Any]) -> ImmutableRow:
        return context.insert_returning(
            "pre_execution_decision", values, EVALUATION_DECISION_COLUMNS
        )
