# ============================================================
# core/trading/position_state.py
# H&A - PositionState v1.0
# Memória estrutural da posição ativa
# ============================================================

from dataclasses import dataclass
from datetime import datetime


@dataclass
class PositionState:
    """
    Representa o estado estrutural de uma posição ativa.

    Não executa.
    Não consulta API.
    Não calcula PnL.
    Apenas mantém memória da posição.
    """

    symbol: str
    entry_price: float
    quantity: float
    entry_timestamp: datetime

    highest_price: float
    ticks_in_trade: int = 0

    # ============================================================
    # Atualizações estruturais
    # ============================================================

    def update_on_tick(self, current_price: float) -> None:
        """
        Atualiza estado estrutural a cada ciclo.

        - Incrementa contador de ticks
        - Atualiza highest_price se necessário
        """

        self.ticks_in_trade += 1

        if current_price > self.highest_price:
            self.highest_price = current_price