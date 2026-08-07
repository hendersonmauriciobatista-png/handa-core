# ============================================================
# H&A - Policy Layer
# Motor principal de decisão do sistema
# ============================================================

from core.decision.trade_context import TradeContext
from core.decision.decision_result import DecisionResult, DecisionAction


class PolicyLayer:

    TAKE_PROFIT_PERCENT = 0.45
    STOP_LOSS_PERCENT = -0.35

    @staticmethod
    def evaluate(context: TradeContext) -> DecisionResult:
        """
        Avalia o contexto do trade e retorna uma decisão.
        """

        # ----------------------------------------------------
        # 1 - Proteção de risco global
        # ----------------------------------------------------
        if context.draining_mode_active:
            return DecisionResult(
                action=DecisionAction.BLOCK,
                reason="DRAINING_MODE_ACTIVE",
                confidence=1.0
            )

        # ----------------------------------------------------
        # 2 - Take Profit
        # ----------------------------------------------------
        if context.unrealized_pnl_percent >= PolicyLayer.TAKE_PROFIT_PERCENT:
            return DecisionResult(
                action=DecisionAction.SELL,
                reason="TAKE_PROFIT",
                confidence=1.0
            )

        # ----------------------------------------------------
        # 3 - Stop Loss
        # ----------------------------------------------------
        if context.unrealized_pnl_percent <= PolicyLayer.STOP_LOSS_PERCENT:
            return DecisionResult(
                action=DecisionAction.SELL,
                reason="STOP_LOSS",
                confidence=1.0
            )

        # ----------------------------------------------------
        # 4 - Reversão técnica
        # ----------------------------------------------------
        if (
            context.ema_10 < context.ema_20
            and context.rsi_14 < 45
        ):
            return DecisionResult(
                action=DecisionAction.SELL,
                reason="TECHNICAL_REVERSAL",
                confidence=0.9
            )

        # ----------------------------------------------------
        # 5 - Caso padrão: manter posição
        # ----------------------------------------------------
        return DecisionResult(
            action=DecisionAction.HOLD,
            reason="NO_SIGNAL",
            confidence=0.5
        )