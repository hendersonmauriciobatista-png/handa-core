"""Compatibility facade for the governed durable submission claim."""

from __future__ import annotations

from typing import Optional

from core.execution.submission_authority import (
    ClaimDisposition,
    ClaimResult,
    SubmissionClaimRequest,
)
from core.persistence.persistence_coordinator import PersistenceCoordinator
from core.persistence.submission_authorization_issuer_store import AUTHORIZATION_COLUMNS
from core.persistence.submission_claim_store import (
    SubmissionClaimPersistence,
    submission_claim_resource_scope,
)
from core.persistence.transaction_context import ImmutableRow, ResourceScope


def submission_authorization_resource_scope() -> ResourceScope:
    """Keep the legacy name while exposing only the governed claim scope."""

    return submission_claim_resource_scope()


class SubmissionAuthorizationStore:
    """Legacy facade; the claimer is the sole semantic claim authority."""

    def __init__(self, coordinator: PersistenceCoordinator):
        self._coordinator = coordinator

    def get_authorization(self, submission_authorization_id: str) -> Optional[ImmutableRow]:
        with self._coordinator.transaction() as context:
            return context.read_by_key(
                "submission_authorization",
                {"submission_authorization_id": submission_authorization_id},
                AUTHORIZATION_COLUMNS,
            )

    def claim_authorization(self, request: SubmissionClaimRequest) -> ClaimResult:
        from core.execution.submission_authorization_claimer import SubmissionAuthorizationClaimer

        if not isinstance(request, SubmissionClaimRequest):
            return ClaimResult(ClaimDisposition.CANNOT_CLAIM, reason="INVALID_CLAIM_REQUEST")
        return SubmissionAuthorizationClaimer(
            SubmissionClaimPersistence(self._coordinator)
        ).claim(request.submission_authorization_id)
