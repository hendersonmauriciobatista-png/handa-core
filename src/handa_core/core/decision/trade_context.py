# ============================================================
# H&A - Trade Context
# Estrutura de contexto usada pelo motor de decisão
# ============================================================

from dataclasses import dataclass


@dataclass
class TradeContext:

    # identificação
    symbol: str
    slot_id: int

    # posição
    entry_price: float
    current_price: float
    position_size: float

    # performance
    unrealized_pnl_percent: float
    trade_duration_seconds: int

    # indicadores técnicos
    ema_10: float
    ema_20: float
    ema_50: float
    rsi_14: float
    volume_ratio: float

    # contexto de risco
    consecutive_losses: int
    daily_drawdown_percent: float
    draining_mode_active: bool