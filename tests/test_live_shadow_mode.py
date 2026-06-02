from types import SimpleNamespace

import pytest

from core.executor.live_shadow import LiveShadowSimulator
from core.executor.mock_executor import MockExecutor


class FakeTickerClient:
    def __init__(self, price: float):
        self.price = float(price)
        self.orders_created = []

    def get_symbol_ticker(self, symbol: str):
        return {"symbol": symbol, "price": str(self.price)}

    def create_order(self, *args, **kwargs):
        self.orders_created.append((args, kwargs))
        raise AssertionError("Real order path must not be called")


class ControlledMockExecutor(MockExecutor):
    def _load_state(self):
        self.positions = {}

    def _save_state(self):
        self.saved = True

    def _persist_state_to_git(self):
        raise AssertionError("Git persistence must not run in live shadow test")


class RecordingLiveShadowSimulator(LiveShadowSimulator):
    def __init__(self):
        super().__init__(
            enabled=True,
            fee_pct=0.10,
            slippage_pct=0.05,
            latency_ms=500,
        )
        self.buy_telemetry = None
        self.sell_telemetry = None

    def record_buy(self, *args, **kwargs):
        self.buy_telemetry = super().record_buy(*args, **kwargs)
        return self.buy_telemetry

    def record_sell(self, *args, **kwargs):
        self.sell_telemetry = super().record_sell(*args, **kwargs)
        return self.sell_telemetry


def test_live_shadow_mode_buy_sell_cycle_does_not_affect_mock_contract():
    client = FakeTickerClient(price=110.0)
    executor = ControlledMockExecutor(
        client=client,
        position_manager=None,
        tracker=None,
        initial_balance=1000.0,
        notifier=None,
    )
    executor.live_shadow = RecordingLiveShadowSimulator()

    initial_balance = executor.get_balance("USDC")
    signal = SimpleNamespace(
        pair="TESTUSDC",
        entry_price=100.0,
        allocated_usdc=100.0,
        stop_loss=95.0,
        take_profit=115.0,
    )

    buy_result = executor.execute_buy(signal)

    assert buy_result.pair == "TESTUSDC"
    assert buy_result.entry_price == 100.0
    assert buy_result.quantity == 1.0
    assert buy_result.allocated_usdc == 100.0
    assert buy_result.status == "FILLED"
    assert executor.has_open_position("TESTUSDC") is True
    assert executor.get_balance("USDC") == pytest.approx(initial_balance - 100.0)

    buy_shadow = executor.live_shadow.buy_telemetry
    assert buy_shadow["symbol"] == "TESTUSDC"
    assert buy_shadow["signal_price"] == 100.0
    assert buy_shadow["shadow_entry_price"] == pytest.approx(100.05)
    assert buy_shadow["no_effect"] is True

    sell_result = executor.execute_sell("TESTUSDC", reason="CONTROLLED_TEST")

    assert sell_result.pair == "TESTUSDC"
    assert sell_result.entry_price == 100.0
    assert sell_result.exit_price == 110.0
    assert sell_result.quantity == 1.0
    assert sell_result.net_pnl_usdc == pytest.approx(10.0)
    assert sell_result.reason == "CONTROLLED_TEST"
    assert sell_result.status == "FILLED"
    assert executor.has_open_position("TESTUSDC") is False
    assert executor.get_balance("USDC") == pytest.approx(initial_balance + 10.0)

    sell_shadow = executor.live_shadow.sell_telemetry
    assert sell_shadow["shadow_entry_price"] == pytest.approx(100.05)
    assert sell_shadow["shadow_exit_price"] == pytest.approx(109.945)
    assert sell_shadow["gross_pnl_pct"] == pytest.approx(9.890054972513745)
    assert sell_shadow["net_pnl_pct"] == pytest.approx(9.68016491754124)
    assert sell_shadow["gross_pnl_usdc"] == pytest.approx(9.895)
    assert sell_shadow["net_pnl_usdc"] == pytest.approx(9.685005)
    assert sell_shadow["mock_vs_shadow_delta"] == pytest.approx(-0.314995)
    assert sell_shadow["shadow_result"] == "WIN"
    assert sell_shadow["no_effect"] is True

    assert client.orders_created == []
    assert executor.live_shadow.shadow_positions == {}
