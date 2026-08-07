# ============================================================
# core/market_quality/evaluator.py
# MQII — Market Quality Internal Indicator
# Evaluator oficial v1.0
# ============================================================

from core.market_quality.models import (
    MarketQualityAggregate,
    MarketQualitySnapshot,
)


class MarketQualityEvaluator:
    """
    Responsável por transformar o aggregate em:
    - score final
    - estado do mercado
    - label
    - mensagem interpretativa
    """

    def _safe_div(self, a: float, b: float) -> float:
        if b <= 0:
            return 0.0
        return a / b

    def _clamp(self, value: float, min_v: float = 0.0, max_v: float = 1.0) -> float:
        return max(min_v, min(max_v, value))

    def evaluate(self, agg: MarketQualityAggregate) -> MarketQualitySnapshot:
        total = max(agg.total_assets, 1)

        # ============================================================
        # COMPONENTES NORMALIZADOS (0 → 1)
        # ============================================================

        trend_component = self._safe_div(agg.uptrend_count, total)

        momentum_component = self._safe_div(agg.bullish_momentum_count, total)

        volume_component = self._clamp(agg.avg_volume_ratio / 2.0)

        approval_component = self._safe_div(
            (agg.refined_count + agg.approved_count), total
        )

        quality_component = self._clamp(agg.avg_market_score / 10.0)

        # ============================================================
        # SCORE FINAL
        # ============================================================

        final_score = (
            trend_component * 0.30
            + momentum_component * 0.25
            + volume_component * 0.20
            + approval_component * 0.15
            + quality_component * 0.10
        )

        final_score = self._clamp(final_score)

        print(
            f"[MQII DEBUG] "
            f"trend={trend_component:.3f} | "
            f"momentum={momentum_component:.3f} | "
            f"volume={volume_component:.3f} | "
            f"approval={approval_component:.3f} | "
            f"quality={quality_component:.3f} | "
            f"final={final_score:.3f}"
        )

        # ============================================================
        # CLASSIFICAÇÃO DO ESTADO
        # ============================================================

        if final_score < 0.25:
            state = "NO_TRADE"
            label = "FRACO"
            message = "Mercado fraco. Evitar novas entradas."

        elif final_score < 0.50:
            state = "CAUTIOUS"
            label = "MODERADO"
            message = "Mercado em formação. Monitorando oportunidades."

        elif final_score < 0.75:
            state = "TRADE_OK"
            label = "FORTE"
            message = "Liquidez e estrutura operáveis. Mercado saudável."

        else:
            state = "AGGRESSIVE_OK"
            label = "FORTE"
            message = "Mercado muito forte. Ambiente favorável para continuidade."

        # ============================================================
        # SNAPSHOT FINAL
        # ============================================================

        snapshot = MarketQualitySnapshot(
            state=state,
            label=label,
            score=round(final_score, 4),
            message=message,
            total_assets=agg.total_assets,
            uptrend_count=agg.uptrend_count,
            bullish_momentum_count=agg.bullish_momentum_count,
            bearish_count=agg.bearish_count,
            high_volume_count=agg.high_volume_count,
            neutral_momentum_count=agg.neutral_momentum_count,
            refined_count=agg.refined_count,
            approved_count=agg.approved_count,
            structural_block_count=agg.structural_block_count,
            avg_volume_ratio=round(agg.avg_volume_ratio, 4),
            avg_market_score=round(agg.avg_market_score, 4),
            components={
                "trend": round(trend_component, 4),
                "momentum": round(momentum_component, 4),
                "volume": round(volume_component, 4),
                "approval": round(approval_component, 4),
                "quality": round(quality_component, 4),
            },
        )

        return snapshot
