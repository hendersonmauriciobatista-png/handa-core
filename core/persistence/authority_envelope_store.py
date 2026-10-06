"""Read-only persistence contract for durable authority envelopes."""

from __future__ import annotations

from typing import Optional

from core.persistence.persistence_coordinator import PersistenceCoordinator
from core.persistence.transaction_context import (
    ImmutablePage,
    ImmutableRow,
    Predicate,
    PredicateOperator,
    ResourceScope,
    ResourceSpec,
)


LIVE_SCHEMA = "handa_live"

AUTHORITY_ENVELOPE_COLUMNS = (
    "authority_envelope_id",
    "envelope_version",
    "runtime_mode",
    "venue",
    "account_scope",
    "allowed_sides",
    "strategy_version",
    "decision_contract_version",
    "policy_version",
    "risk_policy_version",
    "valid_from",
    "valid_until",
    "configuration_digest",
    "authority_contract_version",
    "approved_by",
    "approved_at",
    "approval_reason",
    "created_at",
)

AUTHORITY_ENVELOPE_EVENT_COLUMNS = (
    "event_id",
    "authority_envelope_id",
    "event_sequence",
    "event_type",
    "actor_id",
    "reason",
    "safety_epoch_after",
    "runtime_generation_after",
    "recorded_at",
)


def authority_envelope_resource_scope() -> ResourceScope:
    """Return the read-only scope for envelope definitions and history."""

    envelope = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="authority_envelope",
        readable_columns=frozenset(AUTHORITY_ENVELOPE_COLUMNS),
        writable_columns=frozenset(),
        key_columns=frozenset({"authority_envelope_id"}),
        ordering_columns=("authority_envelope_id",),
    )
    event = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="authority_envelope_event",
        readable_columns=frozenset(AUTHORITY_ENVELOPE_EVENT_COLUMNS),
        writable_columns=frozenset(),
        key_columns=frozenset({"event_id"}),
        ordering_columns=("authority_envelope_id", "event_sequence", "event_id"),
    )
    return ResourceScope((envelope, event))


class AuthorityEnvelopeStore:
    """Read-only envelope contract; administration is intentionally absent."""

    def __init__(self, coordinator: PersistenceCoordinator):
        self._coordinator = coordinator

    def get_envelope(self, authority_envelope_id: str) -> Optional[ImmutableRow]:
        with self._coordinator.transaction() as context:
            return context.read_by_key(
                "authority_envelope",
                {"authority_envelope_id": authority_envelope_id},
                AUTHORITY_ENVELOPE_COLUMNS,
            )

    def get_event(self, event_id: str) -> Optional[ImmutableRow]:
        with self._coordinator.transaction() as context:
            return context.read_by_key(
                "authority_envelope_event",
                {"event_id": event_id},
                AUTHORITY_ENVELOPE_EVENT_COLUMNS,
            )

    def list_events(
        self,
        authority_envelope_id: str,
        *,
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> ImmutablePage:
        with self._coordinator.transaction() as context:
            return context.enumerate(
                "authority_envelope_event",
                (
                    Predicate(
                        "authority_envelope_id",
                        PredicateOperator.EQ,
                        authority_envelope_id,
                    ),
                ),
                AUTHORITY_ENVELOPE_EVENT_COLUMNS,
                limit,
                cursor,
            )

