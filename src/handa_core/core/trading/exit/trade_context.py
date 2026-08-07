# ============================================================
# core/trading/exit/trade_context.py
# H&A - TradeContext Imutável Validado
# Política Oficial Operação Autônoma v1.0 (Perfil Moderado)
# ============================================================

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TradeContext:
    """
    Snapshot institucional do estado da posição.
    Não executa, não decide, não consulta API.
    Apenas valida e encapsula estado.
    """

    # --- Identificação ---
    symbol: str
    entry_price: float
    current_price: float
    quantity: float
    entry_timestamp: datetime

    # --- Indicadores ---
    ema_10: float
    ema_20: float
    ema_50: float
    rsi_14: float
    volume_ratio: float
    atr_14: float

    # --- Estado da posição ---
    highest_price: float
    unrealized_pnl_percent: float
    ticks_in_trade: int

    # --- Risco global ---
    consecutive_losses: int
    daily_drawdown_percent: float
    draining_mode_active: bool

    def __post_init__(self):

        # --- Validações estruturais obrigatórias ---

        if not self.symbol:
            raise ValueError("TradeContext: symbol inválido")

        if self.entry_price <= 0:
            raise ValueError("TradeContext: entry_price deve ser > 0")

        if self.current_price <= 0:
            raise ValueError("TradeContext: current_price deve ser > 0")

        if self.quantity <= 0:
            raise ValueError("TradeContext: quantity deve ser > 0")

        if self.highest_price < self.entry_price:
            raise ValueError("TradeContext: highest_price não pode ser menor que entry_price")

        if not (0 <= self.rsi_14 <= 100):
            raise ValueError("TradeContext: rsi_14 deve estar entre 0 e 100")

        if self.atr_14 <= 0:
            raise ValueError("TradeContext: atr_14 deve ser > 0")

        if self.ticks_in_trade < 0:
            raise ValueError("TradeContext: ticks_in_trade não pode ser negativo")

        if self.consecutive_losses < 0:
            raise ValueError("TradeContext: consecutive_losses não pode ser negativo")

        if self.daily_drawdown_percent < 0:
            raise ValueError("TradeContext: daily_drawdown_percent não pode ser negativo")

        if not (-100.0 < self.unrealized_pnl_percent < 1000.0):
            raise ValueError("TradeContext: unrealized_pnl_percent fora de faixa aceitável")