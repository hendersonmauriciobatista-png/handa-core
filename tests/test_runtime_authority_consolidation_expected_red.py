"""Expected-RED controls for runtime authority consolidation.

These tests intentionally expose legacy authority mutations.  They use only
local doubles and never construct a real exchange client or submit an order.
"""

from __future__ import annotations

from pathlib import Path
import importlib
import sys
import types
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


class _Manager:
    def __init__(self):
        self.open_calls = []
        self.close_calls = []

    def get_position(self, **_kwargs):
        return None

    def open_position(self, **kwargs):
        self.open_calls.append(kwargs)

    def close_position(self, **kwargs):
        self.close_calls.append(kwargs)

    def has_position(self, **_kwargs):
        return False


class _Client:
    def __init__(self):
        self.calls = []

    def get_account(self):
        self.calls.append(("get_account", None))
        return {"balances": [{"asset": "BTC", "free": "1.25"}]}

    def get_symbol_ticker(self, *, symbol):
        self.calls.append(("get_symbol_ticker", symbol))
        return {"price": "100"}

    def order_market_buy(self, **kwargs):
        self.calls.append(("order_market_buy", kwargs))
        raise AssertionError("network submission boundary must not be reached")

    def order_market_sell(self, **kwargs):
        self.calls.append(("order_market_sell", kwargs))
        raise AssertionError("network submission boundary must not be reached")

    def create_order(self, **kwargs):
        self.calls.append(("create_order", kwargs))
        raise AssertionError("network submission boundary must not be reached")


def _buy_signal():
    return SimpleNamespace(
        pair="BTCUSDC",
        entry_price=100.0,
        allocated_usdc=10.0,
        stop_loss=90.0,
        take_profit=110.0,
    )


def _slot(slot_id=1, state="READY"):
    from core.slot import Slot

    slot = Slot(slot_id)
    slot.pair = "BTCUSDC"
    slot._state = state
    slot.pending_buy_signal = _buy_signal()
    return slot


def _controller(executor, slot, manager=None):
    from core.slot_controller import SlotController

    controller = object.__new__(SlotController)
    controller.client = object()
    controller.executor = executor
    controller.position_manager = manager or _Manager()
    controller._slots = {slot.slot_id: slot}
    controller.symbol_execution_lock = {"BTCUSDC"}
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
    controller.trade_history = []
    controller.profit_today = 0.0
    controller.profit_total = 0.0
    controller.balance = 0.0
    controller.peak_balance = 0.0
    controller._register_loss_cooldown = lambda *_args, **_kwargs: None
    controller._register_win_recovery = lambda *_args, **_kwargs: None
    controller._register_dynamic_reentry_control = lambda *_args, **_kwargs: None
    controller._cleanup_successful_sell = lambda **_kwargs: None
    return controller


class _LegacyExecutor:
    def __init__(self, *, buy_result=None, sell_result=None, buy_error=None):
        self.buy_result = buy_result
        self.sell_result = sell_result
        self.buy_error = buy_error

    def execute_buy(self, _signal):
        if self.buy_error is not None:
            raise self.buy_error
        return self.buy_result

    def execute_sell(self, _pair, _reason):
        return self.sell_result

    def get_balance(self, _asset):
        return 100.0


def _legacy_sell_result():
    return SimpleNamespace(
        pair="BTCUSDC",
        entry_price=100.0,
        exit_price=101.0,
        quantity=1.0,
        net_pnl_usdc=1.0,
    )


def _import_main_without_ui_dependency(monkeypatch):
    app_layout = types.ModuleType("interface.desktop.app_layout")
    app_layout.HAControlPanel = object
    monkeypatch.setitem(sys.modules, "interface.desktop.app_layout", app_layout)
    sys.modules.pop("main", None)
    return importlib.import_module("main")


def test_a01_legacy_buy_result_cannot_open_or_advance_slot():
    slot = _slot(state="READY")
    manager = _Manager()
    legacy_result = SimpleNamespace(entry_price=100.0, quantity=1.0)
    controller = _controller(
        _LegacyExecutor(buy_result=legacy_result),
        slot,
        manager,
    )
    quantity_before = slot.quantity

    controller._execute_buy(slot)

    assert not manager.open_calls
    assert slot.state == "READY"
    assert slot.entry_price is None
    assert slot.quantity == quantity_before


def test_a02_legacy_sell_result_cannot_close_or_finalize_accounting():
    slot = _slot(state="RUNNING")
    manager = _Manager()
    controller = _controller(
        _LegacyExecutor(sell_result=_legacy_sell_result()),
        slot,
        manager,
    )

    controller._execute_sell(slot, reason="TEST")

    assert not manager.close_calls
    assert not controller.trade_history
    assert controller.profit_today == 0.0
    assert controller.profit_total == 0.0


