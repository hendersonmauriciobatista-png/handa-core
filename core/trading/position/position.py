# ============================================================
# core/trading/position/position.py
# H&A - Position v1.0
# Container institucional de dados de operação
# ============================================================

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:
    """
    Representa uma posição ativa no sistema.
    Não decide saída.
    Não executa ordem.
    Apenas mantém estado da operação.
    """

    symbol: str
    entry_price: float
    quantity: float
    entry_timestamp: datetime

    highest_price: float
    unrealized_pnl_percent: float = 0.0
    ticks_in_trade: int = 0

    def update_price(self, current_price: float) -> None:
        """
        Atualiza preço atual da posição.
        Recalcula PnL e highest_price.
        """

        if current_price <= 0:
            raise ValueError("Position: current_price inválido")

        # Atualiza highest_price
        if current_price > self.highest_price:
            self.highest_price = current_price

        # Atualiza PnL %
        self.unrealized_pnl_percent = (
            (current_price - self.entry_price)
            / self.entry_price
        ) * 100

    def increment_tick(self) -> None:
        """
        Incrementa contador interno de ticks.
        """
        self.ticks_in_trade += 1

    def snapshot(self, current_price: float) -> dict:
        """
        Retorna snapshot estruturado da posição.
        """

        return {
            "entry_price": self.entry_price,
            "current_price": current_price,
            "quantity": self.quantity,
            "entry_timestamp": self.entry_timestamp,
            "highest_price": self.highest_price,
            "unrealized_pnl_percent": self.unrealized_pnl_percent,
            "ticks_in_trade": self.ticks_in_trade,
        }