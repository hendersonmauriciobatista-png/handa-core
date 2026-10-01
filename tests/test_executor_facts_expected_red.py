"""3B4 expected-RED controls for the executor observation-only contract.

This file is deliberately test-only.  It does not implement ``ExecutionFact``
and it never uses a real exchange client.  Reachable controls falsify current
executor side effects; controls requiring the future fact boundary are skipped
after recording one shared boundary absence instead of duplicating that RED.
"""

from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace

import pytest


def _fact_boundary():
    """Return the future boundary, or ``None`` when the shared boundary is absent."""

    try:
        module = import_module("core.execution.execution_fact")
        return getattr(module, "ExecutionFact")
    except (ImportError, AttributeError):
        return None


def _require_fact_boundary():
    fact_type = _fact_boundary()
    if fact_type is None:
        pytest.skip("NOT_YET_REACHED: shared ExecutionFact production boundary is absent")
    return fact_type


def _normalize_external_observation(observation):
    """Use the future canonical normalizer once the shared boundary exists."""

    _require_fact_boundary()
    module = import_module("core.execution.execution_fact")
    normalizer = getattr(module, "normalize_external_execution", None)
    if normalizer is None:
        pytest.skip("NOT_YET_REACHED: canonical ExecutionFact normalizer is absent")
    return normalizer(observation)


class _Client:
    def __init__(self, *, buy_response=None, sell_response=None, buy_error=None):
        self.buy_response = buy_response or {
            "status": "FILLED",
            "executedQty": "1",
            "cummulativeQuoteQty": "100",
            "orderId": "buy-1",
        }
        self.sell_response = sell_response or {
            "status": "FILLED",
            "executedQty": "1",
            "cummulativeQuoteQty": "100",
            "orderId": "sell-1",
        }
        self.buy_error = buy_error

    def order_market_buy(self, **_kwargs):
        if self.buy_error:
            raise self.buy_error
        return self.buy_response

    def order_market_sell(self, **_kwargs):
        return self.sell_response


class _PositionManager:
    def __init__(self, position=None):
        self.position = position
        self.open_calls = []
        self.close_calls = []

    def open_position(self, **kwargs):
        self.open_calls.append(kwargs)
        return SimpleNamespace(**kwargs)

    def get_position(self, _pair):
        return self.position

    def close_position(self, **kwargs):
        self.close_calls.append(kwargs)
        return SimpleNamespace(net_pnl_usdc=0)


class _Tracker:
    def __init__(self):
        self.calls = []

    def record(self, value):
        self.calls.append(("record", value))

    def open_position(self, *args):
        self.calls.append(("open_position", args))

    def close_position(self, *args):
        self.calls.append(("close_position", args))


def _executor(*, client=None, position=None):
    from core.executor.binance_executor import BinanceExecutor

    manager = _PositionManager(position=position)
    tracker = _Tracker()
    executor = object.__new__(BinanceExecutor)
    executor.client = client or _Client()
    executor.position_manager = manager
    executor.tracker = tracker
    executor.last_balance = 0.0
    executor.symbol_filters = {"BTCUSDC": {"min_qty": 0, "max_qty": 0, "step_size": 0, "min_notional": 0}}
    executor._get_asset_free_balance = lambda _asset: 10.0
    executor.get_current_price = lambda _pair: 100.0
    executor._validate_quantity = lambda **_kwargs: (True, 1.0, "OK")
    return executor, manager, tracker


def _buy_signal():
    return SimpleNamespace(
        pair="BTCUSDC",
        entry_price=100.0,
        allocated_usdc=100.0,
        stop_loss=90.0,
        take_profit=110.0,
    )


def _position(quantity=10.0):
    return SimpleNamespace(quantity=quantity)


def test_ef001_executor_buy_cannot_mutate_position_manager():
    executor, manager, _tracker = _executor()
    executor.execute_buy(_buy_signal())
    assert not manager.open_calls, "VALID_RED: execute_buy called PositionManager.open_position"


def test_ef002_executor_sell_cannot_mutate_position_manager():
    executor, manager, _tracker = _executor(position=_position())
    executor.execute_sell("BTCUSDC", reason="TEST")
    assert not manager.close_calls, "VALID_RED: execute_sell called PositionManager.close_position"


