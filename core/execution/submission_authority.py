"""Bounded mechanics for consuming a durable submission authorization.

This module deliberately contains no authority issuer or policy decision.  A
successful claim is evidence that an already-authorized row was consumed once.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Optional


class ClaimDisposition(str, Enum):
    CLAIMED = "CLAIMED"
    CLAIM_REPLAY = "CLAIM_REPLAY"
    ALREADY_CLAIMED = "ALREADY_CLAIMED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    NOT_CURRENT = "NOT_CURRENT"
    CANNOT_CLAIM = "CANNOT_CLAIM"


def canonical_decimal(value: Any) -> Optional[str]:
    """Return an exact, float-free decimal representation for fingerprints."""

    if value is None:
        return None
    if isinstance(value, float):
        raise TypeError("float values are not valid semantic amounts")
    try:
        decimal = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise TypeError("amount must be an exact decimal value") from exc
    if not decimal.is_finite():
        raise ValueError("amount must be finite")
    normalized = format(decimal.normalize(), "f")
    if normalized in {"-0", "-0.0"}:
        return "0"
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def submission_fingerprint(
    *,
    intent_id: str,
    submission_attempt_id: str,
    client_order_id: str,
    venue: str,
    account_scope: str,
    symbol: str,
    side: str,
    requested_quote_amount: Any = None,
    requested_base_qty: Any = None,
) -> str:
    """Hash the complete bound submission semantics deterministically."""

    payload = {
        "account_scope": account_scope,
        "client_order_id": client_order_id,
        "intent_id": intent_id,
        "requested_base_qty": canonical_decimal(requested_base_qty),
        "requested_quote_amount": canonical_decimal(requested_quote_amount),
        "side": side,
        "submission_attempt_id": submission_attempt_id,
        "symbol": symbol,
        "venue": venue,
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class SubmissionClaimRequest:
    submission_authorization_id: str


@dataclass(frozen=True)
class ClaimResult:
    disposition: ClaimDisposition
    capability: Optional["ClaimedSubmissionCapability"] = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.disposition in {ClaimDisposition.CLAIMED, ClaimDisposition.CLAIM_REPLAY}:
            if self.capability is None:
                raise ValueError("successful claim results require a capability")
        elif self.capability is not None:
            raise ValueError("non-successful claim results cannot carry capability")


_CAPABILITY_MARKER = object()


class ClaimedSubmissionCapability:
    """Immutable evidence issued only after a committed durable claim."""

    __slots__ = (
        "submission_authorization_id", "intent_id", "submission_attempt_id",
        "client_order_id", "venue", "account_scope", "symbol", "side",
        "requested_quote_amount", "requested_base_qty", "submission_fingerprint",
        "issuer_id", "authority_reference_id", "authority_contract_version",
        "claimed_by", "claimed_at", "claimed_version", "_marker",
    )

    def __init__(
        self,
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
        submission_fingerprint: str,
        issuer_id: str,
        authority_reference_id: str,
        authority_contract_version: str,
        claimed_by: str,
        claimed_at: datetime,
        claimed_version: int,
        _marker: object = None,
    ) -> None:
        if _marker is not _CAPABILITY_MARKER:
            raise ValueError("capability can only be issued after a durable claim")
        values = locals().copy()
        values.pop("self")
        values.pop("_marker")
        for name, value in values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_marker", _CAPABILITY_MARKER)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("claimed submission capability is immutable")


def is_valid_claimed_submission_capability(value: Any) -> bool:
    """Validate the opaque marker used by a future transport boundary."""

    return (
        isinstance(value, ClaimedSubmissionCapability)
        and getattr(value, "_marker", None) is _CAPABILITY_MARKER
    )


def _issue_claimed_capability(record: Any) -> ClaimedSubmissionCapability:
    return ClaimedSubmissionCapability(
        submission_authorization_id=record["submission_authorization_id"],
        intent_id=record["intent_id"],
        submission_attempt_id=record["submission_attempt_id"],
        client_order_id=record["client_order_id"],
        venue=record["venue"],
        account_scope=record["account_scope"],
        symbol=record["symbol"],
        side=record["side"],
        requested_quote_amount=record["requested_quote_amount"],
        requested_base_qty=record["requested_base_qty"],
        submission_fingerprint=record["submission_fingerprint"],
        issuer_id=record["issuer_id"],
        authority_reference_id=record["authority_reference_id"],
        authority_contract_version=record["authority_contract_version"],
        claimed_by=record["claimed_by"],
        claimed_at=record["claimed_at"],
        claimed_version=record["current_version"],
        _marker=_CAPABILITY_MARKER,
    )
