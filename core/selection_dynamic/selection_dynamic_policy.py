# =============================================================================
# core/selection_dynamic/selection_dynamic_policy.py
# H&A — Selection Dynamic Policy Engine
# =============================================================================

from core.selection_dynamic.market_regime_mapper import MarketRegimeMapper
from core.selection_dynamic.dynamic_thresholds import DynamicThresholdProvider
from core.selection_dynamic.selection_dynamic_models import (
    DynamicMarketContext,
    DynamicSelectionResult,
)
from core.selection_dynamic.policy_modes import SelectionPolicyMode


class SelectionDynamicPolicy:
    """
    Camada dinâmica que ajusta a régua da seleção com base no mercado.
    """

    def __init__(self):
        self.mapper = MarketRegimeMapper()
        self.thresholds = DynamicThresholdProvider()

    def evaluate(self, data, final_score: float, market_context: dict) -> DynamicSelectionResult:
        """
        data = SelectionInput
        final_score = score calculado pelo SelectionPolicyEngine
        market_context = contexto macro (MQII + Liquidez)
        """

        # ======================================================
        # 1. MAPEAR MODO
        # ======================================================
        mode = self.mapper.map_mode(market_context)

        # ======================================================
        # 2. OBTER PERFIL DINÂMICO
        # ======================================================
        profile = self.thresholds.get_profile(mode)

        trend = str(data.trend).strip().upper()
        momentum = str(data.momentum).strip().upper()
        market_state = str(data.market_state).strip().upper()
        volume = float(data.volume_ratio)

        # ======================================================
        # PATCH H&A — TREND MODE CONTEXTUAL v1
        # ======================================================
        # Permite entrada controlada em continuação de tendência
        # quando o mercado está saudável, mesmo com momentum NEUTRAL.
        #
        # NÃO libera:
        # - volume baixo
        # - RSI extremo
        # - tendência lateral
        # - mercado sem contexto forte
        # ======================================================

        mqii_state = str(market_context.get("mqii_state", "")).strip().upper()
        avg_volume_ratio = float(market_context.get("avg_volume_ratio", 0.0) or 0.0)
        approved_count = int(market_context.get("approved_count", 0) or 0)
        uptrend_count = int(market_context.get("uptrend_count", 0) or 0)
        rsi = float(getattr(data, "rsi", 0.0) or 0.0)

        is_contextual_trend_entry = (
            mqii_state == "TRADE_OK"
            and trend == "UPTREND"
            and momentum == "NEUTRAL"
            and market_state == "SIDEWAYS"
            and volume >= 1.10
            and avg_volume_ratio >= 1.50
            and approved_count >= 3
            and uptrend_count >= 15
            and 45.0 <= rsi <= 65.0
        )

        if is_contextual_trend_entry:
            min_score = min(profile.min_score_uptrend_neutral, 0.55)
            approved = final_score >= min_score

            return DynamicSelectionResult(
                mode=mode,
                approved=approved,
                reason="TREND_CONTEXT_ENTRY_OK" if approved else "TREND_CONTEXT_SCORE_LOW",
                min_score_required=min_score,
            )

        # ======================================================
        # 3. BLOQUEIOS DIRETOS (ENTRY QUALITY)
        # ======================================================

        # ❌ Bloqueio clássico: lateral fraco
        if (
            trend == "UPTREND"
            and momentum != "BULLISH"
            and market_state == "SIDEWAYS"
            and volume < profile.min_volume_sideways
        ):
            return DynamicSelectionResult(
                mode=mode,
                approved=False,
                reason="BLOCK_SIDEWAYS_WEAK",
                min_score_required=profile.min_score_other,
            )

                # ❌ Bloqueio: momentum neutro fraco
        if momentum == "NEUTRAL":

            # ======================================================
            # 🔥 H&A PATCH — NEUTRAL PREMIUM SELECTION LIBERATION
            # ======================================================
            neutral_premium = (
                trend == "UPTREND"
                and market_state in ("SIDEWAYS", "CAUTIOUS")
                and volume >= 1.6
                and 40.0 <= rsi <= 60.0
                and final_score >= 0.60
            )

            if neutral_premium:
                return DynamicSelectionResult(
                    mode=mode,
                    approved=True,
                    reason="NEUTRAL_PREMIUM_SELECTION_OK",
                    min_score_required=0.62,
                )

            if not profile.allow_neutral_entries:
                return DynamicSelectionResult(
                    mode=mode,
                    approved=False,
                    reason="BLOCK_NEUTRAL_MODE",
                    min_score_required=profile.min_score_uptrend_neutral,
                )

            if volume < profile.min_volume_neutral:
                return DynamicSelectionResult(
                    mode=mode,
                    approved=False,
                    reason="BLOCK_NEUTRAL_LOW_VOLUME",
                    min_score_required=profile.min_score_uptrend_neutral,
                )

        # ❌ Bloqueio de sideways (se não permitido)
        if market_state == "SIDEWAYS" and not profile.allow_sideways_entries:
            return DynamicSelectionResult(
                mode=mode,
                approved=False,
                reason="BLOCK_SIDEWAYS_MODE",
                min_score_required=profile.min_score_other,
            )

        # ======================================================
        # 4. DEFINIÇÃO DE SCORE MÍNIMO
        # ======================================================

        if trend == "UPTREND" and momentum == "BULLISH":
            min_score = profile.min_score_uptrend_bullish

        elif trend == "UPTREND" and momentum == "NEUTRAL":
            min_score = profile.min_score_uptrend_neutral

        else:
            min_score = profile.min_score_other

        # ======================================================
        # 5. DECISÃO FINAL
        # ======================================================

        approved = final_score >= min_score

        return DynamicSelectionResult(
            mode=mode,
            approved=approved,
            reason="SCORE_OK" if approved else "SCORE_BELOW_DYNAMIC_MIN",
            min_score_required=min_score,
        )