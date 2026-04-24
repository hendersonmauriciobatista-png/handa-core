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

        # ------------------------------------------------------
        # PATCH DRC v2 — REPETIÇÃO DO MESMO ATIVO
        # ------------------------------------------------------

        same_symbol_trades = int(getattr(memory, "same_symbol_recent_trades", 0) or 0)
        same_symbol_failures = int(getattr(memory, "same_symbol_recent_failures", 0) or 0)
        last_trade_result = str(getattr(memory, "last_trade_result", "") or "").upper()
        minutes_since_last_failure = getattr(temporal, "minutes_since_last_failure", None)

        # 1) Mesmo ativo já falhou 2x recentemente -> block forte
        if same_symbol_failures >= 2:
            return ReentryState.TEMP_BLOCK

        # 2) STOP rápido / fast stop continua sendo restrição forte
        if memory.fast_stop_flag:
            return ReentryState.RESTRICTED

        # 3) Mesmo ativo já operado várias vezes em sequência -> restringe
        if same_symbol_trades >= 2:
            return ReentryState.RESTRICTED

        # 4) Falha recente + mesmo ativo insistido -> bloqueio temporário
        if (
            minutes_since_last_failure is not None
            and minutes_since_last_failure < 20
            and same_symbol_failures >= 1
        ):
            return ReentryState.TEMP_BLOCK

        # 5) Stagnation repetida continua sendo block
        if memory.stagnation_count_recent >= 2:
            return ReentryState.TEMP_BLOCK

        # 6) Uma stagnation recente -> pelo menos restringe
        if memory.stagnation_count_recent >= 1:
            return ReentryState.RESTRICTED

        # 7) Falha recente genérica -> cautela
        if (
            minutes_since_last_failure is not None
           and minutes_since_last_failure < 15
           and memory.recent_failures >= 1
        ):
           return ReentryState.CAUTION

        # 8) Win pequeno seguido de insistência no mesmo ativo -> restringe
        if last_trade_result == "WIN" and same_symbol_trades >= 1:
            return ReentryState.CAUTION

        return ReentryState.CLEAN