# ============================================================
# core/alo/market_context_builder.py
# H&A — ALO Market Context Builder
# Constrói o contexto macro de mercado para a camada de visão
# ============================================================

from typing import Any, Dict, Optional

from core.alo.vision_models import MarketContext


class MarketContextBuilder:
    """
    Builder responsável por transformar snapshots/resumos
    de mercado em um MarketContext padronizado para o ALO.
    """

    def __init__(self):
        pass

    # ============================================================
    # PUBLIC API
    # ============================================================

    def build(
        self,
        liquidity_data: Optional[Dict[str, Any]] = None,
        market_summary: Optional[Dict[str, Any]] = None,
    ) -> MarketContext:
        liquidity_data = liquidity_data or {}
        market_summary = market_summary or {}

        liquidity_score = self._safe_float(liquidity_data.get("liquidity_score", 0.0))
        liquidity_label = str(liquidity_data.get("liquidity_label", "")).strip()
        liquidity_message = str(liquidity_data.get("liquidity_message", "")).strip()

        avg_volume_ratio = self._safe_float(liquidity_data.get("avg_volume_ratio", 0.0))
        uptrend_count = self._safe_int(liquidity_data.get("uptrend_count", 0))
        refined_count = self._safe_int(liquidity_data.get("refined_count", 0))
        approved_count = self._safe_int(liquidity_data.get("approved_count", 0))

        market_state = self._infer_market_state(
            liquidity_score=liquidity_score,
            approved_count=approved_count,
            uptrend_count=uptrend_count,
            refined_count=refined_count,
        )

        opportunity_density = self._infer_opportunity_density(
            approved_count=approved_count,
            refined_count=refined_count,
        )

        trend_strength = self._infer_trend_strength(
            uptrend_count=uptrend_count,
            refined_count=refined_count,
            approved_count=approved_count,
        )

        extra = {
            "raw_liquidity_data": dict(liquidity_data),
            "raw_market_summary": dict(market_summary),
        }

        if market_summary:
            for key, value in market_summary.items():
                if key not in extra:
                    extra[key] = value

        return MarketContext(
            liquidity_score=liquidity_score,
            liquidity_label=liquidity_label,
            liquidity_message=liquidity_message,
            avg_volume_ratio=avg_volume_ratio,
            uptrend_count=uptrend_count,
            refined_count=refined_count,
            approved_count=approved_count,
            market_state=market_state,
            opportunity_density=opportunity_density,
            trend_strength=trend_strength,
            extra=extra,
        )

    # ============================================================
    # INFERENCE RULES
    # ============================================================

    def _infer_market_state(
        self,
        liquidity_score: float,
        approved_count: int,
        uptrend_count: int,
        refined_count: int,
    ) -> str:
        if liquidity_score <= 0.0 and approved_count <= 0 and uptrend_count <= 0:
            return "UNKNOWN"

        if liquidity_score < 0.35:
            return "LATERAL_FRACO"

        if liquidity_score < 0.55:
            if approved_count <= 0:
                return "LATERAL_FRACO"
            return "NEUTRO_OPERAVEL"

        if liquidity_score < 0.75:
            if approved_count >= 2 or uptrend_count >= 4:
                return "BULLISH_MODERADO"
            return "NEUTRO_OPERAVEL"

        if approved_count >= 3 or uptrend_count >= 5 or refined_count >= 5:
            return "BULLISH_FORTE"

        return "OPERAVEL"

    def _infer_opportunity_density(
        self,
        approved_count: int,
        refined_count: int,
    ) -> str:
        if approved_count <= 0 and refined_count <= 0:
            return "NULA"

        if approved_count <= 0 and refined_count > 0:
            return "BAIXA"

        if approved_count == 1:
            return "BAIXA"

        if approved_count in (2, 3):
            return "MODERADA"

        if approved_count >= 4:
            return "ALTA"

        return "UNKNOWN"

    def _infer_trend_strength(
        self,
        uptrend_count: int,
        refined_count: int,
        approved_count: int,
    ) -> str:
        base_count = max(uptrend_count, refined_count, approved_count)

        if base_count <= 0:
            return "FRACA"

        if base_count == 1:
            return "FRACA"

        if base_count in (2, 3):
            return "MODERADA"

        if base_count >= 4:
            return "FORTE"

        return "UNKNOWN"

    # ============================================================
    # HELPERS
    # ============================================================

    def _safe_float(self, value: Any) -> float:
        try:
            if value is None:
                return 0.0
            return float(value)
        except Exception:
            return 0.0

    def _safe_int(self, value: Any) -> int:
        try:
            if value is None:
                return 0
            return int(value)
        except Exception:
            return 0
