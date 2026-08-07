# ============================================================
# core/trading/exit/exit_decision.py
# H&A - ExitDecision Enum
# Política Oficial Operação Autônoma v1.0 (Perfil Moderado)
# ============================================================

from enum import Enum


class ExitDecision(Enum):
    """
    Enum oficial de decisões do ExitEngine.
    Nenhuma decisão fora desta lista é permitida.
    """

    HOLD = "hold"

    SELL_TP = "sell_take_profit"
    SELL_SL = "sell_stop_loss"
    SELL_TRAILING = "sell_trailing"
    SELL_REVERSAL = "sell_reversal"

    BLOCK_RISK = "block_risk"

    def is_sell(self) -> bool:
        """
        Retorna True se a decisão for de venda.
        """
        return self in {
            ExitDecision.SELL_TP,
            ExitDecision.SELL_SL,
            ExitDecision.SELL_TRAILING,
            ExitDecision.SELL_REVERSAL,
        }

    def is_block(self) -> bool:
        """
        Retorna True se a decisão for bloqueio por risco.
        """
        return self == ExitDecision.BLOCK_RISK