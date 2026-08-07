# ============================================================
# core/trading/exit/trade_context_builder.py
# H&A - TradeContextBuilder v1.0
# Constrói TradeContext a partir de PositionState + Snapshot
# ============================================================

from datetime import datetime
from typing import Dict

from core.trading.position_state import PositionState
from .trade_context import TradeContext


class TradeContextBuilder:
    """
    Responsável por construir o TradeContext institucional.

    - Calcula PnL %
    - Atualiza highest_price
    - Atualiza ticks
    - Injeta snapshot técnico
    - Injeta estado global de risco
    """

    # ============================================================
    # Método principal
    # ============================================================

    def build(
        self,
        position: PositionState,
        snapshot: Dict,
        consecutive_losses: int,
        daily_drawdown_percent: float,
        draining_mode_active: bool,
    ) -> TradeContext:

        current_price = snapshot["price"]

        # --------------------------------------------------------
        # Atualização estrutural da posição
        # --------------------------------------------------------
        position.update_on_tick(current_price)

        # --------------------------------------------------------
        # Cálculo de PnL %
        # --------------------------------------------------------
        unrealized_pnl_percent = (
            (current_price - position.entry_price)
            / position.entry_price
        ) * 100

        # --------------------------------------------------------
        # Construção do TradeContext
        # --------------------------------------------------------
        return TradeContext(
            symbol=position.symbol,
            entry_price=position.entry_price,
            current_price=current_price,
            quantity=position.quantity,
            entry_timestamp=position.entry_timestamp,
            ema_10=snapshot["ema_10"],
            ema_20=snapshot["ema_20"],
            ema_50=snapshot["ema_50"],
            rsi_14=snapshot["rsi_14"],
            volume_ratio=snapshot["volume_ratio"],
            atr_14=snapshot["atr_14"],
            highest_price=position.highest_price,
            unrealized_pnl_percent=unrealized_pnl_percent,
            ticks_in_trade=position.ticks_in_trade,
            consecutive_losses=consecutive_losses,
            daily_drawdown_percent=daily_drawdown_percent,
            draining_mode_active=draining_mode_active,
        )