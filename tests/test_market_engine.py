from core.market_engine.score_calculator import ScoreCalculator
from core.market_engine.historical_memory import HistoricalMemory
from core.market_engine.ranking_engine import RankingEngine
from core.interfaces.risk_interface import RiskInterface


class MockRisk(RiskInterface):

    def get_current_regime(self) -> str:
        return "TRENDING"

    def get_igr(self) -> float:
        return 0.2

    def is_system_stressed(self) -> bool:
        return False


def run_market_test():
    risk = MockRisk()
    memory = HistoricalMemory()
    calculator = ScoreCalculator(risk)
    ranking_engine = RankingEngine(calculator, memory, delta_minimo=0.5)

    memory.register_trade_result("BTCUSDC", "TRENDING", 1.2)
    memory.register_trade_result("BTCUSDC", "TRENDING", 0.8)
    memory.register_trade_result("ETHUSDC", "TRENDING", 0.5)
    memory.register_trade_result("SOLUSDC", "LATERAL", 1.0)

    symbols = ["BTCUSDC", "ETHUSDC", "SOLUSDC"]

    technical_data_map = {
        "BTCUSDC": {"technical": 2.0, "momentum": 1.0, "liquidity": 0.5},
        "ETHUSDC": {"technical": 1.5, "momentum": 0.8, "liquidity": 0.4},
        "SOLUSDC": {"technical": 1.8, "momentum": 0.9, "liquidity": 0.3},
    }

    ranking_engine.recalculate(symbols, technical_data_map)

    ranking = ranking_engine.get_ranking()

    print("\nRanking Final:")
    for asset in ranking:
        print(asset)

    print("\nTop symbols:", ranking_engine.get_top_symbols())

    print("\nTeste Swap BTC -> ETH:",
          ranking_engine.should_swap("BTCUSDC", "ETHUSDC"))


if __name__ == "__main__":
    run_market_test()
