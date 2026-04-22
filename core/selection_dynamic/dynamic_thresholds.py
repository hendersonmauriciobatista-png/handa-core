# =============================================================================
# core/selection_dynamic/dynamic_thresholds.py
# H&A — Dynamic Threshold Definitions
# =============================================================================

from dataclasses import dataclass

from core.selection_dynamic.policy_modes import SelectionPolicyMode


@dataclass
class DynamicThresholdProfile:
    mode: SelectionPolicyMode

    # score mínimo por tipo de setup
    min_score_uptrend_bullish: float
    min_score_uptrend_neutral: float
    min_score_other: float

    # gates de contexto
    allow_neutral_entries: bool
    allow_sideways_entries: bool

    # exigência mínima de volume
    min_volume_neutral: float
    min_volume_sideways: float


class DynamicThresholdProvider:
    """
    Retorna o perfil de thresholds conforme o modo atual da policy.
    """

    def get_profile(self, mode: SelectionPolicyMode) -> DynamicThresholdProfile:

        # ======================================================
        # DEFENSIVE
        # ======================================================
        if mode == SelectionPolicyMode.DEFENSIVE:
            return DynamicThresholdProfile(
                mode=mode,
                min_score_uptrend_bullish=0.45,
                min_score_uptrend_neutral=0.90,
                min_score_other=0.95,
                allow_neutral_entries=False,
                allow_sideways_entries=False,
                min_volume_neutral=1.50,
                min_volume_sideways=1.60,
            )

        # ======================================================
        # BALANCED
        # ======================================================
        if mode == SelectionPolicyMode.BALANCED:
            return DynamicThresholdProfile(
                mode=mode,
                min_score_uptrend_bullish=0.35,
                min_score_uptrend_neutral=0.65,
                min_score_other=0.80,
                allow_neutral_entries=True,
                allow_sideways_entries=False,
                min_volume_neutral=1.25,
                min_volume_sideways=1.40,
            )

        # ======================================================
        # OPPORTUNITY
        # ======================================================
        return DynamicThresholdProfile(
            mode=mode,
            min_score_uptrend_bullish=0.28,
            min_score_uptrend_neutral=0.55,
            min_score_other=0.70,
            allow_neutral_entries=True,
            allow_sideways_entries=True,
            min_volume_neutral=1.10,
            min_volume_sideways=1.20,
        )