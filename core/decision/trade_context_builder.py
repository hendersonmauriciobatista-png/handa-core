# ============================================================
# core/decision/trade_context_builder.py
# Builder responsável por montar o TradeContext automaticamente
# ============================================================

from core.decision.trade_context import TradeContext


class TradeContextBuilder:
    """
    Constrói automaticamente um TradeContext a partir
    dos dados de mercado e sensores.
    """

    @staticmethod
    def build(
        symbol: str,
        slot_id: int,

        entry_price: float,
        current_price: float,
        position_size: float,

        ema_10: float,
        ema_20: float,
        ema_50: float,
        rsi_14: float,
        volume_ratio: float,

        trade_duration_seconds: int,

        consecutive_losses: int,
        daily_drawdown_percent: float,
        draining_mode_active: bool
    ) -> TradeContext:

        # cálculo do PNL não realizado
        unrealized_pnl_percent = (
            (current_price - entry_price) / entry_price
        ) * 100

        return TradeContext(
            symbol=symbol,
            slot_id=slot_id,

            entry_price=entry_price,
            current_price=current_price,
            position_size=position_size,

            unrealized_pnl_percent=unrealized_pnl_percent,
            trade_duration_seconds=trade_duration_seconds,

            ema_10=ema_10,
            ema_20=ema_20,
            ema_50=ema_50,
            rsi_14=rsi_14,
            volume_ratio=volume_ratio,

            consecutive_losses=consecutive_losses,
            daily_drawdown_percent=daily_drawdown_percent,
            draining_mode_active=draining_mode_active
        )