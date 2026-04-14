# ============================================================
# core/sensors/trend_sensor.py
# Sensor institucional de tendência do H&A
# Baseado na estrutura EMA 10 / 20 / 50
# ============================================================

from enum import Enum


class TrendDirection(Enum):
    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    SIDEWAYS = "SIDEWAYS"


class TrendSensor:
    """
    Detecta a direção da tendência usando EMAs institucionais.
    """

    @staticmethod
    def detect(ema_10: float, ema_20: float, ema_50: float) -> TrendDirection:

        # Tendência forte de alta
        if ema_10 > ema_20 > ema_50:
            return TrendDirection.UPTREND

        # Tendência forte de baixa
        if ema_10 < ema_20 < ema_50:
            return TrendDirection.DOWNTREND

        # Mercado lateral
        return TrendDirection.SIDEWAYS