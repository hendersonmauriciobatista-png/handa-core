# ============================================================
# core/market/market_liquidity_analyzer.py
# H&A — Market Liquidity Analyzer
# ============================================================


class MarketLiquidityAnalyzer:
    """
    Analisa o estado geral de liquidez do mercado com base nos dados
    já coletados pelo radar.
    """

    def __init__(self):
        print("MarketLiquidityAnalyzer iniciado")

    # ========================================================
    # CÁLCULO PRINCIPAL
    # ========================================================

    def analyze(
        self,
        all_analyses,
        refined_tokens,
        approved_tokens,
        market_snapshot=None,
    ):
        """
        all_analyses: lista completa do scanner
        refined_tokens: lista pós-refine
        approved_tokens: lista final aprovada
        """

        total = len(all_analyses)

        if total == 0:
            return self._empty_state()

        # ----------------------------------------------------
        # CONTADORES
        # ----------------------------------------------------
        uptrend_count = 0
        volume_sum = 0.0
        volume_samples = 0

        for token in all_analyses:

            analysis = token.get("analysis", {})

            trend = self._get_enum_value(analysis.get("trend"))
            volume_ratio = self._safe_float(analysis.get("volume_ratio", 0))

            if trend == "UPTREND":
                uptrend_count += 1

            volume_sum += volume_ratio
            volume_samples += 1

        avg_volume_ratio = volume_sum / volume_samples if volume_samples else 0.0

        if market_snapshot:
            refined_count = int(market_snapshot.get("refined_count", 0) or 0)
            approved_count = int(market_snapshot.get("approved_count", 0) or 0)
            avg_volume_ratio = self._safe_float(
                market_snapshot.get("avg_volume_ratio", avg_volume_ratio),
                avg_volume_ratio,
            )
            uptrend_count = int(
                market_snapshot.get("uptrend_count", uptrend_count) or uptrend_count
            )
        else:
            refined_count = len(refined_tokens)
            approved_count = len(approved_tokens)

        # ----------------------------------------------------
        # COMPONENTES DO SCORE
        # ----------------------------------------------------

        volume_component = min(avg_volume_ratio / 1.5, 1.0)

        trend_component = min(uptrend_count / 8, 1.0)

        refined_component = min(refined_count / 5, 1.0)

        approved_component = min(approved_count / 3, 1.0)

        # ----------------------------------------------------
        # SCORE FINAL
        # ----------------------------------------------------
        liquidity_score = (
            volume_component * 0.45
            + trend_component * 0.25
            + refined_component * 0.20
            + approved_component * 0.10
        )

        liquidity_score = max(min(liquidity_score, 1.0), 0.0)

        label, message = self._classify(liquidity_score)

        return {
            "liquidity_score": round(liquidity_score, 4),
            "liquidity_label": label,
            "liquidity_message": message,
            "avg_volume_ratio": round(avg_volume_ratio, 4),
            "uptrend_count": uptrend_count,
            "refined_count": refined_count,
            "approved_count": approved_count,
        }

    # ========================================================
    # CLASSIFICAÇÃO
    # ========================================================

    def _classify(self, score):

        if score < 0.20:
            return "MUITO BAIXA", "Mercado sem liquidez. H&A em modo de preservação."

        elif score < 0.40:
            return "BAIXA", "Liquidez fraca. Operações com alta seletividade."

        elif score < 0.60:
            return "MODERADA", "Mercado em formação. Monitorando oportunidades."

        elif score < 0.80:
            return "ALTA", "Liquidez saudável. Mercado operável."

        else:
            return "MUITO ALTA", "Fluxo intenso. Atenção a excessos."

    # ========================================================
    # HELPERS
    # ========================================================

    def _get_enum_value(self, value):
        return getattr(value, "value", value)

    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default

    def _empty_state(self):
        return {
            "liquidity_score": 0.0,
            "liquidity_label": "SEM DADOS",
            "liquidity_message": "Sem dados suficientes.",
            "avg_volume_ratio": 0.0,
            "uptrend_count": 0,
            "refined_count": 0,
            "approved_count": 0,
        }
