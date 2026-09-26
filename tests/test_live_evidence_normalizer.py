from decimal import Decimal

import pytest

from core.execution.live_evidence_normalizer import (
    QuoteQtyProvenance,
    normalize_order_result,
    normalize_trade_effects,
)
from core.execution.live_order_models import (
    ExchangeOrderStatus,
    NormalizedExecutionStatus,
    OrderSide,
    ReconciliationState,
)


def order_with_fills():
    return {
        "symbol": "BTCUSDC",
        "orderId": 42,
        "status": "FILLED",
        "executedQty": "0.00300000",
        "cummulativeQuoteQty": "90.12345000",
        "fills": [
            {
                "tradeId": 1001,
                "price": "30041.15000000",
                "qty": "0.00123000",
                "quoteQty": "36.95061450",
                "commission": "0.00000123",
                "commissionAsset": "BTC",
            },
            {
                "tradeId": 1002,
                "price": "30057.00500000",
                "qty": "0.00177000",
                "quoteQty": "53.17283550",
                "commission": "0.05317284",
                "commissionAsset": "USDC",
            },
        ],
    }


def normalize(raw, **kwargs):
    defaults = {
        "intent_id": "intent-1",
        "client_order_id": "client-1",
        "symbol": "BTCUSDC",
        "side": OrderSide.BUY,
    }
    defaults.update(kwargs)
    return normalize_order_result(raw, **defaults)


def test_single_fill_preserves_exact_decimal_values():
    raw = order_with_fills()
    raw["fills"] = [raw["fills"][0]]
    normalized_order = normalize(raw)
    normalized = normalized_order.trade_effects
    evidence = normalized[0].evidence
    assert evidence.price == Decimal("30041.15000000")
    assert evidence.gross_base_qty == Decimal("0.00123000")
    assert evidence.quote_qty == Decimal("36.95061450")
    assert evidence.commission_amount == Decimal("0.00000123")
    assert normalized[0].quote_qty_provenance is QuoteQtyProvenance.EXCHANGE
    raw_fill = dict(dict(normalized_order.raw_order)["fills"][0])
    assert "quoteQty" in raw_fill
    assert raw_fill["quoteQty"] == "36.95061450"


def test_missing_quote_qty_is_explicitly_derived():
    raw = order_with_fills()
    fill = dict(raw["fills"][0])
    fill.pop("quoteQty")
    raw["fills"] = [fill]
    normalized_order = normalize(raw)
    normalized = normalized_order.trade_effects[0]
    assert normalized.quote_qty_provenance is QuoteQtyProvenance.DERIVED_PRICE_TIMES_QTY
    assert normalized.evidence.quote_qty == Decimal("36.9506145000000000")
    raw_fill = dict(dict(normalized_order.raw_order)["fills"][0])
    assert "quoteQty" not in raw_fill


def test_multiple_fills_remain_distinct_effects():
    effects = normalize_trade_effects(order_with_fills())
    assert len(effects) == 2
    assert effects[0].identity.exchange_trade_id == "1001"
    assert effects[1].identity.exchange_trade_id == "1002"
    assert effects[0].identity != effects[1].identity


@pytest.mark.parametrize("field", ["price", "qty", "quoteQty", "commission"])
def test_float_authoritative_input_is_rejected(field):
    raw = order_with_fills()
    raw["fills"] = [dict(raw["fills"][0], **{field: 1.0})]
    with pytest.raises(TypeError):
        normalize_trade_effects(raw)


def test_malformed_decimal_is_rejected():
    raw = order_with_fills()
    raw["fills"] = [dict(raw["fills"][0], price="not-a-decimal")]
    with pytest.raises(ValueError):
        normalize_trade_effects(raw)


@pytest.mark.parametrize("field", ["price", "qty"])
def test_negative_domain_values_are_rejected(field):
    raw = order_with_fills()
    raw["fills"] = [dict(raw["fills"][0], **{field: "-1"})]
    with pytest.raises(ValueError):
        normalize_trade_effects(raw)


@pytest.mark.parametrize("asset", ["USDC", "BTC", "BNB"])
def test_commission_asset_is_preserved_without_conversion(asset):
    raw = order_with_fills()
    raw["fills"] = [dict(raw["fills"][0], commissionAsset=asset)]
    effect = normalize_trade_effects(raw)[0]
    assert effect.evidence.commission_asset == asset


def test_zero_commission_is_preserved():
    raw = order_with_fills()
    raw["fills"] = [dict(raw["fills"][0], commission="0.00000000")]
    effect = normalize_trade_effects(raw)[0]
    assert effect.evidence.commission_amount == Decimal("0.00000000")


