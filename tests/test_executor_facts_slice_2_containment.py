"""Expected-RED falsifiers for the Slice 2 facts-only containment boundary.

This file is intentionally test-only.  It uses stubs at exchange boundaries
and does not submit real orders, change production state, or repair callers.
"""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest

from core.execution.execution_fact import (
    ExecutionFact,
    ExternalOrderStatus,
    ExtentCertainty,
    QuantitySemantics,
)


class _Client:
    def __init__(self, *, buy_response=None, sell_response=None, buy_error=None):
        self.buy_response = buy_response or {
            "status": "FILLED",
            "executedQty": "1",
            "cummulativeQuoteQty": "100",
            "orderId": "buy-1",
        }
        self.sell_response = sell_response or {
            "status": "PARTIALLY_FILLED",
            "executedQty": "4",
            "cummulativeQuoteQty": "400",
            "orderId": "sell-1",
        }
        self.buy_error = buy_error

    def order_market_buy(self, **_kwargs):
        if self.buy_error:
            raise self.buy_error
        return self.buy_response

    def order_market_sell(self, **_kwargs):
        return self.sell_response

    def create_order(self, **_kwargs):
        if self.buy_error:
            raise self.buy_error
        return self.buy_response

    def get_asset_balance(self, **_kwargs):
        return {"free": "1"}

    def get_symbol_info(self, **_kwargs):
        return {"filters": [{"filterType": "LOT_SIZE", "stepSize": "0.001"}]}


class _Manager:
    def __init__(self, position=None):
        self.position = position or SimpleNamespace(quantity=10.0)
        self.open_calls = []
        self.close_calls = []

    def open_position(self, **kwargs):
        self.open_calls.append(kwargs)
        return SimpleNamespace(**kwargs)

    def get_position(self, _pair=None, **_kwargs):
        return self.position

    def close_position(self, **kwargs):
        self.close_calls.append(kwargs)
        return SimpleNamespace(net_pnl_usdc=0)


class _Tracker:
    def __init__(self):
        self.calls = []

    def open_position(self, *args):
        self.calls.append(("open_position", args))

    def close_position(self, *args):
        self.calls.append(("close_position", args))

    def record(self, value):
        self.calls.append(("record", value))


def _binance_executor(*, client=None, manager=None, tracker=None):
    from core.executor.binance_executor import BinanceExecutor

    manager = manager or _Manager()
    tracker = tracker or _Tracker()
    executor = object.__new__(BinanceExecutor)
    executor.client = client or _Client()
    executor.position_manager = manager
    executor.tracker = tracker
    executor.last_balance = 0.0
    executor.symbol_filters = {
        "BTCUSDC": {
            "min_qty": 0.0,
            "max_qty": 0.0,
            "step_size": 0.0,
            "min_notional": 0.0,
        }
    }
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


def _fact(*, certainty=ExtentCertainty.KNOWN_FULL, status=ExternalOrderStatus.FILLED):
    return ExecutionFact(
        observation_identity="observation-1",
        external_order_id="order-1",
        client_order_id="client-1",
        symbol="BTCUSDC",
        side="BUY",
        external_status=status,
        executed_base_qty=1,
        executed_quote_qty=100,
        quantity_semantics=QuantitySemantics.CUMULATIVE_EXTERNAL_OBSERVATION,
        average_price_or_wap=100,
        fill_digest=None,
        exchange_timestamp="2026-01-01T00:00:00Z",
        raw_source_reference="test-source",
        execution_extent_identity=None,
        extent_certainty=certainty,
    )


def test_s2_001_binance_buy_does_not_mutate_position_manager():
    executor, manager, _tracker = _binance_executor()
    executor.execute_buy(_buy_signal())
    assert not manager.open_calls, "VALID_RED: Binance BUY called PositionManager.open_position"


def test_s2_002_binance_partial_sell_does_not_close_or_mutate_position():
    manager = _Manager(position=SimpleNamespace(quantity=10.0))
    client = _Client(
        sell_response={
            "status": "PARTIALLY_FILLED",
            "executedQty": "4",
            "cummulativeQuoteQty": "400",
            "orderId": "sell-partial",
        }
    )
    executor, manager, tracker = _binance_executor(client=client, manager=manager)
    executor.execute_sell("BTCUSDC", reason="TEST")
    assert not manager.close_calls
    assert manager.position.quantity == 10.0
    assert not tracker.calls


def _bare_mock(executor_type):
    executor = object.__new__(executor_type)
    executor.client = None
    executor.position_manager = _Manager()
    executor.tracker = _Tracker()
    executor.balance_usdc = 1000.0
    executor.initial_balance = 1000.0
    executor.positions = {}
    executor.live_shadow = None
    executor._save_state = lambda: None
    return executor


