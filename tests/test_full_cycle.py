import pytest

from core.decision_cycle import DecisionCycle


class FakeExecutor:
    def __init__(self):
        self._has_position = True
        self.sell_called = False

    def has_open_position(self):
        return self._has_position

    def sell(self, price):
        self.sell_called = True
        self._has_position = False
        return {"status": "ok"}


def test_sell_after_hold_cycles():
    fake_executor = FakeExecutor()
    cycle = DecisionCycle(fake_executor)

    # Simular que já existe ativo comprado
    cycle.current_asset = "BTCUSDC"

    for _ in range(3):
        cycle.run_cycle(
            total_usdc=1000.0,
            current_exposure=100.0,
            market_data={},
            asset_price_lookup={"BTCUSDC": 105.0},
            step_size_lookup={"BTCUSDC": 0.0001},
            min_notional_lookup={"BTCUSDC": 10}
        )

    assert fake_executor.sell_called is True
def test_not_sell_before_hold_limit():
    fake_executor = FakeExecutor()
    cycle = DecisionCycle(fake_executor)

    cycle.current_asset = "BTCUSDC"

    # Rodar apenas 2 ciclos (limite é 3)
    for _ in range(2):
        result = cycle.run_cycle(
            total_usdc=1000.0,
            current_exposure=100.0,
            market_data={},
            asset_price_lookup={"BTCUSDC": 105.0},
            step_size_lookup={"BTCUSDC": 0.0001},
            min_notional_lookup={"BTCUSDC": 10}
        )

    assert fake_executor.sell_called is False
    assert result["executed"] is False


def test_state_reset_after_sell():
    fake_executor = FakeExecutor()
    cycle = DecisionCycle(fake_executor)

    cycle.current_asset = "BTCUSDC"
    cycle.current_score = 5.0

    for _ in range(3):
        result = cycle.run_cycle(
            total_usdc=1000.0,
            current_exposure=100.0,
            market_data={},
            asset_price_lookup={"BTCUSDC": 105.0},
            step_size_lookup={"BTCUSDC": 0.0001},
            min_notional_lookup={"BTCUSDC": 10}
        )

    assert fake_executor.sell_called is True
    assert cycle.current_asset is None
    assert cycle.current_score is None
    assert cycle.hold_cycles == 0

