# ============================================================
# core/sensors/sensor_hub.py
# Orquestrador dos sensores institucionais do H&A
# ============================================================

from core.sensors.trend_sensor import TrendSensor
from core.sensors.momentum_sensor import MomentumSensor
from core.sensors.volume_sensor import VolumeSensor

from core.market.market_state import MarketStateInterpreter
from core.indicators.indicator_snapshot import IndicatorSnapshot


class SensorHub:
    """
    Centraliza a execução dos sensores de mercado.
    Também agrega os sinais em um market_score institucional.

    Responsabilidades:
    - executar sensores primários
    - interpretar estado de mercado
    - consolidar score institucional
    - manter compatibilidade com o restante do H&A
    """

    # ========================================================
    # HELPERS INTERNOS
    # ========================================================

    @staticmethod
    def _safe_name(enum_obj) -> str:
        if enum_obj is None:
            return "UNKNOWN"

        try:
            if hasattr(enum_obj, "name"):
                return str(enum_obj.name).strip().upper()

            if hasattr(enum_obj, "value"):
                return str(enum_obj.value).strip().upper()

            return str(enum_obj).strip().upper()
        except Exception:
            return "UNKNOWN"

    @staticmethod
    def _score_trend(trend_name: str, snapshot: IndicatorSnapshot) -> int:
        score = 0

        ema_10 = float(snapshot.ema_10 or 0.0)
        ema_20 = float(snapshot.ema_20 or 0.0)
        ema_50 = float(snapshot.ema_50 or 0.0)

        if trend_name in ("UPTREND", "STRONG_UPTREND", "BULLISH"):
            score += 2

        # força estrutural adicional
        if ema_10 > ema_20 > ema_50:
            score += 1

        return score

    @staticmethod
    def _score_momentum(momentum_name: str, snapshot: IndicatorSnapshot) -> int:
        score = 0

        rsi = float(snapshot.rsi_14 or 0.0)
        volume_ratio = float(snapshot.volume_ratio or 0.0)

        if momentum_name == "BULLISH":
            score += 2
        elif momentum_name in ("STRONG", "STRONG_BULLISH"):
            score += 3
        elif momentum_name == "NEUTRAL":
            score += 0
        elif momentum_name in ("BEARISH", "STRONG_BEARISH"):
            score -= 1

        # força adicional contextual
        if rsi >= 55:
            score += 1

        if rsi >= 65:
            score += 1

        if volume_ratio >= 1.20:
            score += 1

        return score

    @staticmethod
    def _score_volume(volume_name: str, snapshot: IndicatorSnapshot) -> int:
        score = 0

        volume_ratio = float(snapshot.volume_ratio or 0.0)

        if volume_name == "HIGH":
            score += 1
        elif volume_name == "VERY_HIGH":
            score += 2
        elif volume_name == "LOW":
            score += 0

        # reforço quantitativo
        if volume_ratio >= 1.50:
            score += 1

        return score

    @staticmethod
    def _apply_guardrails(
        base_score: int,
        trend_name: str,
        momentum_name: str,
        volume_name: str,
        snapshot: IndicatorSnapshot,
    ) -> int:
        """
        Guardrails para evitar score artificialmente alto em mercado ruim.
        """
        score = int(base_score)

        rsi = float(snapshot.rsi_14 or 0.0)
        volume_ratio = float(snapshot.volume_ratio or 0.0)

        # momentum neutro + volume fraco = não pode parecer mercado forte
        if momentum_name == "NEUTRAL" and volume_name == "LOW":
            score = min(score, 1)

        # RSI muito fraco limita score
        if rsi < 45:
            score = min(score, 1)

        # volume morto limita score
        if volume_ratio < 0.80:
            score = min(score, 1)

        # tendência ruim puxa score para baixo
        if trend_name in ("DOWNTREND", "BEARISH", "STRONG_DOWNTREND"):
            score = min(score, 0)

        # proteção para não deixar score negativo
        if score < 0:
            score = 0

        return score

    # ========================================================
    # ANÁLISE PRINCIPAL
    # ========================================================

    @staticmethod
    def analyze(snapshot: IndicatorSnapshot) -> dict:
        # ------------------------------------------------
        # Execução dos sensores
        # ------------------------------------------------
        trend = TrendSensor.detect(
            ema_10=snapshot.ema_10, ema_20=snapshot.ema_20, ema_50=snapshot.ema_50
        )

        momentum = MomentumSensor.detect(
            ema_10=snapshot.ema_10,
            ema_20=snapshot.ema_20,
            rsi_14=snapshot.rsi_14,
            volume_ratio=snapshot.volume_ratio,
        )

        volume = VolumeSensor.detect(volume_ratio=snapshot.volume_ratio)

        trend_name = SensorHub._safe_name(trend)
        momentum_name = SensorHub._safe_name(momentum)
        volume_name = SensorHub._safe_name(volume)

        # ------------------------------------------------
        # Interpretação do estado de mercado
        # ------------------------------------------------
        market_state = MarketStateInterpreter.interpret(
            trend=trend, momentum=momentum, volume=volume
        )

        # ------------------------------------------------
        # Market Score institucional
        # ------------------------------------------------
        trend_score = SensorHub._score_trend(trend_name, snapshot)
        momentum_score = SensorHub._score_momentum(momentum_name, snapshot)
        volume_score = SensorHub._score_volume(volume_name, snapshot)

        raw_score = trend_score + momentum_score + volume_score

        final_score = SensorHub._apply_guardrails(
            base_score=raw_score,
            trend_name=trend_name,
            momentum_name=momentum_name,
            volume_name=volume_name,
            snapshot=snapshot,
        )

        # ------------------------------------------------
        # Resultado consolidado
        # ------------------------------------------------
        return {
            "market_state": market_state,
            "trend": trend,
            "momentum": momentum,
            "volume": volume,
            "rsi": float(snapshot.rsi_14 or 0.0),
            "volume_ratio": float(snapshot.volume_ratio or 0.0),
            "market_score": int(final_score),
            "price": float(snapshot.price or 0.0),
        }
