# ============================================================
# core/scanner/market_scanner.py
# Scanner de mercado do H&A
# ============================================================

from binance.client import Client


STABLE_ASSETS = {
    "USDC",
    "USDT",
    "FDUSD",
    "TUSD",
    "USDP",
    "BUSD",
    "DAI",
    "EUR",
    "USD1"
}

MIN_VOLUME =500_000 # volume mínimo em USDC


class MarketScanner:

    def __init__(self, client: Client):
        self.client = client


    def _is_stable_pair(self, symbol):

        base = symbol[:-4]  # remove "USDC"

        return base in STABLE_ASSETS


    def get_top_liquid_usdc_pairs(self, limit=40):
        """
        Retorna pares USDC com boa liquidez e volatilidade
        """

        tickers = self.client.get_ticker()

        candidates = []

        for t in tickers:

            symbol = t["symbol"]

            if not symbol.endswith("USDC"):
                continue

            if self._is_stable_pair(symbol):
                continue

            volume = float(t["quoteVolume"])

            if volume < MIN_VOLUME:
                continue

            volatility = abs(float(t["priceChangePercent"]))

            # score balanceado
            liquidity_score = min(volume / 10_000_000, 5.0)
            ranking_score = (volatility * 0.7) + (liquidity_score * 0.3)

            candidates.append((symbol, volume, volatility, ranking_score))

            candidates.sort(key=lambda x: x[3], reverse=True)
        

        top_pairs = [c[0] for c in candidates[:limit]]

        return top_pairs