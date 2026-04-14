# ============================================================
# core/market/market_state.py
# Interpretação estrutural do estado de mercado do H&A
# ============================================================

from enum import Enum

from core.sensors.trend_sensor import TrendDirection
from core.sensors.momentum_sensor import MomentumState
from core.sensors.volume_sensor import VolumeState


class MarketState(Enum):

    BULLISH_STRONG = "BULLISH_STRONG"
    BULLISH_WEAK = "BULLISH_WEAK"

    BEARISH_STRONG = "BEARISH_STRONG"
    BEARISH_WEAK = "BEARISH_WEAK"

    SIDEWAYS = "SIDEWAYS"


class MarketStateInterpreter:
    """
    Converte sinais dos sensores em um estado único de mercado.
    """

    @staticmethod
    def interpret(
        trend: TrendDirection,
        momentum: MomentumState,
        volume: VolumeState
    ) -> MarketState:

        # tendência forte de alta
        if trend == TrendDirection.UPTREND and momentum == MomentumState.BULLISH:

            if volume == VolumeState.HIGH:
                return MarketState.BULLISH_STRONG

            return MarketState.BULLISH_WEAK

        # tendência forte de baixa
        if trend == TrendDirection.DOWNTREND and momentum == MomentumState.BEARISH:

            if volume == VolumeState.HIGH:
                return MarketState.BEARISH_STRONG

            return MarketState.BEARISH_WEAK

        # mercado lateral
        return MarketState.SIDEWAYS