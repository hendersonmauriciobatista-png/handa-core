"""Pure conversion of Binance-shaped evidence into LIVE domain contracts."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Mapping, Optional, Tuple

from core.execution.live_order_models import (
    ExchangeEvidence,
    ExchangeOrderStatus,
    LiveExecutionResult,
    NormalizedExecutionStatus,
    OrderSide,
    ReconciliationState,
    TradeEffect,
)


class QuoteQtyProvenance(str, Enum):
    EXCHANGE = "EXCHANGE"
    DERIVED_PRICE_TIMES_QTY = "DERIVED_PRICE_TIMES_QTY"


def _decimal_from_raw(
    name: str,
    value: Any,
    *,
    allow_zero: bool = False,
) -> Decimal:
    """Parse an exchange decimal string without rounding or float coercion."""

    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, str) and value.strip():
        try:
            result = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"{name} must be a valid decimal string") from exc
    else:
        raise TypeError(f"{name} must be a Decimal or decimal string")

    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    if result < Decimal("0") or (not allow_zero and result == Decimal("0")):
        raise ValueError(f"{name} must be positive")
    return result


def _optional_decimal_from_raw(name: str, value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    return _decimal_from_raw(name, value, allow_zero=True)


def _required_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _exchange_status(raw_status: Any) -> Optional[ExchangeOrderStatus]:
    if raw_status is None:
        return None
    if not isinstance(raw_status, str):
        raise TypeError("status must be a string")
    try:
        return ExchangeOrderStatus(raw_status)
    except ValueError as exc:
        raise ValueError(f"unsupported exchange status: {raw_status}") from exc


def _freeze_raw(value: Any) -> Any:
    """Create an immutable, lossless structural snapshot of raw evidence."""

    if isinstance(value, Mapping):
        return tuple((key, _freeze_raw(item)) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_raw(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze_raw(item) for item in value))
    return value


@dataclass(frozen=True)
class NormalizedTradeEffect:
    effect: TradeEffect
    quote_qty_provenance: QuoteQtyProvenance

    @property
    def identity(self):
        return self.effect.identity

    @property
    def evidence(self):
        return self.effect.evidence

    @property
    def normalized_status(self):
        return self.effect.normalized_status

    @property
    def reconciliation_state(self):
        return self.effect.reconciliation_state


@dataclass(frozen=True)
class NormalizedOrderEvidence:
    """Result plus individual effects and an immutable raw-evidence snapshot."""

    result: LiveExecutionResult
    trade_effects: Tuple[NormalizedTradeEffect, ...]
    raw_order: Any


def normalize_order_result(
    raw_order: Optional[Mapping[str, Any]],
    *,
    intent_id: str,
    client_order_id: str,
    symbol: str,
    side: OrderSide,
    transport_ambiguous: bool = False,
    submission_rejected: bool = False,
) -> NormalizedOrderEvidence:
    """Normalize an order response without performing reconciliation or effects."""

    if transport_ambiguous and submission_rejected:
        raise ValueError("transport ambiguity cannot be submission rejection")
    if raw_order is not None and not isinstance(raw_order, Mapping):
        raise TypeError("raw_order must be a mapping or None")

    raw_snapshot = _freeze_raw(raw_order) if raw_order is not None else tuple()
    exchange_status = _exchange_status(raw_order.get("status")) if raw_order else None
    exchange_order_id = None
    executed_base_qty = None
    executed_quote_qty = None

    if raw_order:
        if raw_order.get("orderId") is not None:
            exchange_order_id = str(raw_order["orderId"])
        executed_base_qty = _optional_decimal_from_raw(
            "executedQty", raw_order.get("executedQty")
        )
        executed_quote_qty = _optional_decimal_from_raw(
            "cummulativeQuoteQty", raw_order.get("cummulativeQuoteQty")
        )

    if transport_ambiguous:
        normalized_status = NormalizedExecutionStatus.UNKNOWN
        reconciliation_state = ReconciliationState.PENDING
    elif submission_rejected:
        normalized_status = NormalizedExecutionStatus.SUBMISSION_REJECTED
        reconciliation_state = ReconciliationState.RESOLVED
    elif exchange_status is ExchangeOrderStatus.FILLED:
        normalized_status = NormalizedExecutionStatus.FILLED
        reconciliation_state = ReconciliationState.NOT_REQUIRED
    elif exchange_status is ExchangeOrderStatus.PARTIALLY_FILLED:
        normalized_status = NormalizedExecutionStatus.PARTIALLY_FILLED
        reconciliation_state = ReconciliationState.NOT_REQUIRED
    elif exchange_status in (
        ExchangeOrderStatus.CANCELED,
        ExchangeOrderStatus.EXPIRED,
        ExchangeOrderStatus.EXPIRED_IN_MATCH,
    ):
        normalized_status = NormalizedExecutionStatus.CANCELED
        reconciliation_state = ReconciliationState.NOT_REQUIRED
    elif exchange_status is ExchangeOrderStatus.NEW:
        normalized_status = NormalizedExecutionStatus.UNKNOWN
        reconciliation_state = ReconciliationState.PENDING
    elif raw_order and raw_order.get("fills"):
        normalized_status = NormalizedExecutionStatus.PARTIALLY_FILLED
        reconciliation_state = ReconciliationState.PENDING
    else:
        normalized_status = NormalizedExecutionStatus.UNKNOWN
        reconciliation_state = ReconciliationState.PENDING

    result = LiveExecutionResult(
        intent_id=intent_id,
        client_order_id=client_order_id,
        symbol=symbol,
        side=side,
        exchange_status=exchange_status,
        normalized_status=normalized_status,
        reconciliation_state=reconciliation_state,
        exchange_order_id=exchange_order_id,
        executed_base_qty=executed_base_qty,
        executed_quote_qty=executed_quote_qty,
    )
    return NormalizedOrderEvidence(
        result=result,
        trade_effects=normalize_trade_effects(raw_order) if raw_order else tuple(),
        raw_order=raw_snapshot,
    )


def normalize_trade_effects(
    raw_order: Mapping[str, Any],
) -> Tuple[NormalizedTradeEffect, ...]:
    """Normalize every fill independently; never merge distinct trade IDs."""

    if not isinstance(raw_order, Mapping):
        raise TypeError("raw_order must be a mapping")
    symbol = _required_text("symbol", raw_order.get("symbol"))
    exchange_order_id = raw_order.get("orderId")
    if exchange_order_id is None:
        raise ValueError("orderId is required for trade evidence")
    exchange_order_id = str(exchange_order_id)
    exchange_status = _exchange_status(raw_order.get("status"))
    fills = raw_order.get("fills", [])
    if not isinstance(fills, (list, tuple)):
        raise TypeError("fills must be a list or tuple")

    effects = []
    for fill in fills:
        if not isinstance(fill, Mapping):
            raise TypeError("each fill must be a mapping")
        trade_id_value = fill.get("tradeId")
        legacy_id_value = fill.get("id")
        if trade_id_value is not None and legacy_id_value is not None:
            if str(trade_id_value) != str(legacy_id_value):
                raise ValueError("REJECT_AMBIGUOUS_EVIDENCE: tradeId differs from id")
            trade_id = trade_id_value
        else:
            trade_id = (
                trade_id_value
                if trade_id_value is not None
                else legacy_id_value
            )
        if trade_id is None:
            raise ValueError("tradeId is required for trade evidence")
        price = _decimal_from_raw("price", fill.get("price"))
        gross_base_qty = _decimal_from_raw("qty", fill.get("qty"))
        quote_qty = _optional_decimal_from_raw("quoteQty", fill.get("quoteQty"))
        quote_qty_provenance = QuoteQtyProvenance.EXCHANGE
        if quote_qty is None:
            quote_qty = price * gross_base_qty
            quote_qty_provenance = QuoteQtyProvenance.DERIVED_PRICE_TIMES_QTY
        commission_amount = _decimal_from_raw(
            "commission", fill.get("commission", "0"), allow_zero=True
        )
        commission_asset = _required_text(
            "commissionAsset", fill.get("commissionAsset")
        )
        evidence = ExchangeEvidence(
            symbol=symbol,
            exchange_order_id=exchange_order_id,
            exchange_trade_id=str(trade_id),
            price=price,
            gross_base_qty=gross_base_qty,
            quote_qty=quote_qty,
            commission_amount=commission_amount,
            commission_asset=commission_asset,
            exchange_status=exchange_status,
        )
        effects.append(
            NormalizedTradeEffect(
                effect=TradeEffect(
                    evidence=evidence,
                    normalized_status=(
                        NormalizedExecutionStatus.PARTIALLY_FILLED
                        if exchange_status is ExchangeOrderStatus.CANCELED
                        and len(fills) > 0
                        else (
                            NormalizedExecutionStatus.PARTIALLY_FILLED
                            if exchange_status is not ExchangeOrderStatus.FILLED
                            else NormalizedExecutionStatus.FILLED
                        )
                    ),
                    reconciliation_state=ReconciliationState.NOT_REQUIRED,
                ),
                quote_qty_provenance=quote_qty_provenance,
            )
        )
    return tuple(effects)
