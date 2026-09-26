"""Immutable domain contracts for governed LIVE order execution.

This module intentionally has no runtime, persistence, Binance, or PositionManager
dependencies.  Financial values are required to arrive as ``Decimal`` instances;
the models never coerce floats or strings into authoritative values.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ExchangeOrderStatus(str, Enum):
    """Statuses emitted by the exchange order domain.

    ``REJECTED`` is deliberately absent.  H&A submission rejection is a
    normalized result, not an assumed Binance exchange status.
    """

    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    EXPIRED_IN_MATCH = "EXPIRED_IN_MATCH"


class NormalizedExecutionStatus(str, Enum):
    SUBMISSION_REJECTED = "SUBMISSION_REJECTED"
    UNKNOWN = "UNKNOWN"
    NO_EFFECT_CONFIRMED = "NO_EFFECT_CONFIRMED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"


class ReconciliationState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    BLOCKED = "BLOCKED"


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _required_decimal(name: str, value: Decimal, *, positive: bool = True) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal")
    if positive and value <= Decimal("0"):
        raise ValueError(f"{name} must be greater than zero")
    return value


def _optional_decimal(name: str, value: Optional[Decimal]) -> Optional[Decimal]:
    if value is None:
        return None
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal or None")
    if value < Decimal("0"):
        raise ValueError(f"{name} must not be negative")
    return value


@dataclass(frozen=True)
class TradeEffectIdentity:
    symbol: str
    exchange_order_id: str
    exchange_trade_id: str

    def __post_init__(self) -> None:
        _required_text("symbol", self.symbol)
        _required_text("exchange_order_id", self.exchange_order_id)
        _required_text("exchange_trade_id", self.exchange_trade_id)


@dataclass(frozen=True)
class LiveOrderIntent:
    intent_id: str
    client_order_id: str
    slot_id: str
    symbol: str
    side: OrderSide
    requested_quote_amount: Optional[Decimal] = None
    requested_base_qty: Optional[Decimal] = None
    policy_context: str = ""

    def __post_init__(self) -> None:
        _required_text("intent_id", self.intent_id)
        _required_text("client_order_id", self.client_order_id)
        _required_text("slot_id", self.slot_id)
        _required_text("symbol", self.symbol)
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be OrderSide")

        quote = self.requested_quote_amount
        base = self.requested_base_qty
        if self.side is OrderSide.BUY:
            _required_decimal("requested_quote_amount", quote)
            if base is not None:
                raise ValueError("BUY intent cannot contain requested_base_qty")
        else:
            _required_decimal("requested_base_qty", base)
            if quote is not None:
                raise ValueError("SELL intent cannot contain requested_quote_amount")


@dataclass(frozen=True)
class ExchangeEvidence:
    symbol: str
    exchange_order_id: str
    exchange_trade_id: str
    price: Decimal
    gross_base_qty: Decimal
    quote_qty: Decimal
    commission_amount: Decimal
    commission_asset: str
    exchange_status: Optional[ExchangeOrderStatus] = None

    def __post_init__(self) -> None:
        identity = TradeEffectIdentity(
            self.symbol, self.exchange_order_id, self.exchange_trade_id
        )
        _required_decimal("price", self.price)
        _required_decimal("gross_base_qty", self.gross_base_qty)
        _required_decimal("quote_qty", self.quote_qty, positive=False)
        _required_decimal("commission_amount", self.commission_amount, positive=False)
        _required_text("commission_asset", self.commission_asset)
        if self.exchange_status is not None and not isinstance(
            self.exchange_status, ExchangeOrderStatus
        ):
            raise TypeError("exchange_status must be ExchangeOrderStatus or None")
        object.__setattr__(self, "_identity", identity)

    @property
    def identity(self) -> TradeEffectIdentity:
        return self._identity


@dataclass(frozen=True)
class TradeEffect:
    evidence: ExchangeEvidence
    normalized_status: NormalizedExecutionStatus
    reconciliation_state: ReconciliationState

    @property
    def identity(self) -> TradeEffectIdentity:
        return self.evidence.identity

    def __post_init__(self) -> None:
        if not isinstance(self.normalized_status, NormalizedExecutionStatus):
            raise TypeError("normalized_status must be NormalizedExecutionStatus")
        if not isinstance(self.reconciliation_state, ReconciliationState):
            raise TypeError("reconciliation_state must be ReconciliationState")
        _validate_state_combination(
            self.evidence.exchange_status,
            self.normalized_status,
            self.reconciliation_state,
        )


@dataclass(frozen=True)
class LiveExecutionResult:
    intent_id: str
    client_order_id: str
    symbol: str
    side: OrderSide
    exchange_status: Optional[ExchangeOrderStatus]
    normalized_status: NormalizedExecutionStatus
    reconciliation_state: ReconciliationState
    exchange_order_id: Optional[str] = None
    executed_base_qty: Optional[Decimal] = None
    executed_quote_qty: Optional[Decimal] = None

    def __post_init__(self) -> None:
        _required_text("intent_id", self.intent_id)
        _required_text("client_order_id", self.client_order_id)
        _required_text("symbol", self.symbol)
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be OrderSide")
        if self.exchange_status is not None and not isinstance(
            self.exchange_status, ExchangeOrderStatus
        ):
            raise TypeError("exchange_status must be ExchangeOrderStatus or None")
        if not isinstance(self.normalized_status, NormalizedExecutionStatus):
            raise TypeError("normalized_status must be NormalizedExecutionStatus")
        if not isinstance(self.reconciliation_state, ReconciliationState):
            raise TypeError("reconciliation_state must be ReconciliationState")
        if self.exchange_order_id is not None:
            _required_text("exchange_order_id", self.exchange_order_id)
        _optional_decimal("executed_base_qty", self.executed_base_qty)
        _optional_decimal("executed_quote_qty", self.executed_quote_qty)
        _validate_state_combination(
            self.exchange_status,
            self.normalized_status,
            self.reconciliation_state,
        )


def _validate_state_combination(
    exchange_status: Optional[ExchangeOrderStatus],
    normalized_status: NormalizedExecutionStatus,
    reconciliation_state: ReconciliationState,
) -> None:
    if normalized_status is NormalizedExecutionStatus.UNKNOWN and reconciliation_state not in (
        ReconciliationState.PENDING,
        ReconciliationState.BLOCKED,
    ):
        raise ValueError("UNKNOWN requires PENDING or BLOCKED reconciliation")

    if normalized_status is NormalizedExecutionStatus.NO_EFFECT_CONFIRMED:
        if reconciliation_state is not ReconciliationState.RESOLVED:
            raise ValueError("NO_EFFECT_CONFIRMED requires RESOLVED reconciliation")
        if exchange_status in (
            ExchangeOrderStatus.FILLED,
            ExchangeOrderStatus.PARTIALLY_FILLED,
        ):
            raise ValueError("confirmed exchange execution cannot be NO_EFFECT_CONFIRMED")

    if normalized_status is NormalizedExecutionStatus.SUBMISSION_REJECTED and exchange_status in (
        ExchangeOrderStatus.FILLED,
        ExchangeOrderStatus.PARTIALLY_FILLED,
    ):
        raise ValueError("submission rejection cannot include confirmed execution")
