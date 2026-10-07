"""Canonical, Decimal-safe digests for authority-neutral evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
from enum import Enum
from typing import Any, Mapping


def canonical_decimal(value: Decimal | float | int) -> str:
    """Return one deterministic decimal representation without float authority."""

    if isinstance(value, bool):
        raise TypeError("boolean is not a decimal")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite float cannot be canonicalized")
        value = Decimal(str(value))
    elif isinstance(value, int):
        value = Decimal(value)
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError("value must be a finite Decimal, float, or int")
    normalized = value.normalize()
    if normalized == 0:
        return "0"
    return format(normalized, "f")


def canonical_timestamp(value: datetime) -> str:
    """Normalize timestamps to UTC with a deterministic ISO representation."""

    if not isinstance(value, datetime):
        raise TypeError("timestamp must be datetime")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return canonical_decimal(value)
    if isinstance(value, float):
        return canonical_decimal(value)
    if isinstance(value, datetime):
        return canonical_timestamp(value)
    if isinstance(value, Enum):
        return _canonical_value(value.value)
    if isinstance(value, Mapping):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"unsupported digest value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def market_snapshot_digest(snapshot: Any) -> str:
    fields = (
        "pair", "price", "rsi", "ema_fast", "ema_slow", "volume_ratio",
        "atr", "trend", "momentum", "market_state", "volume_state",
        "market_score", "selection_score", "liquidity_score",
    )
    return sha256_digest({field: getattr(snapshot, field, None) for field in fields})


def strategy_decision_digest(*, symbol: str, reason_codes: tuple[str, ...], confidence: float) -> str:
    return sha256_digest(
        {
            "symbol": symbol,
            "side": "BUY",
            "reason_codes": list(reason_codes),
            "confidence": canonical_decimal(confidence),
        }
    )


def upstream_evidence_digest(
    *,
    source_component: str,
    source_contract_version: str,
    symbol: str,
    side: str,
    reason_codes: tuple[str, ...],
    market_snapshot_digest_value: str,
    strategy_decision_digest_value: str,
    produced_at: datetime,
) -> str:
    return sha256_digest(
        {
            "source_component": source_component,
            "source_contract_version": source_contract_version,
            "symbol": symbol,
            "side": side,
            "reason_codes": list(reason_codes),
            "market_snapshot_digest": market_snapshot_digest_value,
            "strategy_decision_digest": strategy_decision_digest_value,
            "produced_at": produced_at,
        }
    )


def evaluation_request_digest(
    *, intent_id: str, submission_attempt_id: str, upstream_evidence_digest_value: str
) -> str:
    return sha256_digest(
        {
            "intent_id": intent_id,
            "submission_attempt_id": submission_attempt_id,
            "upstream_evidence_digest": upstream_evidence_digest_value,
        }
    )


def intent_semantic_digest(row: Mapping[str, Any]) -> str:
    fields = (
        "intent_id", "venue", "account_scope", "client_order_id", "slot_id",
        "symbol", "side", "requested_quote_amount", "requested_base_qty",
        "policy_context",
    )
    return sha256_digest({field: row[field] for field in fields})


def attempt_semantic_digest(row: Mapping[str, Any]) -> str:
    fields = (
        "attempt_id", "intent_id", "attempt_sequence", "venue",
        "account_scope", "client_order_id", "context_id",
    )
    return sha256_digest({field: row[field] for field in fields})