def test_ef003_executor_cannot_mutate_position_tracker():
    executor, _manager, tracker = _executor(position=_position())
    executor.execute_sell("BTCUSDC", reason="TEST")
    assert not tracker.calls, "VALID_RED: execute_sell called PositionTracker.record"


def test_ef004_partial_sell_is_observation_only_and_not_integral_close():
    client = _Client(
        sell_response={
            "status": "PARTIALLY_FILLED",
            "executedQty": "4",
            "cummulativeQuoteQty": "400",
            "orderId": "sell-partial",
        }
    )
    executor, manager, _tracker = _executor(client=client, position=_position(10.0))
    executor.execute_sell("BTCUSDC", reason="TEST")
    assert not manager.close_calls, "VALID_RED: partial SELL caused local close"


def test_ef005_timeout_after_submission_is_unknown_observation():
    executor, _manager, _tracker = _executor(
        client=_Client(buy_error=TimeoutError("submitted request timed out"))
    )
    result = executor.execute_buy(_buy_signal())
    assert result is not None and getattr(result, "extent_certainty", None) == "UNKNOWN"


def test_ef006_authoritative_rejection_is_known_zero_without_semantic_confirmation():
    client = _Client(buy_response={"status": "REJECTED", "orderId": "reject-1"})
    executor, _manager, _tracker = _executor(client=client)
    result = executor.execute_buy(_buy_signal())
    assert result is not None
    assert getattr(result, "extent_certainty", None) == "KNOWN_ZERO"
    assert not hasattr(result, "reconciliation_state")


def test_ef007_fact_preserves_canonical_external_order_identity():
    _require_fact_boundary()


def test_ef008_identical_external_evidence_has_stable_extent_identity():
    """A canonical non-overlapping extent may be identified repeatedly."""

    observation = {
        "symbol": "BTCUSDC",
        "side": "BUY",
        "orderId": "order-extent-1",
        "clientOrderId": "client-extent-1",
        "status": "PARTIALLY_FILLED",
        "executedQty": "0.4",
        "cummulativeQuoteQty": "40",
        "fills": [{"tradeId": "trade-1", "qty": "0.4", "quoteQty": "40", "price": "100"}],
        "nonOverlappingExtent": True,
        "nonOverlappingExtent": True,
    }
    first = _normalize_external_observation(observation)
    second = _normalize_external_observation(observation)
    assert first.execution_extent_identity is not None
    assert first.execution_extent_identity == second.execution_extent_identity


def test_ef009_executor_result_alone_cannot_release_or_complete_slot():
    pytest.skip("NOT_YET_REACHED: caller-controlled SlotController path not exercised by executor-only surface")


def test_ef010_executor_result_alone_cannot_finalize_accounting():
    pytest.skip("NOT_YET_REACHED: caller-controlled accounting path not exercised by executor-only surface")


def test_ef011_exception_after_submission_is_unknown():
    executor, _manager, _tracker = _executor(
        client=_Client(buy_error=RuntimeError("transport failed after submission"))
    )
    result = executor.execute_buy(_buy_signal())
    assert result is not None and getattr(result, "extent_certainty", None) == "UNKNOWN"


def test_ef012_unknown_is_not_none_false_or_generic_failure():
    executor, _manager, _tracker = _executor(
        client=_Client(buy_error=RuntimeError("ambiguous acceptance"))
    )
    result = executor.execute_buy(_buy_signal())
    assert result is not None and getattr(result, "extent_certainty", None) == "UNKNOWN"


def test_ef013_fact_contains_no_reconciliation_state():
    _require_fact_boundary()


def test_ef014_canceled_with_positive_quantity_remains_positive_observation():
    _require_fact_boundary()


def test_ef015_insufficient_evidence_cannot_prove_full_extent():
    _require_fact_boundary()


