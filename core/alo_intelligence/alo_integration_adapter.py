# =============================================================================
# core/alo_intelligence/alo_integration_adapter.py
# H&A — ALO Integration Adapter
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass

from core.alo_intelligence.alo_models import (
    ALOGuidance,
    GuidanceType,
    RankingBias,
    RiskBias,
)


@dataclass
class ALOAdjustedDecisionInput:
    adjusted_selection_score: float
    require_stronger_confirmation: bool
    temporary_block: bool
    hard_block: bool
    risk_bias: str
    ranking_bias: str


class ALOIntegrationAdapter:
    """
    Adapta o guidance do ALO para consumo por Ranking / Risk / Decision.
    """

    def apply_to_selection_score(
        self,
        original_score: float,
        guidance: ALOGuidance,
    ) -> float:
        score = original_score

        score += guidance.dynamic_bonus
        score -= guidance.dynamic_penalty

        if guidance.ranking_bias == RankingBias.BOOST:
            score += 0.03
        elif guidance.ranking_bias == RankingBias.REDUCE:
            score -= 0.05
        elif guidance.ranking_bias == RankingBias.DEPRIORITIZE:
            score -= 0.10

        return round(max(0.0, min(1.0, score)), 4)

    def adapt(
        self,
        original_score: float,
        guidance: ALOGuidance,
    ) -> ALOAdjustedDecisionInput:
        adjusted_score = self.apply_to_selection_score(original_score, guidance)

        return ALOAdjustedDecisionInput(
            adjusted_selection_score=adjusted_score,
            require_stronger_confirmation=(
                guidance.guidance == GuidanceType.REQUIRE_STRONGER_CONFIRMATION
            ),
            temporary_block=(guidance.guidance == GuidanceType.TEMPORARY_BLOCK),
            hard_block=(guidance.guidance == GuidanceType.HARD_BLOCK),
            risk_bias=guidance.risk_bias.value if isinstance(guidance.risk_bias, RiskBias) else str(guidance.risk_bias),
            ranking_bias=guidance.ranking_bias.value if isinstance(guidance.ranking_bias, RankingBias) else str(guidance.ranking_bias),
        )