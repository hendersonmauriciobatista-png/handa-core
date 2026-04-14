from typing import Dict


class HistoricalMemory:
    """
    Armazena histórico agregado por ativo.
    Mantém:
        - histórico total
        - histórico por regime
        - número de amostras por regime
    """

    def __init__(self):
        # Estrutura:
        # {
        #   "BTCUSDC": {
        #       "total_score": float,
        #       "total_trades": int,
        #       "by_regime": {
        #           "TRENDING": {
        #               "score": float,
        #               "trades": int
        #           }
        #       }
        #   }
        # }
        self._memory: Dict[str, Dict] = {}

    # --------------------------------------------------
    # Atualização após fechamento de trade
    # --------------------------------------------------

    def register_trade_result(self, symbol: str, regime: str, score_result: float):
        """
        score_result: valor agregado do trade (ex: R:R normalizado)
        """

        if symbol not in self._memory:
            self._memory[symbol] = {
                "total_score": 0.0,
                "total_trades": 0,
                "by_regime": {}
            }

        # Atualiza total
        self._memory[symbol]["total_score"] += score_result
        self._memory[symbol]["total_trades"] += 1

        # Atualiza por regime
        regime_data = self._memory[symbol]["by_regime"].setdefault(
            regime,
            {"score": 0.0, "trades": 0}
        )

        regime_data["score"] += score_result
        regime_data["trades"] += 1

    # --------------------------------------------------
    # Consulta
    # --------------------------------------------------

    def get_historical_data(self, symbol: str) -> Dict:
        """
        Retorna estrutura compatível com ScoreCalculator.
        """

        if symbol not in self._memory:
            return {
                "total": 0.0,
                "by_regime": {}
            }

        data = self._memory[symbol]

        total_trades = data["total_trades"]
        total_score = data["total_score"]

        total_avg = total_score / total_trades if total_trades > 0 else 0.0

        by_regime_avg = {}

        for regime, values in data["by_regime"].items():
            trades = values["trades"]
            score = values["score"]

            # Peso adaptativo por número de amostras
            weight_factor = min(trades / 20, 1.0)  # peso cheio após 20 trades

            regime_avg = (score / trades) if trades > 0 else 0.0
            by_regime_avg[regime] = regime_avg * weight_factor

        return {
            "total": total_avg,
            "by_regime": by_regime_avg
        }
