# =============================================================================
# core/alo_intelligence/alo_interpreter.py
# H&A — ALO Intelligent Context Interpreter
# =============================================================================

from __future__ import annotations

from core.alo_intelligence.alo_models import ALOInput, ReasonBundle


class ALOContextInterpreter:
    """
    Traduz os dados brutos em sinais interpretáveis.
    Não produz a decisão final; apenas constrói leitura contextual.
    """

    def interpret(self, alo_input: ALOInput) -> ReasonBundle:
        reasons = ReasonBundle()

        technical = alo_input.technical
        memory = alo_input.memory
        structural = alo_input.structural
        web = alo_input.web

        if structural.hard_block or structural.structural_block:
            reasons.add("STRUCTURAL_BLOCK")

        if technical.trend == "UPTREND":
            reasons.add("UPTREND_STRUCTURE")

        if technical.market_state == "SIDEWAYS":
            reasons.add("SIDEWAYS_MARKET_STATE")

        if technical.momentum == "NEUTRAL":
            reasons.add("MOMENTUM_NEUTRAL")

        if technical.volume_ratio < 1.20:
            reasons.add("LOW_VOLUME_CONFIRMATION")

        if memory.stagnation_count_recent >= 1:
            reasons.add("STAGNATION_RECENT")

        if memory.stagnation_count_recent >= 2:
            reasons.add("REPEATED_STAGNATION")

        if memory.fast_stop_flag:
            reasons.add("RAPID_STOP_RECENT")

        if memory.loss_streak >= 2:
            reasons.add("LOSS_STREAK_ACTIVE")

        if web.macro_regime == "RISK_OFF":
            reasons.add("WEB_RISK_OFF")

        if web.news_risk in {"MODERATE", "HIGH"}:
            reasons.add("WEB_NEWS_RISK")

        if web.asset_event_risk in {"WATCH", "CRITICAL"}:
            reasons.add("WEB_ASSET_EVENT_RISK")

        if memory.last_trade_result == "WIN":
            reasons.add("RECENT_WIN_CONTEXT")

        return reasons