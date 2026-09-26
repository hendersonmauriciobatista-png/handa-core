from decimal import Decimal

import pytest

from core.execution.live_order_models import (
    ExchangeEvidence,
    ExchangeOrderStatus,
    LiveExecutionResult,
    LiveOrderIntent,
    NormalizedExecutionStatus,
    OrderSide,
    ReconciliationState,
    TradeEffect,
)


def dec(value: str) -> Decimal:
    return Decimal(value)


def make_evidence(**overrides):
    values = {
        "symbol": "BTCUSDC",
        "exchange_order_id": "order-1",
        "exchange_trade_id": "trade-1",
        "price": dec("100.10"),
        "gross_base_qty": dec("0.1000"),
        "quote_qty": dec("10.010"),
        "commission_amount": dec("0.0001"),
        "commission_asset": "BTC",
        "exchange_status": ExchangeOrderStatus.FILLED,
    }
    values.update(overrides)
    return ExchangeEvidence(**values)


def test_valid_buy_intent_uses_quote_request():
    intent = LiveOrderIntent(
        intent_id="intent-1",
        client_order_id="client-1",
        slot_id="slot-1",
        symbol="BTCUSDC",
        side=OrderSide.BUY,
        requested_quote_amount=dec("10.00"),
    )
    assert intent.requested_quote_amount == dec("10.00")


def test_valid_sell_intent_uses_base_request():
    intent = LiveOrderIntent(
        intent_id="intent-2",
        client_order_id="client-2",
        slot_id="slot-1",
        symbol="BTCUSDC",
        side=OrderSide.SELL,
        requested_base_qty=dec("0.1000"),
    )
    assert intent.requested_base_qty == dec("0.1000")


@pytest.mark.parametrize("field", ["intent_id", "client_order_id", "slot_id", "symbol"])
def test_intent_rejects_missing_identity(field):
    values = {
        "intent_id": "intent-1",
        "client_order_id": "client-1",
        "slot_id": "slot-1",
        "symbol": "BTCUSDC",
        "side": OrderSide.BUY,
        "requested_quote_amount": dec("10"),
    }
    values[field] = ""
    with pytest.raises(ValueError):
        LiveOrderIntent(**values)


def test_trade_effect_identity_and_duplicate_equality():
    first = make_evidence()
    second = make_evidence()
    assert first.identity == second.identity
    assert hash(first.identity) == hash(second.identity)
    assert first.identity.symbol == "BTCUSDC"
    assert first.identity.exchange_order_id == "order-1"
    assert first.identity.exchange_trade_id == "trade-1"


def test_identity_does_not_depend_on_financial_values():
    first = make_evidence(price=dec("100"), gross_base_qty=dec("1"))
    second = make_evidence(price=dec("101"), gross_base_qty=dec("2"))
    assert first.identity == second.identity


@pytest.mark.parametrize("field", ["price", "gross_base_qty", "quote_qty", "commission_amount"])
def test_authoritative_values_require_decimal(field):
    values = {
        "symbol": "BTCUSDC",
        "exchange_order_id": "order-1",
        "exchange_trade_id": "trade-1",
        "price": dec("100"),
        "gross_base_qty": dec("1"),
        "quote_qty": dec("100"),
        "commission_amount": dec("0.1"),
        "commission_asset": "USDC",
    }
    values[field] = 1.0
    with pytest.raises(TypeError):
        ExchangeEvidence(**values)


@pytest.mark.parametrize("asset", ["USDC", "BTC", "BNB"])
def test_commission_asset_is_preserved(asset):
    evidence = make_evidence(commission_asset=asset)
    assert evidence.commission_asset == asset
    assert evidence.commission_amount == dec("0.0001")


def test_exchange_and_normalized_status_are_separate():
    result = LiveExecutionResult(
        intent_id="intent-1",
        client_order_id="client-1",
        symbol="BTCUSDC",
        side=OrderSide.BUY,
        exchange_status=ExchangeOrderStatus.FILLED,
        normalized_status=NormalizedExecutionStatus.FILLED,
        reconciliation_state=ReconciliationState.RESOLVED,
    )
    assert result.exchange_status is ExchangeOrderStatus.FILLED
    assert result.normalized_status is NormalizedExecutionStatus.FILLED
    assert result.reconciliation_state is ReconciliationState.RESOLVED


def test_partial_effect_can_be_confirmed_before_order_is_canceled():
    effect = TradeEffect(
        evidence=make_evidence(exchange_status=ExchangeOrderStatus.CANCELED),
        normalized_status=NormalizedExecutionStatus.PARTIALLY_FILLED,
        reconciliation_state=ReconciliationState.RESOLVED,
    )
    assert effect.normalized_status is NormalizedExecutionStatus.PARTIALLY_FILLED


def test_normalized_execution_can_use_evidence_without_exchange_status():
    result = LiveExecutionResult(
        intent_id="intent-1",
        client_order_id="client-1",
        symbol="BTCUSDC",
        side=OrderSide.BUY,
        exchange_status=None,
        normalized_status=NormalizedExecutionStatus.FILLED,
        reconciliation_state=ReconciliationState.RESOLVED,
    )
    assert result.exchange_status is None
    assert result.normalized_status is NormalizedExecutionStatus.FILLED


def test_unknown_requires_pending_reconciliation():
    result = LiveExecutionResult(
        intent_id="intent-1",
        client_order_id="client-1",
        symbol="BTCUSDC",
        side=OrderSide.BUY,
        exchange_status=None,
        normalized_status=NormalizedExecutionStatus.UNKNOWN,
        reconciliation_state=ReconciliationState.PENDING,
    )
    assert result.normalized_status is NormalizedExecutionStatus.UNKNOWN


