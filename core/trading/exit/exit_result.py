# ============================================================
# core/trading/exit/exit_result.py
# H&A - ExitResult Estruturado
# Política Oficial Operação Autônoma v1.0 (Perfil Moderado)
# ============================================================

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .exit_decision import ExitDecision


@dataclass(frozen=True)
class ExitResult:
    """
    Resultado estruturado retornado pelo ExitEngine.
    Não executa ordens. Apenas descreve a decisão.
    """

    decision: ExitDecision
    reason: str
    pnl_percent: float
    trailing_stop_price: Optional[float]
    highest_price: float
    risk_blocked: bool
    timestamp: datetime

    def is_exit(self) -> bool:
        """
        True se a decisão representar saída (SELL ou BLOCK).
        """
        return self.decision.is_sell() or self.decision.is_block()

    def is_hold(self) -> bool:
        """
        True se nenhuma saída foi acionada.
        """
        return self.decision == ExitDecision.HOLD