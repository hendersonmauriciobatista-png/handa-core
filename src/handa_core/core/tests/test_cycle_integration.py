from core.decision_cycle import DecisionCycle
from executor.mock_executor import ExecutorMock


def test_single_cycle_execution():

    executor = ExecutorMock()
    cycle = DecisionCycle(executor)

    market_data = {
        "BTCUSDC": {"score": 3.0},
        "ETHUSDC": {"score": 2.5},
    }

    def mock_rank_assets(_):
        return "BTCUSDC", 3.0, 2.75

    cycle.market_engine.rank_assets = mock_rank_assets

    result = cycle.run_cycle(
        total_usdc=1000,
        current_exposure=0,
        market_data=market_data,
        asset_price_lookup={"BTCUSDC": 50000},
        step_size_lookup={"BTCUSDC": 0.0001},
        min_notional_lookup={"BTCUSDC": 10},
    )

    assert result["executed"] is True
    assert result["symbol"] == "BTCUSDC"
