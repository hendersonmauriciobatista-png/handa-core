"""Persistence boundary for one-time durable submission authorization claims."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from core.execution.submission_authority import (
    ClaimDisposition,
    ClaimResult,
    SubmissionClaimRequest,
    _issue_claimed_capability,
    submission_fingerprint,
)
from core.persistence.persistence_coordinator import PersistenceCoordinator
from core.persistence.transaction_context import (
    ImmutableRow,
    ResourceScope,
    ResourceSpec,
    VersionConflict,
)


LIVE_SCHEMA = "handa_live"
AUTHORIZATION_COLUMNS = (
    "submission_authorization_id", "intent_id", "submission_attempt_id",
    "client_order_id", "venue", "account_scope", "symbol", "side",
    "requested_quote_amount", "requested_base_qty", "authority_reference_id",
    "issuer_id", "authority_contract_version", "authorization_sequence",
    "submission_fingerprint", "authorization_state", "current_version",
    "claimed_by", "claimed_at", "created_at",
)
INTENT_COLUMNS = (
    "intent_id", "venue", "account_scope", "client_order_id", "symbol",
    "side", "requested_quote_amount", "requested_base_qty",
)
ATTEMPT_COLUMNS = (
    "attempt_id", "intent_id", "venue", "account_scope", "client_order_id",
)


def submission_authorization_resource_scope() -> ResourceScope:
    """Return the least resource scope needed to validate and claim."""

    authorization = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="submission_authorization",
        readable_columns=frozenset(AUTHORIZATION_COLUMNS),
        writable_columns=frozenset({
            "authorization_state", "current_version", "claimed_by", "claimed_at",
        }),
        key_columns=frozenset({"submission_authorization_id"}),
        ordering_columns=("submission_authorization_id",),
        version_column="current_version",
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
    return ResourceScope((authorization, intent, attempt))


class SubmissionAuthorizationStore:
    """Read and consume authority; deliberately cannot create AUTHORIZED rows."""

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
        claimed_row: Optional[ImmutableRow] = None
        disposition = ClaimDisposition.CONFLICT

        try:
            with self._coordinator.transaction() as context:
                authorization = context.read_by_key(
                    "submission_authorization",
                    {"submission_authorization_id": request.submission_authorization_id},
                    AUTHORIZATION_COLUMNS,
                )
                if authorization is None:
                    disposition = ClaimDisposition.NOT_FOUND
                elif authorization["authorization_state"] != "AUTHORIZED":
                    disposition = ClaimDisposition.ALREADY_CLAIMED
                elif not self._matches_request(context, authorization, request):
                    disposition = ClaimDisposition.CONFLICT
                elif authorization["current_version"] != request.expected_version:
                    disposition = ClaimDisposition.CONFLICT
                else:
                    try:
                        claimed_row = context.update_if_version(
                            "submission_authorization",
                            {"submission_authorization_id": request.submission_authorization_id},
                            request.expected_version,
                            {
                                "authorization_state": "CLAIMED",
                                "claimed_by": request.claimant_id,
                                "claimed_at": None,
                            },
                            AUTHORIZATION_COLUMNS,
                        )
                    except VersionConflict:
                        # The competing transaction owns the only retryable fact.
                        # Do not read its new version and do not retry this claim.
                        disposition = ClaimDisposition.ALREADY_CLAIMED
                    else:
                        disposition = ClaimDisposition.CLAIMED
        except Exception:
            # Coordinator rollback is the atomicity boundary.  No capability can
            # escape on a persistence failure.
            raise

        if disposition is ClaimDisposition.CLAIMED:
            return ClaimResult(disposition, _issue_claimed_capability(claimed_row))
        return ClaimResult(disposition)

    @staticmethod
    def _matches_request(context: Any, authorization: Mapping[str, Any], request: SubmissionClaimRequest) -> bool:
        intent = context.read_by_key("order_intent", {"intent_id": authorization["intent_id"]}, INTENT_COLUMNS)
        attempt = context.read_by_key("submission_attempt", {"attempt_id": authorization["submission_attempt_id"]}, ATTEMPT_COLUMNS)
        if intent is None or attempt is None:
            return False
        if attempt["intent_id"] != authorization["intent_id"]:
            return False

        fields = (
            "intent_id", "submission_attempt_id", "client_order_id", "venue",
            "account_scope", "symbol", "side",
        )
        for field in fields:
            if authorization[field] != request.__dict__[field]:
                return False
        if (
            authorization["requested_quote_amount"] != request.requested_quote_amount
            or authorization["requested_base_qty"] != request.requested_base_qty
        ):
            return False
        for field in ("client_order_id", "venue", "account_scope"):
            if intent[field] != authorization[field] or attempt[field] != authorization[field]:
                return False
        for field in ("symbol", "side", "requested_quote_amount", "requested_base_qty"):
            if intent[field] != authorization[field]:
                return False
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
        return (
            authorization["submission_fingerprint"] == expected_fingerprint
            and request.submission_fingerprint == expected_fingerprint
        )
