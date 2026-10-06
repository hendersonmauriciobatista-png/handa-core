"""Read-only persistence contract for immutable pre-execution decisions."""

from __future__ import annotations

from typing import Optional

from core.persistence.persistence_coordinator import PersistenceCoordinator
from core.persistence.transaction_context import (
    ImmutableRow,
    Predicate,
    PredicateOperator,
    ResourceScope,
    ResourceSpec,
)


LIVE_SCHEMA = "handa_live"
PRE_EXECUTION_DECISION_COLUMNS = (
    "pre_execution_decision_id",
    "intent_id",
    "submission_attempt_id",
    "authority_envelope_id",
    "decision_sequence",
    "decision_outcome",
    "decision_reason",
    "intent_semantic_digest",
    "submission_attempt_semantic_digest",
    "decision_contract_version",
    "decision_engine_version",
    "policy_version",
    "risk_policy_version",
    "strategy_version",
    "input_snapshot_digest",
    "decision_semantics_digest",
    "global_safety_epoch",
    "runtime_generation",
    "runtime_mode",
    "venue",
    "account_scope",
    "evaluated_at",
    "valid_until",
    "recorded_at",
)


def pre_execution_decision_resource_scope() -> ResourceScope:
    """Return the read-only decision scope."""

    decision = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="pre_execution_decision",
        readable_columns=frozenset(PRE_EXECUTION_DECISION_COLUMNS),
        writable_columns=frozenset(),
        key_columns=frozenset({"pre_execution_decision_id"}),
        ordering_columns=(
            "submission_attempt_id",
            "decision_sequence",
            "pre_execution_decision_id",
        ),
    )
    return ResourceScope((decision,))


class PreExecutionDecisionStore:
    """Read-only decision contract; it cannot assert ALLOW or create authority."""

    def __init__(self, coordinator: PersistenceCoordinator):
        self._coordinator = coordinator

    def get_decision(
        self, pre_execution_decision_id: str
    ) -> Optional[ImmutableRow]:
        with self._coordinator.transaction() as context:
            return context.read_by_key(
                "pre_execution_decision",
                {"pre_execution_decision_id": pre_execution_decision_id},
                PRE_EXECUTION_DECISION_COLUMNS,
            )

    def get_latest_for_attempt(
        self, submission_attempt_id: str
    ) -> Optional[ImmutableRow]:
        with self._coordinator.transaction() as context:
            cursor = None
            latest: Optional[ImmutableRow] = None
            while True:
                page = context.enumerate(
                    "pre_execution_decision",
                    (
                        Predicate(
                            "submission_attempt_id",
                            PredicateOperator.EQ,
                            submission_attempt_id,
                        ),
                    ),
                    PRE_EXECUTION_DECISION_COLUMNS,
                    100,
                    cursor,
                )
                for row in page.rows:
                    if (
                        latest is None
                        or row["decision_sequence"] > latest["decision_sequence"]
                        or (
                            row["decision_sequence"] == latest["decision_sequence"]
                            and row["pre_execution_decision_id"]
                            > latest["pre_execution_decision_id"]
                        )
                    ):
                        latest = row
                if page.next_cursor is None:
                    return latest
                cursor = page.next_cursor

