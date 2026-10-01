"""Immutable, observation-only execution facts.

This module deliberately has no dependencies on position, slot, accounting,
reconciliation, or effect-application authorities.  External order quantities
are cumulative observations by default; an applicable extent identity is
created only when the external evidence explicitly proves non-overlap.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Mapping, Optional


class ExternalOrderStatus(str, Enum):
    PENDING_NEW = "PENDING_NEW"
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    PENDING_CANCEL = "PENDING_CANCEL"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    EXPIRED_IN_MATCH = "EXPIRED_IN_MATCH"
    REJECTED = "REJECTED"
    UNKNOWN_EXTERNAL_STATUS = "UNKNOWN_EXTERNAL_STATUS"


class ExtentCertainty(str, Enum):
    KNOWN_ZERO = "KNOWN_ZERO"
    KNOWN_PARTIAL = "KNOWN_PARTIAL"
    KNOWN_FULL = "KNOWN_FULL"
    UNKNOWN = "UNKNOWN"


class QuantitySemantics(str, Enum):
    CUMULATIVE_EXTERNAL_OBSERVATION = "CUMULATIVE_EXTERNAL_OBSERVATION"
    NON_OVERLAPPING_EXTENT = "NON_OVERLAPPING_EXTENT"


@dataclass(frozen=True, slots=True)
class ExecutionFact:
    observation_identity: Optional[str]

    external_order_id: Optional[str]
    client_order_id: Optional[str]
    symbol: str
    side: str

    external_status: Optional[ExternalOrderStatus]

    executed_base_qty: Decimal
    executed_quote_qty: Decimal
    quantity_semantics: QuantitySemantics

    average_price_or_wap: Optional[Decimal]

    fill_digest: Optional[str]
    exchange_timestamp: Optional[str]
    raw_source_reference: Optional[str]

    execution_extent_identity: Optional[str]
    extent_certainty: ExtentCertainty


def _decimal(value: Any, *, default: Decimal = Decimal("0")) -> Decimal:
    if value is None or value == "":
        return default
    if isinstance(value, Decimal):
        result = value
    else:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(f"invalid decimal value: {value!r}") from exc
    if result < 0:
        raise ValueError("execution quantities cannot be negative")
    return result


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f") if value else "0"


def _canonical(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, set):
        return sorted(_canonical(item) for item in value)
    return value


def _digest(value: Any) -> str:
    payload = json.dumps(
        _canonical(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _first(raw: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in raw and raw[name] is not None:
            return raw[name]
    return None


def _status(value: Any) -> Optional[ExternalOrderStatus]:
    if value is None:
        return None
    if isinstance(value, ExternalOrderStatus):
        return value
    try:
        return ExternalOrderStatus(str(value).upper())
    except ValueError:
        return ExternalOrderStatus.UNKNOWN_EXTERNAL_STATUS


def _fills(raw: Mapping[str, Any]) -> list[Any]:
    fills = _first(raw, "fills", "tradeFills", "trades")
    if fills is None:
        return []
    if not isinstance(fills, (list, tuple)):
        raise TypeError("fills must be a list or tuple")
    return list(fills)


def _is_ambiguous(raw: Mapping[str, Any]) -> bool:
    return bool(
        raw.get("timeout")
        or raw.get("transport_ambiguous")
        or raw.get("ambiguous_response")
        or raw.get("submission_ambiguous")
        or raw.get("transport_exception")
    )


def _proves_non_overlapping_extent(raw: Mapping[str, Any], fills: list[Any]) -> bool:
    explicit = _first(
        raw,
        "nonOverlappingExtent",
        "non_overlapping_extent",
        "deltaScoped",
        "delta_scoped",
        "providerGuaranteedNonCumulative",
        "provider_guaranteed_non_cumulative",
    )
    if explicit is True:
        return True
    scope = _first(raw, "extentScope", "extent_scope")
    if isinstance(scope, str) and scope.upper() in {"DELTA", "SINGLE_FILL", "SINGLE_TRADE"}:
        return True
    return bool(len(fills) == 1 and _first(fills[0], "tradeId", "trade_id", "fillId", "fill_id") is not None and raw.get("singleFill") is True)


def _extent_identity(
    raw: Mapping[str, Any],
    *,
    fills: list[Any],
    symbol: str,
    side: str,
    order_id: Optional[str],
    client_order_id: Optional[str],
) -> Optional[str]:
    if not _proves_non_overlapping_extent(raw, fills):
        return None

    external_extent_reference = _first(
        raw, "externalExtentReference", "external_extent_reference"
    )
    if external_extent_reference is not None:
        extent_evidence = {
            "external_extent_reference": str(external_extent_reference),
            "symbol": symbol,
            "side": side,
            "external_order_id": order_id,
            "client_order_id": client_order_id,
        }
    elif fills:
        extent_evidence = {
            "symbol": symbol,
            "side": side,
            "external_order_id": order_id,
            "client_order_id": client_order_id,
            "fills": fills,
        }
    else:
        return None
    return _digest(extent_evidence)


def _extent_certainty(
    status: Optional[ExternalOrderStatus],
    *,
    executed_base_qty: Decimal,
    raw: Mapping[str, Any],
    quantity_semantics: QuantitySemantics,
) -> ExtentCertainty:
    if status is ExternalOrderStatus.REJECTED:
        return ExtentCertainty.KNOWN_ZERO if executed_base_qty == 0 else ExtentCertainty.KNOWN_PARTIAL

    if status is ExternalOrderStatus.PARTIALLY_FILLED:
        return ExtentCertainty.KNOWN_PARTIAL if executed_base_qty > 0 else ExtentCertainty.UNKNOWN

    if status in (
        ExternalOrderStatus.CANCELED,
        ExternalOrderStatus.EXPIRED,
        ExternalOrderStatus.EXPIRED_IN_MATCH,
    ):
        return ExtentCertainty.KNOWN_PARTIAL if executed_base_qty > 0 else ExtentCertainty.UNKNOWN

    if status is ExternalOrderStatus.FILLED:
        full_proof = _first(
            raw,
            "fullExtentProven",
            "full_extent_proven",
            "orderSpecificFullExtentProven",
            "order_specific_full_extent_proven",
        )
        if full_proof is True and executed_base_qty > 0:
            return ExtentCertainty.KNOWN_FULL
        return ExtentCertainty.UNKNOWN

    if quantity_semantics is QuantitySemantics.NON_OVERLAPPING_EXTENT and executed_base_qty > 0:
        return ExtentCertainty.KNOWN_PARTIAL
    return ExtentCertainty.UNKNOWN


def normalize_external_execution(
    observation: Optional[Mapping[str, Any]] = None,
    *,
    raw_order: Optional[Mapping[str, Any]] = None,
    **overrides: Any,
) -> ExecutionFact:
    """Normalize one external observation without reconciliation or effects."""

    if observation is not None and raw_order is not None:
        raise TypeError("provide observation or raw_order, not both")
    source = raw_order if raw_order is not None else observation
    if source is None:
        source = {}
    if not isinstance(source, Mapping):
        raise TypeError("observation must be a mapping or None")

    raw = dict(source)
    raw.update(overrides)

    symbol = str(_first(raw, "symbol") or "")
    side = str(_first(raw, "side") or "")
    if not symbol.strip() or not side.strip():
        raise ValueError("symbol and side are required")

    order_id_value = _first(raw, "orderId", "external_order_id", "exchange_order_id")
    client_id_value = _first(raw, "clientOrderId", "client_order_id")
    order_id = str(order_id_value) if order_id_value is not None else None
    client_order_id = str(client_id_value) if client_id_value is not None else None

    status = _status(_first(raw, "status", "external_status"))
    base_qty = _decimal(_first(raw, "executedQty", "executed_base_qty"))
    quote_qty = _decimal(
        _first(raw, "cummulativeQuoteQty", "cumulativeQuoteQty", "executed_quote_qty")
    )
    average = _first(raw, "averagePrice", "avgPrice", "avg_price", "weightedAveragePrice", "average_price_or_wap")
    average_price = _decimal(average) if average is not None else None
    fills = _fills(raw)
    fill_digest = _digest(fills) if fills else None
    exchange_timestamp_value = _first(
        raw, "exchangeTimestamp", "exchange_timestamp", "updateTime", "transactTime"
    )
    exchange_timestamp = str(exchange_timestamp_value) if exchange_timestamp_value is not None else None
    raw_source_reference_value = _first(raw, "rawSourceReference", "raw_source_reference", "sourceReference")
    raw_source_reference = str(raw_source_reference_value) if raw_source_reference_value is not None else None

    quantity_semantics = (
        QuantitySemantics.NON_OVERLAPPING_EXTENT
        if _proves_non_overlapping_extent(raw, fills)
        else QuantitySemantics.CUMULATIVE_EXTERNAL_OBSERVATION
    )

    if _is_ambiguous(raw):
        status = None
        certainty = ExtentCertainty.UNKNOWN
        extent_identity = None
        observation_identity = None
    else:
        extent_identity = _extent_identity(
            raw,
            fills=fills,
            symbol=symbol,
            side=side,
            order_id=order_id,
            client_order_id=client_order_id,
        )
        certainty = _extent_certainty(
            status,
            executed_base_qty=base_qty,
            raw=raw,
            quantity_semantics=quantity_semantics,
        )
        observation_identity = _digest(
            {
                "symbol": symbol,
                "side": side,
                "external_order_id": order_id,
                "client_order_id": client_order_id,
                "external_status": status,
                "executed_base_qty": base_qty,
                "executed_quote_qty": quote_qty,
                "average_price_or_wap": average_price,
                "fill_digest": fill_digest,
                "exchange_timestamp": exchange_timestamp,
                "raw_source_reference": raw_source_reference,
            }
        )

    return ExecutionFact(
        observation_identity=observation_identity,
        external_order_id=order_id,
        client_order_id=client_order_id,
        symbol=symbol,
        side=side,
        external_status=status,
        executed_base_qty=base_qty,
        executed_quote_qty=quote_qty,
        quantity_semantics=quantity_semantics,
        average_price_or_wap=average_price,
        fill_digest=fill_digest,
        exchange_timestamp=exchange_timestamp,
        raw_source_reference=raw_source_reference,
        execution_extent_identity=extent_identity,
        extent_certainty=certainty,
    )


__all__ = [
    "ExecutionFact",
    "ExternalOrderStatus",
    "ExtentCertainty",
    "QuantitySemantics",
    "normalize_external_execution",
]
