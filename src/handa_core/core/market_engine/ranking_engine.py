from typing import List, Dict

from core.market_engine.asset_data import AssetData
from core.market_engine.score_calculator import ScoreCalculator
from core.market_engine.historical_memory import HistoricalMemory


class RankingEngine:
    """
    Responsável por:
        - Calcular score dos ativos
        - Ordenar ranking
        - Aplicar política de swap (delta mínimo)
    """

    def __init__(
        self,
        score_calculator: ScoreCalculator,
        historical_memory: HistoricalMemory,
        delta_minimo: float = 0.5
    ):
        self.score_calculator = score_calculator
        self.historical_memory = historical_memory
        self.delta_minimo = delta_minimo

        self._ranking: List[AssetData] = []

    # --------------------------------------------------
    # Recalculo do ranking
    # --------------------------------------------------

    def recalculate(
        self,
        symbols: List[str],
        technical_data_map: Dict[str, Dict]
    ):
        """
        symbols: lista de ativos disponíveis
        technical_data_map:
            {
                "BTCUSDC": {
                    "technical": float,
                    "momentum": float,
                    "liquidity": float
                }
            }
        """

        ranking_list = []

        for symbol in symbols:
            technical_data = technical_data_map.get(symbol, {})

            historical_data = self.historical_memory.get_historical_data(symbol)

            asset = self.score_calculator.calculate(
                symbol=symbol,
                technical_data=technical_data,
                historical_data=historical_data
            )

            ranking_list.append(asset)

        # Ordena por score_total decrescente
        ranking_list.sort(key=lambda x: x.score_total, reverse=True)

        self._ranking = ranking_list

    # --------------------------------------------------
    # Consulta
    # --------------------------------------------------

    def get_ranking(self) -> List[AssetData]:
        return self._ranking

    def get_top_symbols(self) -> List[str]:
        return [asset.symbol for asset in self._ranking]

    # --------------------------------------------------
    # Política de Swap
    # --------------------------------------------------

    def should_swap(self, current_symbol: str, new_symbol: str) -> bool:
        """
        Decide se deve trocar ativo com base no delta mínimo.
        """

        current_asset = next(
            (a for a in self._ranking if a.symbol == current_symbol),
            None
        )

        new_asset = next(
            (a for a in self._ranking if a.symbol == new_symbol),
            None
        )

        if not current_asset or not new_asset:
            return False

        return new_asset.score_total >= current_asset.score_total + self.delta_minimo
