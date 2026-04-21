# =============================================================================
# core/alo_intelligence/alo_explainer.py
# H&A — ALO Explainability Builder
# =============================================================================

from __future__ import annotations

from core.alo_intelligence.alo_models import ALOInput, BehaviorProfile


class ALOExplainer:
    """
    Gera texto auditável e rastreável para logs e observabilidade.
    """

    def build_explainability_text(
        self,
        alo_input: ALOInput,
        profile: BehaviorProfile,
    ) -> str:
        parts = [f"{alo_input.symbol}"]

        parts.append(f"confidence={profile.confidence_level.value}")
        parts.append(f"guidance={profile.guidance.value}")
        parts.append(f"behavior={profile.behavior_label.value}")
        parts.append(f"reentry={profile.reentry_state.value}")

        if profile.reason_codes:
            parts.append(f"reasons={','.join(profile.reason_codes)}")

        return " | ".join(parts)