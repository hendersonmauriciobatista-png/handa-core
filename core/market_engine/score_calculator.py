from typing import Dict

from core.market_engine.asset_data import AssetData
from core.interfaces.risk_interface import RiskInterface


class ScoreCalculator:
    """
    Responsável por calcular o score completo de um ativo.
    Não armazena histórico.
    Não define ranking.
    Apenas calcula e retorna AssetData preenchido.
    """

    def __init__(self, risk_interface: RiskInterface):
        self.risk_interface = risk_interface

    def calculate(self, symbol: str, technical_data: Dict, historical_data: Dict) -> AssetData:
        """
        technical_data:
            {
                "technical": float,
                "momentum": float,
                "liquidity": float
            }

        historical_data:
            {
                "total": float,
                "by_regime": {
                    "TRENDING": float,
                    "LATERAL": float,
                    ...
                }
            }
        """

        asset = AssetData(symbol)

        # -------------------------
        # Scores Técnicos
        # -------------------------

        asset.score_technical = technical_data.get("technical", 0.0)
        asset.score_momentum = technical_data.get("momentum", 0.0)
        asset.score_liquidity = technical_data.get("liquidity", 0.0)

        # -------------------------
        # Histórico
        # -------------------------

        asset.score_historical_total = historical_data.get("total", 0.0)

        current_regime = self.risk_interface.get_current_regime()

        regime_scores = historical_data.get("by_regime", {})
        asset.score_historical_regime = regime_scores.get(current_regime, 0.0)

        # -------------------------
        # Peso Híbrido
        # -------------------------

        alpha = 0.35  # histórico total
        beta = 0.65   # histórico por regime

        historical_component = (
            alpha * asset.score_historical_total
            + beta * asset.score_historical_regime
        )

        # -------------------------
        # Score Final
        # -------------------------

        asset.score_total = (
            asset.score_technical
            + asset.score_momentum
            + asset.score_liquidity
            + historical_component
        )

        return asset
