# ============================================================
# IndicatorEngine
# Matemática pura de indicadores técnicos
# H&A - MarketSnapshotContract v1.0
# ============================================================

from typing import List


class IndicatorEngine:

    # ============================
    # EMA
    # ============================
    @staticmethod
    def compute_ema(closes: List[float], period: int) -> float:
        if len(closes) < period:
            raise ValueError(f"Dados insuficientes para EMA {period}")

        multiplier = 2 / (period + 1)

        ema = sum(closes[:period]) / period

        for price in closes[period:]:
            ema = (price - ema) * multiplier + ema

        return float(ema)

    # ============================
    # RSI
    # ============================
    @staticmethod
    def compute_rsi(closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            raise ValueError("Dados insuficientes para RSI")

        gains = []
        losses = []

        for i in range(1, period + 1):
            delta = closes[i] - closes[i - 1]

            if delta >= 0:
                gains.append(delta)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(delta))

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return float(rsi)

    # ============================
    # ATR
    # ============================
    @staticmethod
    def compute_atr(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14
    ) -> float:

        if len(highs) < period + 1:
            raise ValueError("Dados insuficientes para ATR")

        true_ranges = []

        for i in range(1, period + 1):
            high = highs[i]
            low = lows[i]
            prev_close = closes[i - 1]

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )

            true_ranges.append(tr)

        atr = sum(true_ranges) / period
        return float(atr)

    # ============================
    # Volume Ratio
    # ============================
    @staticmethod
    def compute_volume_ratio(
        volumes: List[float],
        lookback: int = 20
    ) -> float:

        if len(volumes) < lookback + 1:
            raise ValueError("Dados insuficientes para Volume Ratio")

        last_volume = volumes[-1]
        avg_volume = sum(volumes[-(lookback + 1):-1]) / lookback

        if avg_volume == 0:
            return 0.0

        return float(last_volume / avg_volume)