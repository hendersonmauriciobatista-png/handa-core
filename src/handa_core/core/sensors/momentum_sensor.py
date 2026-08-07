# ============================================================
# core/sensors/momentum_sensor.py
# Sensor institucional de momentum do H&A
# ============================================================

from enum import Enum


class MomentumState(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class MomentumSensor:
    """
    Detecta momentum institucional combinando:
    EMA + RSI + Volume
    """

    @staticmethod
    def detect(
        ema_10: float,
        ema_20: float,
        rsi_14: float,
        volume_ratio: float
    ) -> MomentumState:

        # momentum forte de alta
        if ema_10 > ema_20 and rsi_14 > 55 and volume_ratio > 1.2:
            return MomentumState.BULLISH

        # momentum forte de baixa
        if ema_10 < ema_20 and rsi_14 < 45 and volume_ratio > 1.2:
            return MomentumState.BEARISH

        # neutro
        return MomentumState.NEUTRAL