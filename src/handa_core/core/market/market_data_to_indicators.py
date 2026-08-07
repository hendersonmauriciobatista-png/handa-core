# ============================================================
# core/market/market_data_to_indicators.py
# Conecta MarketDataProvider ao IndicatorEngine
# ============================================================

from core.indicators.indicator_engine import IndicatorEngine


class MarketDataToIndicators:
    """
    Converte dados brutos de mercado (klines) em IndicatorSnapshot.
    """

    @staticmethod
    def build_snapshot_from_klines(klines):
        """
        Recebe klines da Binance e gera IndicatorSnapshot.
        Espera formato padrão:
        [
          [
            open_time,
            open,
            high,
            low,
            close,
            volume,
            ...
          ],
          ...
        ]
        """

        prices = []
        volumes = []

        for k in klines:
            close_price = float(k[4])
            volume = float(k[5])

            prices.append(close_price)
            volumes.append(volume)

        snapshot = IndicatorEngine.build_snapshot(prices, volumes)

        return snapshot