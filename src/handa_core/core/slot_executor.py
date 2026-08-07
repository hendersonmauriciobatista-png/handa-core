# =====================================================
# h_a/core/slot_executor.py
# SlotExecutor — MOCK DE ESTADOS (UI VIVA)
# =====================================================

import threading
import time


class SlotExecutor(threading.Thread):
    """
    Executor de Slot (MOCK).
    Emite eventos STATE_CHANGED via EventBus oficial.
    """

    def __init__(self, event_bus, slot_id: int, interval: float = 1.0):
        super().__init__(daemon=False)  # não-daemon para evitar erro no shutdown
        self.event_bus = event_bus
        self.slot_id = slot_id
        self.interval = interval
        self._running = True

        self._states = (
            "ANALYZING",
            "READY",
            "ENTERING",
            "TRADING",
            "EXITING",
            "FINALIZING",
            "IDLE",
        )

    def run(self):
        while self._running:
            for state in self._states:
                if not self._running:
                    break
                self._emit_state(state)
                time.sleep(self.interval)

    def _emit_state(self, state: str):
        self.event_bus.emit(
            "STATE_CHANGED",
            entity_type="Slot",
            entity_id=self.slot_id,
            state=state,
            payload={
                "price": None,
                "pnl": 0.0,
            },
        )

    def stop(self):
        self._running = False
