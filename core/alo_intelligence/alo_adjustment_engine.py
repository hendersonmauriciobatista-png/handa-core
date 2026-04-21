# =============================================================================
# core/alo_intelligence/alo_adjustment_engine.py
# H&A — ALO Dynamic Adjustment Engine
# =============================================================================

from __future__ import annotations

from core.alo_intelligence.alo_models import (
    ALOInput,
    BehaviorLabel,
    BehaviorProfile,
    ConfidenceLevel,
    GuidanceType,
    RankingBias,
    ReasonBundle,
    ReentryState,
    RiskBias,
)


class ALODynamicAdjustmentEngine:
    """
    Converte leitura contextual + memória + DRC-aware em guidance operacional.
    """

    def build_profile(
        self,
        alo_input: ALOInput,
        reasons: ReasonBundle,
        reentry_state: ReentryState,
    ) -> BehaviorProfile:
        technical = alo_input.technical
        memory = alo_input.memory
        web = alo_input.web
        structural = alo_input.structural

        profile = BehaviorProfile()
        profile.reentry_state = reentry_state
        profile.reason_codes = list(reasons.codes)

        if structural.hard_block or structural.structural_block:
            profile.confidence_level = ConfidenceLevel.VERY_LOW
            profile.behavior_label = BehaviorLabel.LOW_CONFIDENCE
            profile.risk_bias = RiskBias.VERY_CONSERVATIVE
            profile.ranking_bias = RankingBias.DEPRIORITIZE
            profile.guidance = GuidanceType.HARD_BLOCK
            profile.dynamic_penalty = 1.0
            return profile

        confidence_score = 0.50
        penalty = 0.0
        bonus = 0.0

        # ---------------------------------------------------------------------
        # BASE POSITIVA
        # ---------------------------------------------------------------------
        if technical.trend == "UPTREND":
            confidence_score += 0.10

        if 45.0 <= technical.rsi <= 65.0:
            confidence_score += 0.05

        if technical.selection_score >= 0.75:
            confidence_score += 0.08

        if memory.last_trade_result == "WIN":
            confidence_score += 0.04
            bonus += 0.03

        if memory.confidence_history_score >= 0.70:
            confidence_score += 0.06
            bonus += 0.04

        if web.continuation_context == "HIGH":
            confidence_score += 0.05

        # ---------------------------------------------------------------------
        # PENALIDADES
        # ---------------------------------------------------------------------
        if technical.market_state == "SIDEWAYS":
            confidence_score -= 0.08
            penalty += 0.05

        if technical.momentum == "NEUTRAL":
            confidence_score -= 0.10
            penalty += 0.06

        if technical.volume_ratio < 1.20:
            confidence_score -= 0.08
            penalty += 0.05

        if memory.stagnation_count_recent >= 1:
            confidence_score -= 0.12
            penalty += 0.10

        if memory.stagnation_count_recent >= 2:
            confidence_score -= 0.12
            penalty += 0.12

        if memory.fast_stop_flag:
            confidence_score -= 0.12
            penalty += 0.12

        if memory.loss_streak >= 2:
            confidence_score -= 0.08
            penalty += 0.08

        if web.macro_regime == "RISK_OFF":
            confidence_score -= 0.12
            penalty += 0.08

        if web.news_risk == "HIGH":
            confidence_score -= 0.10
            penalty += 0.08

        if web.asset_event_risk == "CRITICAL":
            confidence_score -= 0.20
            penalty += 0.15

        # ---------------------------------------------------------------------
        # EFEITOS DE REENTRY
        # ---------------------------------------------------------------------
        if reentry_state == ReentryState.CAUTION:
            confidence_score -= 0.08
            penalty += 0.06

        elif reentry_state == ReentryState.RESTRICTED:
            confidence_score -= 0.12
            penalty += 0.10

        elif reentry_state == ReentryState.TEMP_BLOCK:
            confidence_score -= 0.20
            penalty += 0.20

        # Clamp
        confidence_score = max(0.0, min(1.0, confidence_score))

        # ==========================================================
        # PATCH H&A — ANTI STAGNATION + ANTI FAST LOSS
        # ==========================================================
        try:
            is_sideways = (
                technical.market_state == "SIDEWAYS"
                or technical.trend == "SIDEWAYS"
            )

            weak_structure = (
                technical.selection_score < 0.60
            )

            suspicious_volume = (
                technical.volume_ratio >= 1.4
                and technical.momentum in ("BULLISH", "NEUTRAL")
            )

            if is_sideways and weak_structure:
                profile.guidance = GuidanceType.REQUIRE_STRONGER_CONFIRMATION

            elif is_sideways and suspicious_volume and technical.selection_score < 0.70:
                profile.guidance = GuidanceType.REQUIRE_STRONGER_CONFIRMATION

        except Exception:
            pass


        # ---------------------------------------------------------------------
        # CONFIDENCE LEVEL
        # ---------------------------------------------------------------------
        if confidence_score >= 0.85:
            profile.confidence_level = ConfidenceLevel.VERY_HIGH
        elif confidence_score >= 0.70:
            profile.confidence_level = ConfidenceLevel.HIGH
        elif confidence_score >= 0.50:
            profile.confidence_level = ConfidenceLevel.MEDIUM
        elif confidence_score >= 0.30:
            profile.confidence_level = ConfidenceLevel.LOW
        else:
            profile.confidence_level = ConfidenceLevel.VERY_LOW

        # ---------------------------------------------------------------------
        # BEHAVIOR LABEL
        # ---------------------------------------------------------------------
        if reentry_state == ReentryState.TEMP_BLOCK:
            profile.behavior_label = BehaviorLabel.RECENT_FAILURE
        elif memory.stagnation_count_recent >= 2 or memory.fast_stop_flag:
            profile.behavior_label = BehaviorLabel.EXHAUSTED
        elif technical.trend == "UPTREND" and technical.momentum == "NEUTRAL":
            profile.behavior_label = BehaviorLabel.WARM_BUT_WEAK
        elif technical.market_state == "SIDEWAYS" and technical.volume_ratio < 1.2:
            profile.behavior_label = BehaviorLabel.STAGNATION_RISK
        elif confidence_score >= 0.80:
            profile.behavior_label = BehaviorLabel.PREMIUM_CONTINUATION
        elif confidence_score >= 0.65:
            profile.behavior_label = BehaviorLabel.HEALTHY
        elif confidence_score < 0.30:
            profile.behavior_label = BehaviorLabel.LOW_CONFIDENCE
        else:
            profile.behavior_label = BehaviorLabel.NEUTRAL

        # ---------------------------------------------------------------------
        # RANKING / RISK BIAS
        # ---------------------------------------------------------------------
        if profile.confidence_level in {ConfidenceLevel.VERY_HIGH, ConfidenceLevel.HIGH}:
            profile.ranking_bias = RankingBias.BOOST
            profile.risk_bias = RiskBias.OPPORTUNITY_FAVORABLE
        elif profile.confidence_level == ConfidenceLevel.MEDIUM:
            profile.ranking_bias = RankingBias.KEEP
            profile.risk_bias = RiskBias.NORMAL
        elif profile.confidence_level == ConfidenceLevel.LOW:
            profile.ranking_bias = RankingBias.REDUCE
            profile.risk_bias = RiskBias.CONSERVATIVE
        else:
            profile.ranking_bias = RankingBias.DEPRIORITIZE
            profile.risk_bias = RiskBias.VERY_CONSERVATIVE

        # Override if reentry is restricted
        if reentry_state == ReentryState.RESTRICTED:
            profile.risk_bias = RiskBias.VERY_CONSERVATIVE
            profile.ranking_bias = RankingBias.REDUCE

        if reentry_state == ReentryState.TEMP_BLOCK:
            profile.risk_bias = RiskBias.VERY_CONSERVATIVE
            profile.ranking_bias = RankingBias.DEPRIORITIZE

        # ---------------------------------------------------------------------
        # GUIDANCE
        # ---------------------------------------------------------------------
        if profile.guidance == GuidanceType.REQUIRE_STRONGER_CONFIRMATION:
            pass
        elif reentry_state == ReentryState.HARD_BLOCK:
            profile.guidance = GuidanceType.HARD_BLOCK
        elif reentry_state == ReentryState.TEMP_BLOCK:
            profile.guidance = GuidanceType.TEMPORARY_BLOCK
        elif profile.confidence_level in {ConfidenceLevel.VERY_LOW, ConfidenceLevel.LOW}:
            profile.guidance = GuidanceType.REQUIRE_STRONGER_CONFIRMATION
        elif reentry_state == ReentryState.CAUTION:
            profile.guidance = GuidanceType.ALLOW_WITH_CAUTION
        elif profile.confidence_level in {ConfidenceLevel.HIGH, ConfidenceLevel.VERY_HIGH}:
            profile.guidance = GuidanceType.ALLOW
        else:
            profile.guidance = GuidanceType.ALLOW_WITH_CAUTION

        profile.dynamic_penalty = round(penalty, 4)
        profile.dynamic_bonus = round(bonus, 4)

        return profile