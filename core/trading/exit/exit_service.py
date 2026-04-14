# ============================================================
# core/trading/exit/exit_service.py
# H&A - ExitService v1.0
# Orquestrador institucional de saída
# ============================================================

from typing import Dict, Any

from core.trading.context.trade_context_builder import TradeContextBuilder
from .exit_engine import ExitEngine
from .exit_result import ExitResult


class ExitService:
    """
    Orquestra a construção do TradeContext e
    delega decisão ao ExitEngine.

    Não executa ordens.
    Não calcula indicadores.
    Não altera política.
    """

    def __init__(self, engine: ExitEngine | None = None):
        self._engine = engine or ExitEngine()

    def evaluate(
        self,
        symbol: str,
        position_data: Dict[str, Any],
        indicator_data: Dict[str, Any],
        risk_data: Dict[str, Any],
    ) -> ExitResult:
        """
        Constrói TradeContext via Builder
        e delega decisão ao ExitEngine.
        """

        context = TradeContextBuilder.build(
            symbol=symbol,
            position_data=position_data,
            indicator_data=indicator_data,
            risk_data=risk_data,
        )

        return self._engine.evaluate(context)