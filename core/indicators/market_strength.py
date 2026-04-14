# ============================================================
# core/indicators/market_strength.py
# Calcula a força do mercado (0–100)
# ============================================================

from statistics import mean


class MarketStrengthCalculator:

    """
    Calcula Market Strength baseado em:
    - Expansão entre EMAs
    - Volume relativo
    - Posição do RSI
    """

    def calculate(self, snapshots):

        if len(snapshots) < 3:
            return 0.0

        ema_scores = []
        volume_scores = []
        rsi_scores = []

        for snap in snapshots:

            # ------------------------------------------------
            # EMA Expansion (força da tendência)
            # ------------------------------------------------
            ema_diff = abs(snap.ema_10 - snap.ema_20)

            ema_score = min(ema_diff * 1000, 100)
            ema_scores.append(ema_score)

            # ------------------------------------------------
            # Volume Strength
            # ------------------------------------------------
            volume_score = min(snap.volume_ratio * 50, 100)
            volume_scores.append(volume_score)

            # ------------------------------------------------
            # RSI Energy
            # ------------------------------------------------
            rsi_center_distance = abs(snap.rsi_14 - 50)

            rsi_score = min(rsi_center_distance * 2, 100)
            rsi_scores.append(rsi_score)

        ema_avg = mean(ema_scores)
        volume_avg = mean(volume_scores)
        rsi_avg = mean(rsi_scores)

        strength = (
            ema_avg * 0.4 +
            volume_avg * 0.3 +
            rsi_avg * 0.3
        )

        return round(strength, 2)