@pytest.mark.parametrize(
    "kind",
    ["buy_none", "buy_exception", "buy_legacy", "sell_none", "sell_legacy"],
)
def test_a03_non_execution_fact_cannot_cleanup_release_or_reset(kind):
    if kind == "buy_none":
        executor = _LegacyExecutor(buy_result=None)
        slot = _slot(state="READY")
        controller = _controller(executor, slot)
        controller._execute_buy(slot)
    elif kind == "buy_exception":
        executor = _LegacyExecutor(buy_error=RuntimeError("legacy failure"))
        slot = _slot(state="READY")
        controller = _controller(executor, slot)
        controller._execute_buy(slot)
    elif kind == "buy_legacy":
        executor = _LegacyExecutor(
            buy_result=SimpleNamespace(entry_price=100.0, quantity=1.0)
        )
        slot = _slot(state="READY")
        controller = _controller(executor, slot)
        controller._execute_buy(slot)
    elif kind == "sell_none":
        executor = _LegacyExecutor(sell_result=None)
        slot = _slot(state="RUNNING")
        controller = _controller(executor, slot)
        controller._execute_sell(slot, reason="TEST")
    else:
        executor = _LegacyExecutor(sell_result=_legacy_sell_result())
        slot = _slot(state="RUNNING")
        controller = _controller(executor, slot)
        controller._execute_sell(slot, reason="TEST")

    assert slot.state in {"READY", "RUNNING"}
    assert slot.pending_buy_signal is not None
    assert "BTCUSDC" in controller.symbol_execution_lock


def test_a04_startup_sync_cannot_open_local_position(monkeypatch):
    main = _import_main_without_ui_dependency(monkeypatch)

    client = _Client()
    manager = _Manager()
    slot = _slot(state="IDLE")
    slot_controller = SimpleNamespace(get_slots=lambda: {1: slot})

    main.sync_positions_with_binance(client, slot_controller, manager)

    assert not manager.open_calls


def test_a05_startup_sync_cannot_mutate_slot_state(monkeypatch):
    main = _import_main_without_ui_dependency(monkeypatch)

    client = _Client()
    manager = _Manager()
    slot = _slot(state="IDLE")
    before = (slot.pair, slot.entry_price, slot.quantity, slot.state)
    slot_controller = SimpleNamespace(get_slots=lambda: {1: slot})

    main.sync_positions_with_binance(client, slot_controller, manager)

    after = (slot.pair, slot.entry_price, slot.quantity, slot.state)
    assert after == before


def test_a06_startup_sync_is_observational_and_never_submits(monkeypatch):
    main = _import_main_without_ui_dependency(monkeypatch)

    client = _Client()
    manager = _Manager()
    slot = _slot(state="IDLE")
    slot_controller = SimpleNamespace(get_slots=lambda: {1: slot})

    main.sync_positions_with_binance(client, slot_controller, manager)

    assert [name for name, _value in client.calls] == [
        "get_account",
        "get_symbol_ticker",
    ]
    assert not manager.open_calls
    assert not manager.close_calls


def test_a07_canonical_runtime_identity_is_preserved():
    launcher = (ROOT / "run_handa.py").read_text(encoding="utf-8")
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "from main import main" in launcher
    assert "from core.slot_controller import SlotController" in main_source
    assert "from core.executor.binance_executor import BinanceExecutor" in main_source
    assert "def build_executor" in main_source


def test_a08_canonical_runtime_does_not_depend_on_alternate_paths():
    canonical_source = "\n".join(
        (
            (ROOT / "run_handa.py").read_text(encoding="utf-8"),
            (ROOT / "main.py").read_text(encoding="utf-8"),
        )
    )
    forbidden = (
        "interface.runner.app",
        "run_live",
        "core.run_core",
        "h_a.core.executor",
        "h_a.core.exchange_adapter",
    )
    assert not any(path in canonical_source for path in forbidden)


def test_a09_non_execution_fact_cannot_mutate_slot_quantity():
    outcomes = (
        ("none", _LegacyExecutor(buy_result=None), 7.5),
        ("false", _LegacyExecutor(buy_result=False), 7.5),
        ("dict", _LegacyExecutor(buy_result={"status": "FILLED"}), 7.5),
        (
            "legacy",
            _LegacyExecutor(
                buy_result=SimpleNamespace(entry_price=100.0, quantity=1.0)
            ),
            7.5,
        ),
        ("unexpected_truthy", _LegacyExecutor(buy_result=object()), 7.5),
        ("exception", _LegacyExecutor(buy_error=RuntimeError("legacy failure")), 7.5),
        ("uninitialized_quantity", _LegacyExecutor(buy_result=None), None),
    )
    violations = []

    for name, executor, initial_quantity in outcomes:
        slot = _slot(state="READY")
        slot.quantity = initial_quantity
        controller = _controller(executor, slot)
        quantity_before = slot.quantity

        controller._execute_buy(slot)

        if slot.quantity != quantity_before:
            violations.append((name, quantity_before, slot.quantity))

    assert not violations, (
        "non-ExecutionFact result mutated slot.quantity: "
        f"{violations}"
    )