def test_partially_filled_requires_exchange_partial_status():
    effect = TradeEffect(
        evidence=make_evidence(exchange_status=ExchangeOrderStatus.PARTIALLY_FILLED),
        normalized_status=NormalizedExecutionStatus.PARTIALLY_FILLED,
        reconciliation_state=ReconciliationState.RESOLVED,
    )
    assert effect.identity.exchange_trade_id == "trade-1"


def test_trade_effect_rejects_unknown_as_resolved():
    with pytest.raises(ValueError):
        TradeEffect(
            evidence=make_evidence(exchange_status=None),
            normalized_status=NormalizedExecutionStatus.UNKNOWN,
            reconciliation_state=ReconciliationState.RESOLVED,
        )


def test_trade_effect_rejects_no_effect_with_confirmed_execution():
    with pytest.raises(ValueError):
        TradeEffect(
            evidence=make_evidence(exchange_status=ExchangeOrderStatus.FILLED),
            normalized_status=NormalizedExecutionStatus.NO_EFFECT_CONFIRMED,
            reconciliation_state=ReconciliationState.RESOLVED,
        )


def test_trade_effect_rejects_submission_rejection_with_confirmed_execution():
    with pytest.raises(ValueError):
        TradeEffect(
            evidence=make_evidence(exchange_status=ExchangeOrderStatus.FILLED),
            normalized_status=NormalizedExecutionStatus.SUBMISSION_REJECTED,
            reconciliation_state=ReconciliationState.RESOLVED,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("requested_quote_amount", dec("0")),
        ("requested_quote_amount", dec("-1")),
    ],
)
def test_buy_intent_rejects_zero_or_negative_sizing(field, value):
    with pytest.raises(ValueError):
        LiveOrderIntent(
            intent_id="intent-1",
            client_order_id="client-1",
            slot_id="slot-1",
            symbol="BTCUSDC",
            side=OrderSide.BUY,
            **{field: value},
        )


@pytest.mark.parametrize("value", [dec("0"), dec("-1")])
def test_sell_intent_rejects_zero_or_negative_sizing(value):
    with pytest.raises(ValueError):
        LiveOrderIntent(
            intent_id="intent-1",
            client_order_id="client-1",
            slot_id="slot-1",
            symbol="BTCUSDC",
            side=OrderSide.SELL,
            requested_base_qty=value,
        )


def test_intent_rejects_incompatible_simultaneous_sizing():
    with pytest.raises(ValueError):
        LiveOrderIntent(
            intent_id="intent-1",
            client_order_id="client-1",
            slot_id="slot-1",
            symbol="BTCUSDC",
            side=OrderSide.BUY,
            requested_quote_amount=dec("10"),
            requested_base_qty=dec("0.1"),
        )

    with pytest.raises(ValueError):
        LiveOrderIntent(
            intent_id="intent-1",
            client_order_id="client-1",
            slot_id="slot-1",
            symbol="BTCUSDC",
            side=OrderSide.SELL,
            requested_quote_amount=dec("10"),
            requested_base_qty=dec("0.1"),
        )


def test_execution_result_preserves_exact_decimal_values():
    result = LiveExecutionResult(
        intent_id="intent-1",
        client_order_id="client-1",
        symbol="BTCUSDC",
        side=OrderSide.BUY,
        exchange_status=ExchangeOrderStatus.FILLED,
        normalized_status=NormalizedExecutionStatus.FILLED,
        reconciliation_state=ReconciliationState.RESOLVED,
        executed_base_qty=dec("0.10000000"),
        executed_quote_qty=dec("10.01000000"),
    )
    assert result.executed_base_qty == dec("0.10000000")
    assert result.executed_quote_qty == dec("10.01000000")


@pytest.mark.parametrize(
    "model,field",
    [
        (
            LiveOrderIntent(
                intent_id="intent-1",
                client_order_id="client-1",
                slot_id="slot-1",
                symbol="BTCUSDC",
                side=OrderSide.BUY,
                requested_quote_amount=dec("10"),
            ),
            "intent_id",
        ),
        (make_evidence(), "price"),
        (
            LiveExecutionResult(
                intent_id="intent-1",
                client_order_id="client-1",
                symbol="BTCUSDC",
                side=OrderSide.BUY,
                exchange_status=None,
                normalized_status=NormalizedExecutionStatus.UNKNOWN,
                reconciliation_state=ReconciliationState.PENDING,
            ),
            "intent_id",
        ),
    ],
)
def test_models_reject_mutation(model, field):
    with pytest.raises((AttributeError, TypeError)):
        setattr(model, field, "changed")


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "exchange_status": ExchangeOrderStatus.FILLED,
            "normalized_status": NormalizedExecutionStatus.NO_EFFECT_CONFIRMED,
            "reconciliation_state": ReconciliationState.RESOLVED,
        },
        {
            "exchange_status": None,
            "normalized_status": NormalizedExecutionStatus.UNKNOWN,
            "reconciliation_state": ReconciliationState.RESOLVED,
        },
        {
            "exchange_status": ExchangeOrderStatus.FILLED,
            "normalized_status": NormalizedExecutionStatus.SUBMISSION_REJECTED,
            "reconciliation_state": ReconciliationState.RESOLVED,
        },
    ],
)
def test_invalid_state_combinations_are_rejected(kwargs):
    with pytest.raises(ValueError):
        LiveExecutionResult(
            intent_id="intent-1",
            client_order_id="client-1",
            symbol="BTCUSDC",
            side=OrderSide.BUY,
            **kwargs,
        )


def test_exchange_rejected_is_not_a_supported_exchange_enum():
    assert "REJECTED" not in {status.value for status in ExchangeOrderStatus}
