# ============================================================
# core/alo/setup_context_builder.py
# H&A — ALO Setup Context Builder
# Constrói o contexto micro do setup para a camada de visão
# ============================================================

from typing import Any, Optional

from core.alo.vision_models import SetupContext


class SetupContextBuilder:
    """
    Builder responsável por converter snapshots/objetos de análise
    em um SetupContext padronizado para o ALO Vision.
    """

    def __init__(self):
        pass

    # ============================================================
    # PUBLIC API
    # ============================================================

    def build(self, snapshot: Optional[Any] = None) -> SetupContext:
        if snapshot is None:
            return SetupContext()

        symbol = self._read_attr(snapshot, "pair", "")
        if not symbol:
            symbol = self._read_attr(snapshot, "symbol", "")

        trend = self._normalize_enum_like(self._read_attr(snapshot, "trend", "UNKNOWN"))
        momentum = self._normalize_enum_like(
            self._read_attr(snapshot, "momentum", "UNKNOWN")
        )
        market_state = self._normalize_enum_like(
            self._read_attr(snapshot, "market_state", "UNKNOWN")
        )
        volume_state = self._normalize_enum_like(
            self._read_attr(snapshot, "volume_state", "UNKNOWN")
        )

        rsi = self._safe_float(self._read_attr(snapshot, "rsi", 0.0))
        volume_ratio = self._safe_float(self._read_attr(snapshot, "volume_ratio", 0.0))
        price = self._safe_float(self._read_attr(snapshot, "price", 0.0))

        ema_fast = self._resolve_ema_fast(snapshot)
        ema_slow = self._resolve_ema_slow(snapshot)

        quality_score = self._infer_quality_score(
            trend=trend,
            momentum=momentum,
            market_state=market_state,
            volume_state=volume_state,
            rsi=rsi,
            volume_ratio=volume_ratio,
            price=price,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
        )

        quality_label = self._infer_quality_label(quality_score)

        extra = {
            "raw_snapshot_type": type(snapshot).__name__,
        }

        return SetupContext(
            symbol=str(symbol).strip().upper(),
            trend=trend,
            momentum=momentum,
            market_state=market_state,
            volume_state=volume_state,
            rsi=rsi,
            volume_ratio=volume_ratio,
            price=price,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            quality_label=quality_label,
            quality_score=quality_score,
            extra=extra,
        )

    # ============================================================
    # QUALITY INFERENCE
    # ============================================================

    def _infer_quality_score(
        self,
        trend: str,
        momentum: str,
        market_state: str,
        volume_state: str,
        rsi: float,
        volume_ratio: float,
        price: float,
        ema_fast: float,
        ema_slow: float,
    ) -> float:
        score = 0.0

        # -------------------------
        # TREND
        # -------------------------
        if trend == "UPTREND":
            score += 3.0
        elif trend == "SIDEWAYS":
            score += 1.0
        elif trend == "DOWNTREND":
            score -= 2.0

        # -------------------------
        # MOMENTUM
        # -------------------------
        if momentum in ("BULLISH", "STRONG_BULLISH"):
            score += 2.5
        elif momentum in ("NEUTRAL", "FLAT"):
            score += 0.5
        elif momentum in ("BEARISH", "STRONG_BEARISH"):
            score -= 2.0

        # -------------------------
        # MARKET STATE
        # -------------------------
        if market_state in ("BULLISH_STRONG", "BULLISH_FORTE"):
            score += 2.0
        elif market_state in ("BULLISH", "BULLISH_MODERADO", "OPERAVEL"):
            score += 1.0
        elif market_state in ("LATERAL", "LATERAL_FRACO", "WEAK", "NO_TRADE"):
            score -= 1.5

        # -------------------------
        # VOLUME STATE
        # -------------------------
        if volume_state in ("HIGH", "STRONG", "EXPANSION"):
            score += 1.5
        elif volume_state in ("NORMAL", "MODERATE"):
            score += 0.5
        elif volume_state in ("LOW", "WEAK"):
            score -= 1.0

        # -------------------------
        # RSI
        # -------------------------
        if 48.0 <= rsi <= 68.0:
            score += 2.0
        elif 40.0 <= rsi < 48.0:
            score += 1.0
        elif 68.0 < rsi <= 74.0:
            score += 0.5
        elif rsi <= 0:
            score -= 1.0
        else:
            score -= 1.5

        # -------------------------
        # VOLUME RATIO
        # -------------------------
        if volume_ratio >= 2.0:
            score += 2.0
        elif volume_ratio >= 1.3:
            score += 1.0
        elif volume_ratio >= 1.0:
            score += 0.5
        else:
            score -= 1.0

        # -------------------------
        # PRICE / STRUCTURE
        # -------------------------
        if price > 0:
            score += 0.5
        else:
            score -= 3.0

        if ema_fast > 0 and ema_slow > 0:
            if ema_fast > ema_slow:
                score += 1.5
            elif ema_fast < ema_slow:
                score -= 1.5

        if score < 0.0:
            return 0.0

        return round(score, 4)

    def _infer_quality_label(self, score: float) -> str:
        if score >= 11.0:
            return "FORTE"
        if score >= 7.0:
            return "BOA"
        if score >= 4.0:
            return "MODERADA"
        if score > 0.0:
            return "FRACA"
        return "RUIM"

    # ============================================================
    # EMA RESOLUTION
    # ============================================================

    def _resolve_ema_fast(self, snapshot: Any) -> float:
        candidates = [
            "ema_fast",
            "ema_10",
            "ema_short",
        ]
        for attr in candidates:
            value = self._read_attr(snapshot, attr, None)
            if value is not None:
                return self._safe_float(value)
        return 0.0

    def _resolve_ema_slow(self, snapshot: Any) -> float:
        candidates = [
            "ema_slow",
            "ema_20",
            "ema_long",
        ]
        for attr in candidates:
            value = self._read_attr(snapshot, attr, None)
            if value is not None:
                return self._safe_float(value)
        return 0.0

    # ============================================================
    # HELPERS
    # ============================================================

    def _read_attr(self, obj: Any, attr: str, default: Any = None) -> Any:
        if obj is None:
            return default

        if isinstance(obj, dict):
            return obj.get(attr, default)

        return getattr(obj, attr, default)

    def _safe_float(self, value: Any) -> float:
        try:
            if value is None:
                return 0.0
            return float(value)
        except Exception:
            return 0.0

    def _normalize_enum_like(self, value: Any) -> str:
        if value is None:
            return "UNKNOWN"

        text = str(value).strip()

        if "." in text:
            text = text.split(".")[-1]

        return text.upper() if text else "UNKNOWN"
