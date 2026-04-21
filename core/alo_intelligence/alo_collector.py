# =============================================================================
# core/alo_intelligence/alo_collector.py
# H&A — ALO Intelligent Collector
# =============================================================================

from __future__ import annotations

from typing import Optional

from core.alo_intelligence.alo_models import (
    ALOInput,
    MacroMarketContext,
    MemoryContext,
    StructuralContext,
    TechnicalContext,
    TemporalContext,
    WebContext,
)


class ALOCollector:
    """
    Responsável por consolidar todos os contextos necessários
    para avaliação do ALO Inteligente.

    Esta classe não decide. Apenas normaliza e consolida entradas.
    """

    def build_input(
        self,
        symbol: str,
        technical: TechnicalContext,
        macro: MacroMarketContext,
        memory: Optional[MemoryContext] = None,
        temporal: Optional[TemporalContext] = None,
        structural: Optional[StructuralContext] = None,
        web: Optional[WebContext] = None,
    ) -> ALOInput:
        return ALOInput(
            symbol=symbol,
            technical=technical,
            macro=macro,
            memory=memory or MemoryContext(),
            temporal=temporal or TemporalContext(),
            structural=structural or StructuralContext(),
            web=web or WebContext(),
        )