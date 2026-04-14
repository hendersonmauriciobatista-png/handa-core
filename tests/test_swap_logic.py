from core.decision_cycle import DecisionCycle
from executor.mock_executor import ExecutorMock


def test_swap_respects_delta():

    executor = ExecutorMock()
    cycle = DecisionCycle(executor)

    # Primeiro ciclo — define ativo atual
    cycle.current_asset = "BTCUSDC"
    cycle.current_score = 3.0

    # Novo ativo com score pequeno (menor que DELTA)
    new_asset = "ETHUSDC"
    new_score = 3.1   # delta = 0.1 (menor que 0.3)

    should = cycle.should_swap(new_asset, new_score)

    assert should is False
