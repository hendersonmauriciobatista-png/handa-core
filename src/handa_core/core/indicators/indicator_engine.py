# ============================================================
# core/indicators/indicator_engine.py
# Engine responsável por calcular indicadores técnicos
# ============================================================

import statistics

from core.indicators.indicator_snapshot import IndicatorSnapshot


class IndicatorEngine:
    """
    Calcula indicadores técnicos usados pelos sensores do H&A.
    """

    @staticmethod
    def ema(values, period):
        """
        Calcula Exponential Moving Average.
        """

        if len(values) < period:
            raise ValueError("Dados insuficientes para EMA")

        multiplier = 2 / (period + 1)

        ema = values[0]

        for price in values[1:]:
            ema = (price - ema) * multiplier + ema

        return ema

    @staticmethod
    def rsi(values, period=14):
        """
        Calcula RSI.
        """

        if len(values) < period + 1:
            raise ValueError("Dados insuficientes para RSI")

        gains = []
        losses = []

        for i in range(1, period + 1):

            delta = values[i] - values[i - 1]

            if delta >= 0:
                gains.append(delta)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(delta))

        avg_gain = statistics.mean(gains)
        avg_loss = statistics.mean(losses)

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss

        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def volume_ratio(volumes, window=20):
        """
        Volume atual comparado à média recente.
        """

        if len(volumes) < window:
            raise ValueError("Dados insuficientes para volume ratio")

        avg_volume = statistics.mean(volumes[-window:])

        current_volume = volumes[-1]

        return current_volume / avg_volume

    @staticmethod
    def build_snapshot(prices, volumes):
        """
        Constrói um IndicatorSnapshot automaticamente.
        """

        ema_10 = IndicatorEngine.ema(prices, 10)
        ema_20 = IndicatorEngine.ema(prices, 20)
        ema_50 = IndicatorEngine.ema(prices, 50)

        rsi_14 = IndicatorEngine.rsi(prices)

        volume_ratio = IndicatorEngine.volume_ratio(volumes)

        current_price = prices[-1]

        return IndicatorSnapshot(
            ema_10=ema_10,
            ema_20=ema_20,
            ema_50=ema_50,
            rsi_14=rsi_14,
            volume_ratio=volume_ratio,
            price=current_price,
        )
