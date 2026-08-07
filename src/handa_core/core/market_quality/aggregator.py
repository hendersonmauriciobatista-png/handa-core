# ============================================================
# core/market_quality/aggregator.py
# MQII — Market Quality Internal Indicator
# Aggregator oficial v1.0
# ============================================================

from typing import List, Optional

from core.market_quality.models import MarketQualityAggregate


class MarketQualityAggregator:
    """
    Responsável por transformar os dados brutos do radar em
    métricas agregadas de qualidade de mercado.
    """

    def _safe_upper(self, value) -> str:
        if value is None:
            return ""

        try:
            if hasattr(value, "value"):
                return str(value.value).strip().upper()
            return str(value).strip().upper()
        except Exception:
            return ""

    def _to_float(self, value, default=0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _extract_analysis(self, item: dict) -> dict:
        if not isinstance(item, dict):
            return {}
        return item.get("analysis") or {}

    def aggregate(
        self,
        all_analyses: Optional[List[dict]],
        refined_tokens: Optional[List[dict]],
        approved_tokens: Optional[List[dict]],
    ) -> MarketQualityAggregate:
        aggregate = MarketQualityAggregate()

        all_analyses = all_analyses or []
        refined_tokens = refined_tokens or []
        approved_tokens = approved_tokens or []

        aggregate.total_assets = len(all_analyses)
        aggregate.refined_count = len(refined_tokens)
        aggregate.approved_count = len(approved_tokens)

        volume_sum = 0.0
        market_score_sum = 0.0
        volume_count = 0
        market_score_count = 0

        for item in all_analyses:
            analysis = self._extract_analysis(item)

            trend = self._safe_upper(analysis.get("trend"))
            momentum = self._safe_upper(analysis.get("momentum"))
            market_state = self._safe_upper(analysis.get("market_state"))
            volume_state = self._safe_upper(analysis.get("volume"))

            volume_ratio = self._to_float(analysis.get("volume_ratio"), default=0.0)
            market_score = self._to_float(analysis.get("market_score"), default=0.0)

            if trend in ("UPTREND", "STRONG_UPTREND"):
                aggregate.uptrend_count += 1

            if momentum in ("BULLISH", "STRONG_BULLISH"):
                aggregate.bullish_momentum_count += 1

            if momentum == "NEUTRAL":
                aggregate.neutral_momentum_count += 1

            if (
                trend in ("DOWNTREND", "STRONG_DOWNTREND")
                or momentum in ("BEARISH", "STRONG_BEARISH")
                or market_state in ("BEARISH", "BEARISH_STRONG")
            ):
                aggregate.bearish_count += 1

            if volume_state == "HIGH" or volume_ratio >= 1.0:
                aggregate.high_volume_count += 1

            volume_sum += volume_ratio
            volume_count += 1

            market_score_sum += market_score
            market_score_count += 1

        if volume_count > 0:
            aggregate.avg_volume_ratio = volume_sum / volume_count

        if market_score_count > 0:
            aggregate.avg_market_score = market_score_sum / market_score_count

        # --------------------------------------------------------
        # structural_block_count:
        # estimado com base nos aprovados/refinados que já passaram
        # pelo pipeline do radar/selection. Aqui mantemos seguro e
        # sem inventar leitura estrutural fora do fluxo real.
        # --------------------------------------------------------
        structural_block_symbols = set()

        for item in refined_tokens:
            if not isinstance(item, dict):
                continue

            symbol = str(item.get("symbol", "")).strip().upper()
            if not symbol:
                continue

            analysis = self._extract_analysis(item)
            trend = self._safe_upper(analysis.get("trend"))
            momentum = self._safe_upper(analysis.get("momentum"))
            market_state = self._safe_upper(analysis.get("market_state"))

            if trend == "STRUCTURAL_BLOCK":
                structural_block_symbols.add(symbol)
            elif momentum == "STRUCTURAL_BLOCK":
                structural_block_symbols.add(symbol)
            elif market_state == "STRUCTURAL_BLOCK":
                structural_block_symbols.add(symbol)

        aggregate.structural_block_count = len(structural_block_symbols)

        return aggregate
