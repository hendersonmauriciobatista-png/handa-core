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

        trend = str(data.trend).upper()
        momentum = str(data.momentum).upper()
        market_state = str(data.market_state).upper()
        volume = float(data.volume_ratio)

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