# =====================================================
# h_a/core/slot_manager.py
# SlotManager — MOCK PARA UI VIVA
# =====================================================

import threading
from h_a.core.slot_executor import SlotExecutor


class SlotManager:
    """
    Orquestra múltiplos SlotExecutors (12 slots).
    Não conhece UI, Strategy ou Slot real.
    """

    def __init__(self, event_bus, num_slots: int = 12, interval: float = 1.0):
        self.event_bus = event_bus
        self.num_slots = num_slots
        self.interval = interval

        self.executors = {}
        self._running = False
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True

            for slot_id in range(1, self.num_slots + 1):
                executor = SlotExecutor(
                    event_bus=self.event_bus,
                    slot_id=slot_id,
                    interval=self.interval,
                )
                self.executors[slot_id] = executor
                executor.start()

    def stop_all(self):
        with self._lock:
            if not self._running:
                return
            self._running = False

            for executor in self.executors.values():
                executor.stop()

            self.executors.clear()

    def is_running(self) -> bool:
        return self._running
