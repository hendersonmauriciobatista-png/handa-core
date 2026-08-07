# ============================================================
# core/market/market_snapshot_cache.py
# Cache de klines do mercado (performance radar H&A)
# ============================================================

class MarketSnapshotCache:

    def __init__(self, client):

        self.client = client
        self.cache = {}


    def get_klines(self, symbol, interval="5m", limit=100):

        key = f"{symbol}_{interval}_{limit}"

        if key not in self.cache:

            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )

            self.cache[key] = klines

        return self.cache[key]


    def clear(self):

        self.cache = {}