def test_s2_003_core_mock_does_not_bypass_h_and_a_authority():
    from core.executor.mock_executor import MockExecutor

    executor = _bare_mock(MockExecutor)
    executor.execute_buy(_buy_signal())
    assert not executor.position_manager.open_calls
    assert not executor.tracker.calls
    assert executor.positions, "simulated exchange state is permitted"


def test_s2_004_alternate_mock_does_not_bypass_h_and_a_authority():
    from executor.mock_executor import MockExecutor

    executor = _bare_mock(MockExecutor)
    executor.execute_buy(_buy_signal())
    assert not executor.position_manager.open_calls
    assert not executor.tracker.calls
    assert executor.positions, "simulated exchange state is permitted"


def test_s2_005_executor_live_normalizes_all_external_outcomes_to_facts():
    from executor.executor_live import ExecutorLive

    clients = [
        _Client(buy_response={"status": "FILLED", "executedQty": "1", "orderId": "filled-1"}),
        _Client(buy_response={"status": "PARTIALLY_FILLED", "executedQty": "0.4", "orderId": "partial-1"}),
        _Client(buy_response={"status": "REJECTED", "executedQty": "0", "orderId": "rejected-1"}),
        _Client(buy_error=TimeoutError("timeout")),
        _Client(buy_error=RuntimeError("post-submit exception")),
        _Client(buy_error=RuntimeError("ambiguous response")),
    ]
    results = []
    for client in clients:
        executor = object.__new__(ExecutorLive)
        executor._client = client
        executor.exchange = "BINANCE_SPOT"
        executor.notifier = None
        results.append(executor.place_market_buy_quote("BTCUSDC", 100))
    assert all(isinstance(result, ExecutionFact) for result in results)


def _bare_controller(executor, slot):
    from core.slot_controller import SlotController

    controller = object.__new__(SlotController)
    controller.client = object()
    controller.executor = executor
    controller.position_manager = _Manager()
    controller._slots = {slot.slot_id: slot}
    controller.symbol_execution_lock = set()
    controller.lc1_adapter = None
    controller.alo = None
    controller._mqii_capital_multiplier = lambda: 1.0
    controller._get_setup_quality_multiplier = lambda *_args: 1.0
    controller._normalize_symbol = lambda value: value
    controller._is_pair_blocked = lambda _value: False
    controller._is_rejected_symbol_blocked = lambda _value: False
    controller._block_rejected_symbol = lambda *_args, **_kwargs: None
    controller._unblock_rejected_symbol = lambda *_args, **_kwargs: None
    controller._last_buy_ts = 0.0
    return controller


def test_s2_006_slot_buy_fact_is_contained_without_advancing_state():
    class FactExecutor:
        def execute_buy(self, _signal):
            return _fact()

    from core.slot import Slot

    slot = Slot(1)
    slot.pair = "BTCUSDC"
    slot._state = "READY"
    slot.pending_buy_signal = _buy_signal()
    controller = _bare_controller(FactExecutor(), slot)
    cleanup_calls = []
    controller._cleanup_failed_buy = lambda **kwargs: cleanup_calls.append(kwargs)
    controller._execute_buy(slot)
    assert not cleanup_calls
    assert slot.state == "READY"
    assert getattr(controller, "_contained_execution_facts", {}).get(slot.slot_id) is not None


def test_s2_007_slot_sell_fact_does_not_close_release_or_finish():
    class FactExecutor:
        def execute_sell(self, _pair, _reason):
            return _fact(certainty=ExtentCertainty.KNOWN_PARTIAL, status=ExternalOrderStatus.PARTIALLY_FILLED)

    from core.slot import Slot

    slot = Slot(1)
    slot.pair = "BTCUSDC"
    slot._state = "RUNNING"
    controller = _bare_controller(FactExecutor(), slot)
    controller.trade_history = []
    controller.profit_today = 0.0
    controller.profit_total = 0.0
    controller._execute_sell(slot, reason="TEST")
    assert slot.state == "RUNNING"
    assert not controller.trade_history
    assert getattr(controller, "_contained_execution_facts", {}).get(slot.slot_id) is not None


def test_s2_008_unknown_fact_survives_slot_controller_containment():
    class FactExecutor:
        def execute_sell(self, _pair, _reason):
            return _fact(certainty=ExtentCertainty.UNKNOWN, status=None)

    from core.slot import Slot

    slot = Slot(1)
    slot.pair = "BTCUSDC"
    slot._state = "RUNNING"
    controller = _bare_controller(FactExecutor(), slot)
    controller.trade_history = []
    controller.profit_today = 0.0
    controller.profit_total = 0.0
    controller._execute_sell(slot, reason="TEST")
    retained = getattr(controller, "_contained_execution_facts", {}).get(slot.slot_id)
    assert retained is not None
    assert retained.extent_certainty is ExtentCertainty.UNKNOWN
    assert slot.state == "RUNNING"
    assert not controller.trade_history


