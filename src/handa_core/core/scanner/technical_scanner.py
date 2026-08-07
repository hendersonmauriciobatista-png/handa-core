# ============================================================
# core/scanner/technical_scanner.py
# Scanner técnico de tokens do H&A
# ============================================================

from core.market.market_snapshot_cache import MarketSnapshotCache
from core.market.market_data_to_indicators import MarketDataToIndicators
from core.sensors.sensor_hub import SensorHub


class TechnicalScanner:

    def __init__(self, client):

        self.client = client
        self.cache = MarketSnapshotCache(client)


    def analyze_symbol(self, symbol, interval="5m", limit=100):
        """
        Analisa tecnicamente um único token
        """

        klines = self.cache.get_klines(
            symbol=symbol,
            interval=interval,
            limit=limit
        )

        snapshot = MarketDataToIndicators.build_snapshot_from_klines(
            klines
        )

        sensor_result = SensorHub.analyze(snapshot)

        return {
            "symbol": symbol,
            "snapshot": snapshot,
            "analysis": sensor_result
        }