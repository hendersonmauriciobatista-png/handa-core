"""Least-authority persistence boundary for claim-time revalidation."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Optional

from core.persistence.persistence_coordinator import PersistenceCoordinator
from core.persistence.pre_execution_decision_store import PRE_EXECUTION_DECISION_COLUMNS
from core.persistence.submission_authorization_issuer_store import (
    ATTEMPT_COLUMNS,
    AUTHORIZATION_COLUMNS,
    ENVELOPE_COLUMNS,
    EXCHANGE_EVIDENCE_COLUMNS,
    INTENT_COLUMNS,
    LIVE_SCHEMA,
    STATE_COLUMNS,
)
from core.persistence.transaction_context import (
    ImmutablePage,
    ImmutableRow,
    Predicate,
    PredicateOperator,
    ResourceScope,
    ResourceSpec,
)


AUTHORIZATION_CLAIM_WRITE_COLUMNS = frozenset({
    "authorization_state", "current_version", "claimed_by", "claimed_at",
})


def submission_claim_resource_scope() -> ResourceScope:
    """Return the bounded read/lock scope for one governed claim."""

    specs = (
        ResourceSpec(LIVE_SCHEMA, "operational_authority_state", frozenset(STATE_COLUMNS), frozenset(), frozenset({"state_id"}), ("state_id",)),
        ResourceSpec(LIVE_SCHEMA, "authority_envelope", frozenset(ENVELOPE_COLUMNS), frozenset(), frozenset({"authority_envelope_id"}), ("authority_envelope_id",)),
        ResourceSpec(LIVE_SCHEMA, "order_intent", frozenset(INTENT_COLUMNS), frozenset(), frozenset({"intent_id"}), ("intent_id",)),
        ResourceSpec(LIVE_SCHEMA, "submission_attempt", frozenset(ATTEMPT_COLUMNS), frozenset(), frozenset({"attempt_id"}), ("attempt_id",)),
        ResourceSpec(LIVE_SCHEMA, "pre_execution_decision", frozenset(PRE_EXECUTION_DECISION_COLUMNS), frozenset(), frozenset({"pre_execution_decision_id"}), ("submission_attempt_id", "decision_sequence", "pre_execution_decision_id")),
        ResourceSpec(LIVE_SCHEMA, "exchange_evidence", frozenset(EXCHANGE_EVIDENCE_COLUMNS), frozenset(), frozenset({"evidence_id"}), ("attempt_id", "evidence_sequence", "evidence_id")),
        ResourceSpec(LIVE_SCHEMA, "submission_authorization", frozenset(AUTHORIZATION_COLUMNS), AUTHORIZATION_CLAIM_WRITE_COLUMNS, frozenset({"submission_authorization_id"}), ("submission_authorization_id",), version_column="current_version"),
    )
    return ResourceScope(specs)


class SubmissionClaimPersistence:
    """Internal persistence capability; it cannot insert or alter authority facts."""

    def __init__(self, coordinator: PersistenceCoordinator):
        self._coordinator = coordinator

    def _transaction(self) -> AbstractContextManager[Any]:
        return self._coordinator.transaction()

    @staticmethod
    def get_state_for_update(context) -> Optional[ImmutableRow]:
        return context.read_by_key_for_update("operational_authority_state", {"state_id": True}, STATE_COLUMNS)

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
    def get_authorization(context, authorization_id: str, *, for_update: bool = False) -> Optional[ImmutableRow]:
        reader = context.read_by_key_for_update if for_update else context.read_by_key
        return reader("submission_authorization", {"submission_authorization_id": authorization_id}, AUTHORIZATION_COLUMNS)

    @staticmethod
    def get_decision(context, decision_id: str) -> Optional[ImmutableRow]:
        return context.read_by_key("pre_execution_decision", {"pre_execution_decision_id": decision_id}, PRE_EXECUTION_DECISION_COLUMNS)

    @staticmethod
    def latest_decision(context, attempt_id: str) -> Optional[ImmutableRow]:
        cursor = None
        latest: Optional[ImmutableRow] = None
        while True:
            page: ImmutablePage = context.enumerate("pre_execution_decision", (Predicate("submission_attempt_id", PredicateOperator.EQ, attempt_id),), PRE_EXECUTION_DECISION_COLUMNS, 100, cursor)
            for row in page.rows:
                if latest is None or (row["decision_sequence"], row["pre_execution_decision_id"]) > (latest["decision_sequence"], latest["pre_execution_decision_id"]):
                    latest = row
            if page.next_cursor is None:
                return latest
            cursor = page.next_cursor

    @staticmethod
    def has_exchange_evidence(context, attempt_id: str) -> bool:
        page = context.enumerate("exchange_evidence", (Predicate("attempt_id", PredicateOperator.EQ, attempt_id),), ("evidence_id",), 1)
        return bool(page.rows)

    @staticmethod
    def claim_authorization(context, authorization_id: str, claimant_id: str) -> ImmutableRow:
        return context.update_if_version("submission_authorization", {"submission_authorization_id": authorization_id}, 0, {"authorization_state": "CLAIMED", "claimed_by": claimant_id, "claimed_at": None}, AUTHORIZATION_COLUMNS)


__all__ = ["SubmissionClaimPersistence", "submission_claim_resource_scope"]