def test_partial_canceled_order_preserves_partial_effect():
    raw = order_with_fills()
    raw["status"] = "CANCELED"
    raw["fills"] = [raw["fills"][0]]
    normalized = normalize(raw)
    assert normalized.result.exchange_status is ExchangeOrderStatus.CANCELED
    assert normalized.result.normalized_status is NormalizedExecutionStatus.CANCELED
    assert normalized.trade_effects[0].identity.exchange_trade_id == "1001"
    assert normalized.trade_effects[0].normalized_status is NormalizedExecutionStatus.PARTIALLY_FILLED


def test_missing_exchange_status_with_fills_remains_separate_and_pending():
    raw = order_with_fills()
    raw.pop("status")
    normalized = normalize(raw)
    assert normalized.result.exchange_status is None
    assert normalized.result.normalized_status is NormalizedExecutionStatus.PARTIALLY_FILLED
    assert normalized.result.reconciliation_state is ReconciliationState.PENDING


def test_ambiguous_transport_becomes_unknown_not_rejected():
    normalized = normalize(None, transport_ambiguous=True)
    assert normalized.result.normalized_status is NormalizedExecutionStatus.UNKNOWN
    assert normalized.result.reconciliation_state is ReconciliationState.PENDING


def test_submission_rejection_is_explicit_and_not_transport_ambiguity():
    normalized = normalize({}, submission_rejected=True)
    assert normalized.result.normalized_status is NormalizedExecutionStatus.SUBMISSION_REJECTED
    assert normalized.result.reconciliation_state is ReconciliationState.RESOLVED


def test_raw_evidence_is_preserved_as_immutable_snapshot():
    raw = order_with_fills()
    normalized = normalize(raw)
    assert ("symbol", "BTCUSDC") in normalized.raw_order
    assert any(key == "fills" for key, _ in normalized.raw_order)
    snapshot = dict(normalized.raw_order)
    first_fill = dict(snapshot["fills"][0])
    assert first_fill["price"] == "30041.15000000"
    raw["fills"][0]["price"] = "0"
    assert dict(dict(normalized.raw_order)["fills"][0])["price"] == "30041.15000000"


def test_no_silent_rounding_or_quantization():
    raw = order_with_fills()
    raw["fills"] = [dict(raw["fills"][0], price="1.234567891234")]
    effect = normalize_trade_effects(raw)[0]
    assert effect.evidence.price == Decimal("1.234567891234")


def test_trade_id_is_required_and_not_invented():
    raw = order_with_fills()
    raw["fills"] = [dict(raw["fills"][0])]
    raw["fills"][0].pop("tradeId")
    with pytest.raises(ValueError):
        normalize_trade_effects(raw)


@pytest.mark.parametrize(
    "fill_update,expected",
    [
        ({"tradeId": 1001}, "1001"),
        ({"id": 1001}, "1001"),
        ({"tradeId": 1001, "id": 1001}, "1001"),
    ],
)
def test_trade_id_alias_resolution_is_explicit(fill_update, expected):
    raw = order_with_fills()
    fill = dict(raw["fills"][0])
    fill.pop("tradeId", None)
    fill.pop("id", None)
    fill.update(fill_update)
    raw["fills"] = [fill]
    assert normalize_trade_effects(raw)[0].identity.exchange_trade_id == expected


def test_conflicting_trade_id_aliases_are_rejected():
    raw = order_with_fills()
    raw["fills"] = [dict(raw["fills"][0], id=9999)]
    with pytest.raises(ValueError, match="REJECT_AMBIGUOUS_EVIDENCE"):
        normalize_trade_effects(raw)


def test_duplicate_trade_identity_is_detectable_without_deduplication():
    raw = order_with_fills()
    duplicate = dict(raw["fills"][0])
    raw["fills"] = [raw["fills"][0], duplicate]
    effects = normalize_trade_effects(raw)
    assert len(effects) == 2
    assert effects[0].identity == effects[1].identity


def test_conflicting_ambiguity_flags_are_rejected():
    with pytest.raises(ValueError):
        normalize({}, transport_ambiguous=True, submission_rejected=True)


@pytest.mark.parametrize("value", [1, Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_or_integer_authoritative_input_is_rejected(value):
    raw = order_with_fills()
    raw["fills"] = [dict(raw["fills"][0], price=value)]
    with pytest.raises((TypeError, ValueError)):
        normalize_trade_effects(raw)
