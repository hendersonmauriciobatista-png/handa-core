# ============================================================
# core/trading/exit/exit_engine.py
# H&A - ExitEngine v1.0
# Política Oficial Operação Autônoma v1.0 (Perfil Moderado)
# ============================================================

from datetime import datetime
from typing import Optional

from .exit_decision import ExitDecision
from .exit_result import ExitResult
from .trade_context import TradeContext


class ExitEngine:
    """
    Motor institucional de decisão de saída.
    Não executa ordens.
    Não acessa API.
    Apenas analisa TradeContext e retorna ExitResult.
    """

    # --- Política Oficial v1.0 ---
    STOP_LOSS_PERCENT = -0.35
    TAKE_PROFIT_PERCENT = 0.45
    BREAK_EVEN_TRIGGER = 0.35

    TRAILING_ATR_FACTOR = 0.8
    TRAILING_MIN_PERCENT = 0.20
    TRAILING_MAX_PERCENT = 0.60

    MAX_CONSECUTIVE_LOSSES = 3
    MAX_DAILY_DRAWDOWN_PERCENT = 3.0

    def evaluate(self, context: TradeContext) -> ExitResult:

        now = datetime.utcnow()

        # ====================================================
        # 1️⃣ BLOCK_RISK
        # ====================================================
        if (
            context.draining_mode_active
            or context.consecutive_losses >= self.MAX_CONSECUTIVE_LOSSES
            or context.daily_drawdown_percent > self.MAX_DAILY_DRAWDOWN_PERCENT
        ):
            return ExitResult(
                decision=ExitDecision.BLOCK_RISK,
                reason="Risco global excedido",
                pnl_percent=context.unrealized_pnl_percent,
                trailing_stop_price=None,
                highest_price=context.highest_price,
                risk_blocked=True,
                timestamp=now,
            )

        pnl = context.unrealized_pnl_percent

        # ====================================================
        # 2️⃣ SELL_SL (proteção estrutural)
        # ====================================================
        if pnl <= self.STOP_LOSS_PERCENT:
            return ExitResult(
                decision=ExitDecision.SELL_SL,
                reason="Stop Loss estrutural acionado",
                pnl_percent=pnl,
                trailing_stop_price=None,
                highest_price=context.highest_price,
                risk_blocked=False,
                timestamp=now,
            )

        # ====================================================
        # 3️⃣ SELL_TRAILING (se lucro protegido)
        # ====================================================
        trailing_price = self._calculate_trailing(context)

        if trailing_price is not None:
            if context.current_price <= trailing_price:
                return ExitResult(
                    decision=ExitDecision.SELL_TRAILING,
                    reason="Trailing Stop acionado",
                    pnl_percent=pnl,
                    trailing_stop_price=trailing_price,
                    highest_price=context.highest_price,
                    risk_blocked=False,
                    timestamp=now,
                )

        # ====================================================
        # 4️⃣ SELL_REVERSAL (se ainda não protegido)
        # ====================================================
        if pnl < self.BREAK_EVEN_TRIGGER and self._is_reversal(context):
            return ExitResult(
                decision=ExitDecision.SELL_REVERSAL,
                reason="Inversão técnica detectada",
                pnl_percent=pnl,
                trailing_stop_price=None,
                highest_price=context.highest_price,
                risk_blocked=False,
                timestamp=now,
            )

        # ====================================================
        # 5️⃣ SELL_TP (alvo mínimo garantido)
        # ====================================================
        if pnl >= self.TAKE_PROFIT_PERCENT:
            return ExitResult(
                decision=ExitDecision.SELL_TP,
                reason="Take Profit mínimo atingido",
                pnl_percent=pnl,
                trailing_stop_price=None,
                highest_price=context.highest_price,
                risk_blocked=False,
                timestamp=now,
            )

        # ====================================================
        # 6️⃣ HOLD
        # ====================================================
        return ExitResult(
            decision=ExitDecision.HOLD,
            reason="Nenhuma condição de saída atendida",
            pnl_percent=pnl,
            trailing_stop_price=trailing_price,
            highest_price=context.highest_price,
            risk_blocked=False,
            timestamp=now,
        )

    # ========================================================
    # 🔹 Métodos Internos
    # ========================================================

    def _calculate_trailing(self, context: TradeContext) -> Optional[float]:
        """
        Calcula trailing stop adaptativo baseado em ATR.
        Só ativa após break-even.
        """

        if context.unrealized_pnl_percent < self.BREAK_EVEN_TRIGGER:
            return None

        atr_distance = context.atr_14 * self.TRAILING_ATR_FACTOR
        atr_percent = (atr_distance / context.current_price) * 100

        atr_percent = max(self.TRAILING_MIN_PERCENT, atr_percent)
        atr_percent = min(self.TRAILING_MAX_PERCENT, atr_percent)

        trailing_price = context.highest_price * (1 - atr_percent / 100)

        # Nunca abaixo do preço de entrada após break-even
        trailing_price = max(trailing_price, context.entry_price)

        return trailing_price

    def _is_reversal(self, context: TradeContext) -> bool:
        """
        Detecta inversão técnica forte.
        """

        ema_reversal = context.ema_10 < context.ema_20
        rsi_weak = context.rsi_14 < 45
        volume_sell_pressure = context.volume_ratio < 1.0

        return ema_reversal and rsi_weak and volume_sell_pressure