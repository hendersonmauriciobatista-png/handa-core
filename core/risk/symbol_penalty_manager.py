# ============================================================
# core/risk/symbol_penalty_manager.py
# Punição progressiva por reincidência de loss no mesmo símbolo
# ============================================================

from datetime import datetime, timedelta
from typing import Dict, Optional


class SymbolPenaltyManager:

    def __init__(self):
        self.symbol_state: Dict[str, Dict[str, Optional[datetime] | int]] = {}

    # ========================================================
    # HELPERS
    # ========================================================

    def _now(self) -> datetime:
        return datetime.utcnow()

    def _get_state(self, symbol: str) -> Dict[str, Optional[datetime] | int]:
        if symbol not in self.symbol_state:
            self.symbol_state[symbol] = {
                "loss_count": 0,
                "last_loss_at": None,
                "blocked_until": None,
            }
        return self.symbol_state[symbol]

    # ========================================================
    # REGISTRAR LOSS
    # ========================================================

    def register_loss(self, symbol: str) -> None:

        state = self._get_state(symbol)
        now = self._now()

        last_loss_at = state["last_loss_at"]

        # Se passou muito tempo desde o último loss,
        # reinicia a contagem para não punir eternamente
        if isinstance(last_loss_at, datetime):
            if (now - last_loss_at) > timedelta(hours=12):
                state["loss_count"] = 0

        state["loss_count"] = int(state["loss_count"]) + 1
        state["last_loss_at"] = now

        # Punição progressiva
        if state["loss_count"] == 1:
            block_time = timedelta(minutes=30)
        elif state["loss_count"] == 2:
            block_time = timedelta(hours=2)
        else:
            block_time = timedelta(hours=12)

        state["blocked_until"] = now + block_time

        print(
            f"[SYMBOL PENALTY] {symbol} "
            f"loss_count={state['loss_count']} "
            f"blocked_until={state['blocked_until']}"
        )

    # ========================================================
    # REGISTRAR WIN
    # ========================================================

    def register_win(self, symbol: str) -> None:

        state = self._get_state(symbol)

        # Vitória reduz reincidência negativa
        if int(state["loss_count"]) > 0:
            state["loss_count"] = int(state["loss_count"]) - 1

        print(
            f"[SYMBOL PENALTY] {symbol} "
            f"win -> loss_count={state['loss_count']}"
        )

    # ========================================================
    # ESTÁ BLOQUEADO?
    # ========================================================

    def is_blocked(self, symbol: str) -> bool:

        state = self._get_state(symbol)
        blocked_until = state["blocked_until"]

        if not isinstance(blocked_until, datetime):
            return False

        if self._now() >= blocked_until:
            state["blocked_until"] = None
            return False

        return True

    # ========================================================
    # TEMPO RESTANTE DE BLOQUEIO
    # ========================================================

    def get_remaining_seconds(self, symbol: str) -> int:

        state = self._get_state(symbol)
        blocked_until = state["blocked_until"]

        if not isinstance(blocked_until, datetime):
            return 0

        remaining = (blocked_until - self._now()).total_seconds()

        if remaining <= 0:
            state["blocked_until"] = None
            return 0

        return int(remaining)

    # ========================================================
    # DEBUG / INSPEÇÃO
    # ========================================================

    def get_symbol_state(self, symbol: str) -> Dict[str, Optional[datetime] | int]:
        return self._get_state(symbol).copy()

    def reset_symbol(self, symbol: str) -> None:
        if symbol in self.symbol_state:
            del self.symbol_state[symbol]

    def reset_all(self) -> None:
        self.symbol_state.clear()