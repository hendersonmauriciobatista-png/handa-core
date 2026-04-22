# =============================================================================
# core/alo_intelligence/alo_drc_engine.py
# H&A — ALO DRC-Aware Subengine
# =============================================================================

from __future__ import annotations

from core.alo_intelligence.alo_models import ALOInput, ReentryState


class ALODRCAwareEngine:
    """
    Subcamada responsável por absorver o DRC dentro do ALO.

    Aqui avaliamos apenas a dimensão de reentrada contextual
    por ativo, sem decidir sozinho a operação.
    """

    def evaluate_reentry_state(self, alo_input: ALOInput) -> ReentryState:
        structural = alo_input.structural
        memory = alo_input.memory
        temporal = alo_input.temporal

        if structural.hard_block or structural.structural_block:
            return ReentryState.HARD_BLOCK

        if memory.stagnation_count_recent >= 2:
            return ReentryState.TEMP_BLOCK

        if memory.fast_stop_flag:
            return ReentryState.RESTRICTED

        if (
            temporal.minutes_since_last_failure is not None
            and temporal.minutes_since_last_failure < 15
            and memory.recent_failures >= 1
            and memory.stagnation_count_recent >= 1
        ):
            return ReentryState.TEMP_BLOCK

        if memory.stagnation_count_recent >= 1:
            return ReentryState.RESTRICTED

        if (
            temporal.minutes_since_last_failure is not None
            and temporal.minutes_since_last_failure < 15
            and memory.recent_failures >= 1
        ):
            return ReentryState.RESTRICTED

        return ReentryState.CLEAN