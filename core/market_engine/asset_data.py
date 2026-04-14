class AssetData:
    """
    Estrutura simples de dados para representar um ativo no ranking.
    Não contém lógica. Apenas armazena resultados calculados pelo Motor.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol

        # Score final usado para ranking
        self.score_total = 0.0

        # Breakdown de score (transparência e debug)
        self.score_technical = 0.0
        self.score_momentum = 0.0
        self.score_liquidity = 0.0
        self.score_historical_total = 0.0
        self.score_historical_regime = 0.0

    def __repr__(self):
        return f"<AssetData {self.symbol} | score={self.score_total:.2f}>"
