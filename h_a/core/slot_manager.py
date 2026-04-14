# =====================================================
# h_a/core/slot_manager.py
# SlotManager — MOCK PARA UI VIVA (FINAL UNIFICADO)
# =====================================================

import threading
from h_a.core.slot_executor import SlotExecutor


class SlotManager:
    """
    Orquestra múltiplos SlotExecutors (mock).
    Usa EXCLUSIVAMENTE o EventBus oficial.
    """

    def __init__(self, event_bus, num_slots: int = 12):
        self.event_bus = event_bus
        self.num_slots = num_slots

        self.executors: dict[int, SlotExecutor] = {}
        self._running = False
        self._lock = threading.Lock()

    # -------------------------------------------------
    # START
    # -------------------------------------------------

    def start(self):
        with self._lock:
            if self._running:
                return

            self._running = True

            for slot_id in range(1, self.num_slots + 1):
                executor = SlotExecutor(
                    event_bus=self.event_bus,
                    slot_id=slot_id,
                )
                self.executors[slot_id] = executor
                executor.start()

    # -------------------------------------------------
    # STOP
    # -------------------------------------------------

    def stop_all(self):
        with self._lock:
            if not self._running:
                return

            self._running = False

            for executor in self.executors.values():
                executor.stop()

            self.executors.clear()

    # -------------------------------------------------
    # STATUS
    # -------------------------------------------------

    def is_running(self) -> bool:
        return self._running
