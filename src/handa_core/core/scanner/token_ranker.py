# ============================================================
# core/scanner/token_ranker.py
# Responsável por gerar ranking inicial de tokens
# ============================================================

from typing import List, Dict


class TokenRanker:

    def __init__(self, market_data_provider):

        self.market_data_provider = market_data_provider
        self.tokens_cache: List[Dict] = []


    def update_rankings(self):

        tokens = self.market_data_provider.get_all_pairs()

        ranked_tokens = []

        for token in tokens:

            metrics = self._calculate_metrics(token)

            score = self._calculate_score(metrics)

            ranked_tokens.append({
                "symbol": token,
                "score": score,
                "metrics": metrics
            })

        ranked_tokens.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        self.tokens_cache = ranked_tokens


    def get_ranked_tokens(self, limit: int = 100):

        return self.tokens_cache[:limit]


    def _calculate_metrics(self, token):

        data = self.market_data_provider.get_market_snapshot(token)

        momentum = self._momentum_score(data)
        volume = self._volume_score(data)
        volatility = self._volatility_score(data)

        return {
            "momentum": momentum,
            "volume": volume,
            "volatility": volatility
        }


    def _calculate_score(self, metrics):

        return (
            metrics["momentum"] * 0.4 +
            metrics["volume"] * 0.3 +
            metrics["volatility"] * 0.3
        )


    def _momentum_score(self, data):

        ema10 = data["ema10"]
        ema20 = data["ema20"]

        if ema10 > ema20:
            return 1.0

        return 0.0


    def _volume_score(self, data):

        volume = data["volume"]
        avg_volume = data["avg_volume"]

        if avg_volume == 0:
            return 0

        return min(volume / avg_volume, 1.0)


    def _volatility_score(self, data):

        high = data["high"]
        low = data["low"]

        if high == 0:
            return 0

        return (high - low) / high