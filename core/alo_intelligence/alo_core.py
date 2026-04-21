# =============================================================================
# core/alo_intelligence/alo_core.py
# H&A — ALO Intelligent Core
# =============================================================================

from __future__ import annotations

import logging
from typing import Optional

from core.alo_intelligence.alo_adjustment_engine import ALODynamicAdjustmentEngine
from core.alo_intelligence.alo_collector import ALOCollector
from core.alo_intelligence.alo_drc_engine import ALODRCAwareEngine
from core.alo_intelligence.alo_explainer import ALOExplainer
from core.alo_intelligence.alo_interpreter import ALOContextInterpreter
from core.alo_intelligence.alo_models import (
    ALOGuidance,
    ALOInput,
    ALOMode,
    MacroMarketContext,
    MemoryContext,
    StructuralContext,
    TechnicalContext,
    TemporalContext,
    WebContext,
)

logger = logging.getLogger(__name__)


class ALOIntelligentCore:
    """
    Núcleo central do ALO Inteligente.

    Responsabilidades:
    - consolidar contexto
    - interpretar o símbolo
    - avaliar reentrada contextual (DRC-aware)
    - produzir guidance auditável

    Não executa ordens.
    """

    def __init__(self, mode: ALOMode = ALOMode.ADVISORY) -> None:
        self.mode = mode
        self.collector = ALOCollector()
        self.interpreter = ALOContextInterpreter()
        self.drc_engine = ALODRCAwareEngine()
        self.adjustment_engine = ALODynamicAdjustmentEngine()
        self.explainer = ALOExplainer()

    def evaluate(
        self,
        symbol: str,
        technical: TechnicalContext,
        macro: MacroMarketContext,
        memory: Optional[MemoryContext] = None,
        temporal: Optional[TemporalContext] = None,
        structural: Optional[StructuralContext] = None,
        web: Optional[WebContext] = None,
    ) -> ALOGuidance:
        alo_input: ALOInput = self.collector.build_input(
            symbol=symbol,
            technical=technical,
            macro=macro,
            memory=memory,
            temporal=temporal,
            structural=structural,
            web=web,
        )

        reasons = self.interpreter.interpret(alo_input)
        reentry_state = self.drc_engine.evaluate_reentry_state(alo_input)
        profile = self.adjustment_engine.build_profile(alo_input, reasons, reentry_state)
        explainability_text = self.explainer.build_explainability_text(alo_input, profile)

        guidance = ALOGuidance(
            symbol=symbol,
            confidence_level=profile.confidence_level,
            behavior_label=profile.behavior_label,
            reentry_state=profile.reentry_state,
            dynamic_penalty=profile.dynamic_penalty,
            dynamic_bonus=profile.dynamic_bonus,
            risk_bias=profile.risk_bias,
            ranking_bias=profile.ranking_bias,
            guidance=profile.guidance,
            reason_codes=profile.reason_codes,
            explainability_text=explainability_text,
        )

        logger.info("[ALO CORE] %s", guidance.explainability_text)
        return guidance