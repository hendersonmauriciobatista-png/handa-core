class MarketEngine:

    def rank_assets(self, market_data: dict):
        """
        market_data:
            {
                "BTCUSDC": score,
                "ETHUSDC": score,
                ...
            }

        Retorna:
            best_asset, best_score, score_medio
        """

        if not market_data:
            raise ValueError("market_data vazio")

        best_asset = max(market_data, key=market_data.get)
        best_score = market_data[best_asset]

        score_medio = sum(market_data.values()) / len(market_data)

        return best_asset, best_score, score_medio
