"""Read-only persistence contract for current operational authority state."""

from __future__ import annotations

from typing import Optional

from core.persistence.persistence_coordinator import PersistenceCoordinator
from core.persistence.transaction_context import (
    ImmutableRow,
    ResourceScope,
    ResourceSpec,
)


LIVE_SCHEMA = "handa_live"
STATE_COLUMNS = (
    "state_id",
    "operational_mode",
    "active_authority_envelope_id",
    "global_safety_epoch",
    "runtime_generation",
    "current_version",
    "last_event_id",
    "changed_by",
    "change_reason",
    "updated_at",
)


def operational_authority_state_resource_scope() -> ResourceScope:
    """Return the read-only singleton state scope."""

    state = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="operational_authority_state",
        readable_columns=frozenset(STATE_COLUMNS),
        writable_columns=frozenset(),
        key_columns=frozenset({"state_id"}),
        ordering_columns=("state_id",),
    )
    return ResourceScope((state,))


class OperationalAuthorityStateStore:
    """Read-only current-state contract; mutation belongs to a future boundary."""

    def __init__(self, coordinator: PersistenceCoordinator):
        self._coordinator = coordinator

    def get_current_state(self) -> Optional[ImmutableRow]:
        with self._coordinator.transaction() as context:
            return context.read_by_key(
                "operational_authority_state",
                {"state_id": True},
                STATE_COLUMNS,
            )