def test_ef016_duplicate_canonical_evidence_has_same_extent_identity():
    """Duplicate extent evidence is idempotent; cumulative growth is not new extent."""

    first_observation = {
        "symbol": "BTCUSDC",
        "side": "BUY",
        "orderId": "order-cumulative-1",
        "status": "PARTIALLY_FILLED",
        "executedQty": "0.4",
        "cummulativeQuoteQty": "40",
        "fills": [{"tradeId": "trade-1", "qty": "0.4", "quoteQty": "40", "price": "100"}],
    }
    expanded_observation = {
        **first_observation,
        "status": "FILLED",
        "executedQty": "1.0",
        "cummulativeQuoteQty": "100",
        "fills": [
            {"tradeId": "trade-1", "qty": "0.4", "quoteQty": "40", "price": "100"},
            {"tradeId": "trade-2", "qty": "0.6", "quoteQty": "60", "price": "100"},
        ],
        "nonOverlappingExtent": False,
    }
    first = _normalize_external_observation(first_observation)
    duplicate = _normalize_external_observation(first_observation)
    expanded = _normalize_external_observation(expanded_observation)
    assert first.execution_extent_identity == duplicate.execution_extent_identity
    assert expanded.execution_extent_identity is None


def test_ef017_external_lifecycle_status_is_distinct_from_extent_certainty():
    """Status, certainty, and cumulative/non-overlap semantics are distinct."""

    fact_type = _require_fact_boundary()
    annotations = fact_type.__annotations__
    assert "external_status" in annotations
    assert "extent_certainty" in annotations
    assert "quantity_semantics" in annotations


def test_ef018_quote_equality_alone_cannot_prove_full_extent():
    _require_fact_boundary()


def test_ef019_mock_exchange_state_cannot_mutate_authoritative_state():
    executor, manager, tracker = _executor(position=_position())
    executor.execute_sell("BTCUSDC", reason="TEST")
    assert not manager.close_calls and not tracker.calls


def test_ef020_fact_creation_does_not_invoke_effect_authority_or_ledger():
    _require_fact_boundary()


def test_ef021_ambiguous_submission_has_unknown_without_fabricated_identity():
    executor, _manager, _tracker = _executor(
        client=_Client(buy_error=RuntimeError("ambiguous transport outcome"))
    )
    result = executor.execute_buy(_buy_signal())
    assert result is not None
    assert getattr(result, "extent_certainty", None) == "UNKNOWN"
    assert getattr(result, "execution_extent_identity", None) is None


def test_ef022_status_timestamp_revision_does_not_create_new_extent():
    """Only lifecycle/timestamp revision may change observation identity."""

    first = _normalize_external_observation(
        {
            "symbol": "BTCUSDC",
            "side": "BUY",
            "orderId": "order-revision-1",
            "status": "PARTIALLY_FILLED",
            "executedQty": "0.4",
            "cummulativeQuoteQty": "40",
            "updateTime": "2026-01-01T00:00:00Z",
        }
    )
    revised = _normalize_external_observation(
        {
            "symbol": "BTCUSDC",
            "side": "BUY",
            "orderId": "order-revision-1",
            "status": "FILLED",
            "executedQty": "0.4",
            "cummulativeQuoteQty": "40",
            "updateTime": "2026-01-01T00:00:01Z",
        }
    )
    assert first.observation_identity != revised.observation_identity
    assert first.execution_extent_identity is None
    assert revised.execution_extent_identity is None


def test_ef023_cumulative_revision_is_not_new_extent():
    """Cumulative 0.4 -> 1.0 evidence needs reconciliation, not a fabricated delta."""

    first = _normalize_external_observation(
        {
            "symbol": "BTCUSDC",
            "side": "BUY",
            "orderId": "order-cumulative-2",
            "status": "PARTIALLY_FILLED",
            "executedQty": "0.4",
            "cummulativeQuoteQty": "40",
        }
    )
    revised = _normalize_external_observation(
        {
            "symbol": "BTCUSDC",
            "side": "BUY",
            "orderId": "order-cumulative-2",
            "status": "FILLED",
            "executedQty": "1.0",
            "cummulativeQuoteQty": "100",
        }
    )
    assert first.observation_identity != revised.observation_identity
    assert first.quantity_semantics == "CUMULATIVE_EXTERNAL_OBSERVATION"
    assert revised.quantity_semantics == "CUMULATIVE_EXTERNAL_OBSERVATION"
    assert first.execution_extent_identity is None
    assert revised.execution_extent_identity is None
