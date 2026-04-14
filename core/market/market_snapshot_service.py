# ============================================================
# MarketSnapshotService
# Orquestra dados + indicadores
# H&A - MarketSnapshotContract v1.0
# Usa apenas candle FECHADO
# ============================================================

import time
from binance.client import Client

from core.market.market_data_provider import MarketDataProvider, MarketDataException
from core.market.indicator_engine import IndicatorEngine


class MarketSnapshotService:

    def __init__(self, client: Client):
        self.provider = MarketDataProvider(client)
        self.indicators = IndicatorEngine()

    # ============================================================
    # Snapshot Oficial v1.0 (candle fechado)
    # ============================================================
    def get_market_snapshot(self, symbol: str) -> dict:

        try:
            candles = self.provider.get_candles(symbol)

            # Remove último candle (em formação)
            closed_candles = candles[:-1]

            if len(closed_candles) < 50:
                raise MarketDataException(
                    f"Candles fechados insuficientes para {symbol}"
                )

            closes = [c["close"] for c in closed_candles]
            highs = [c["high"] for c in closed_candles]
            lows = [c["low"] for c in closed_candles]
            volumes = [c["volume"] for c in closed_candles]

            price = closes[-1]

            ema_10 = self.indicators.compute_ema(closes, 10)
            ema_20 = self.indicators.compute_ema(closes, 20)
            ema_50 = self.indicators.compute_ema(closes, 50)

            rsi_14 = self.indicators.compute_rsi(closes, 14)
            atr_14 = self.indicators.compute_atr(highs, lows, closes, 14)
            volume_ratio = self.indicators.compute_volume_ratio(volumes, 20)

            trend_bias = self._compute_trend_bias(
                ema_10,
                ema_20,
                ema_50
            )

            return {
                "symbol": symbol,
                "timestamp": int(time.time()),
                "price": price,
                "ema_10": ema_10,
                "ema_20": ema_20,
                "ema_50": ema_50,
                "rsi_14": rsi_14,
                "atr_14": atr_14,
                "volume_ratio": volume_ratio,
                "trend_bias": trend_bias
            }

        except Exception as e:
            raise MarketDataException(
                f"Falha ao gerar snapshot para {symbol}: {str(e)}"
            )

    # ============================================================
    # Trend Bias Oficial
    # ============================================================
    @staticmethod
    def _compute_trend_bias(
        ema_10: float,
        ema_20: float,
        ema_50: float
    ) -> str:

        if ema_10 > ema_20 > ema_50:
            return "bullish"

        if ema_10 < ema_20 < ema_50:
            return "bearish"

        return "neutral"