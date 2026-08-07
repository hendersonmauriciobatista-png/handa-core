# =============================================================================
# core/dynamic_policy/market_regime_detector.py
# H&A — Market Regime Detector (NPD-H&A v1)
# =============================================================================

from core.dynamic_policy.policy_models import MarketContext


class MarketRegimeDetector:
    """
    Classifica o regime atual do mercado com base no snapshot.

    Regimes:
    - TREND_STRONG
    - TREND_WEAK
    - SIDEWAYS_TRADABLE
    - SIDEWAYS_DEAD
    """

    @staticmethod
    def detect(snapshot: MarketContext) -> str:

        price = float(snapshot.price or 0.0)
        ema_fast = float(snapshot.ema_fast or 0.0)
        ema_slow = float(snapshot.ema_slow or 0.0)
        rsi = float(snapshot.rsi or 0.0)
        volume = float(snapshot.volume_ratio or 0.0)
        atr = float(snapshot.atr or 0.0)

        if price <= 0:
            return "UNKNOWN"

        # -----------------------------------------------------
        # DERIVADOS
        # -----------------------------------------------------
        ema_spread = abs(ema_fast - ema_slow) / price if price > 0 else 0.0
        atr_pct = atr / price if price > 0 else 0.0

        # -----------------------------------------------------
        # TREND FORTE
        # -----------------------------------------------------
        if (
            ema_fast > ema_slow
            and ema_spread >= 0.0012
            and rsi >= 58
            and volume >= 1.4
        ):
            return "TREND_STRONG"

        # -----------------------------------------------------
        # TREND FRACO
        # -----------------------------------------------------
        if (
            ema_fast > ema_slow
            and ema_spread >= 0.0006
            and rsi >= 52
        ):
            return "TREND_WEAK"

        # -----------------------------------------------------
        # LATERAL OPERÁVEL
        # -----------------------------------------------------
        if (
            ema_fast > ema_slow
            and ema_spread >= 0.0004
            and volume >= 1.3
            and 45 <= rsi <= 60
        ):
            return "SIDEWAYS_TRADABLE"

        # -----------------------------------------------------
        # LATERAL RUIM
        # -----------------------------------------------------
        return "SIDEWAYS_DEAD"