def test_s2_009_successful_fact_does_not_finalize_accounting():
    class FactExecutor:
        def execute_sell(self, _pair, _reason):
            return _fact()

    from core.slot import Slot

    slot = Slot(1)
    slot.pair = "BTCUSDC"
    slot._state = "RUNNING"
    controller = _bare_controller(FactExecutor(), slot)
    controller.trade_history = []
    controller.profit_today = 0.0
    controller.profit_total = 0.0
    controller._execute_sell(slot, reason="TEST")
    assert not controller.trade_history
    assert controller.profit_today == 0.0
    assert controller.profit_total == 0.0


def test_s2_010_runner_does_not_auto_submit_follow_up_sell_from_fact():
    mock_module = importlib.import_module("executor.mock_executor")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(mock_module, "ExecutorMock", mock_module.MockExecutor, raising=False)
    monkeypatch.setenv("LIVE_ENABLED", "true")
    sys.modules.pop("interface.runner.app", None)
    try:
        app_module = importlib.import_module("interface.runner.app")

        class FakeLive:
            def __init__(self):
                self.buy_calls = []
                self.sell_calls = []

            def place_market_buy_quote(self, symbol, quote_amount):
                self.buy_calls.append((symbol, quote_amount))
                return _fact()

            def place_market_sell_all(self, symbol):
                self.sell_calls.append(symbol)
                return _fact()

        fake_live = FakeLive()
        runner = app_module.AppRunner()
        runner.ctx.mode = "LIVE"
        runner.ctx.wallet_provider = SimpleNamespace(
            get_usdc_balance=lambda: {"free": 100.0}
        )
        runner.ctx.executor_live = fake_live
        runner.ctx.auto_loop = SimpleNamespace(stop=lambda: None)
        runner.ctx.policy = SimpleNamespace(block_live=lambda: None)

        result = runner.run_live_test_10_usdc()
        assert fake_live.buy_calls == [("BTCUSDC", 10)]
        assert fake_live.sell_calls == []
        assert isinstance(result, ExecutionFact)
    finally:
        monkeypatch.undo()
        sys.modules.pop("interface.runner.app", None)


def test_s2_011_runner_unknown_is_contained_without_follow_up():
    mock_module = importlib.import_module("executor.mock_executor")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(mock_module, "ExecutorMock", mock_module.MockExecutor, raising=False)
    monkeypatch.setenv("LIVE_ENABLED", "true")
    sys.modules.pop("interface.runner.app", None)
    try:
        app_module = importlib.import_module("interface.runner.app")

        class FakeLive:
            def __init__(self):
                self.sell_calls = []

            def place_market_buy_quote(self, symbol=None, quote_amount=None):
                return _fact(
                    certainty=ExtentCertainty.UNKNOWN,
                    status=None,
                )

            def place_market_sell_all(self, symbol):
                self.sell_calls.append(symbol)
                return _fact()

        fake_live = FakeLive()
        runner = app_module.AppRunner()
        runner.ctx.mode = "LIVE"
        runner.ctx.wallet_provider = SimpleNamespace(
            get_usdc_balance=lambda: {"free": 100.0}
        )
        runner.ctx.executor_live = fake_live
        runner.ctx.auto_loop = SimpleNamespace(stop=lambda: None)
        runner.ctx.policy = SimpleNamespace(block_live=lambda: None)

        result = runner.run_live_test_10_usdc()
        assert fake_live.sell_calls == []
        assert isinstance(result, ExecutionFact)
        assert result.extent_certainty is ExtentCertainty.UNKNOWN
        assert result.execution_extent_identity is None
    finally:
        monkeypatch.undo()
        sys.modules.pop("interface.runner.app", None)


def test_s2_012_runner_import_compatibility_is_resolved_in_real_boundary():
    sys.modules.pop("interface.runner.app", None)
    app_module = importlib.import_module("interface.runner.app")
    mock_module = importlib.import_module("executor.mock_executor")

    assert app_module.ExecutorMock is mock_module.MockExecutor
    assert isinstance(app_module.ExecutorMock(initial_balance=1000.0), mock_module.MockExecutor)


def test_s2_013_fact_containment_does_not_invoke_effect_authorities():
    source_files = [
        "core/executor/binance_executor.py",
        "core/executor/mock_executor.py",
        "executor/mock_executor.py",
        "executor/executor_live.py",
        "core/slot_controller.py",
        "interface/runner/app.py",
    ]
    forbidden = ("PositionEffectAuthority", "EffectApplicationLedger")
    for path in source_files:
        source = open(path, encoding="utf-8").read()
        assert not any(name in source for name in forbidden)


def test_s2_014_initial_external_submission_gate_is_out_of_scope():
    assert "EXTERNAL_INITIAL_SUBMISSION_GATE" == "EXTERNAL_INITIAL_SUBMISSION_GATE"
