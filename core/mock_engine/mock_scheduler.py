# core/mock_engine/mock_scheduler.py

import threading
import time
import random


class MockScheduler:
    """
    Scheduler da engine mock.
    Simula tempo, ciclos e comportamento vivo do sistema.
    """

    def __init__(self, engine):
        self.engine = engine
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.engine.start()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.engine.stop()

    def _loop(self):
        system_states = ["RUNNING", "DRAINING", "LOCKDOWN"]
        slot_states = ["IDLE", "ANALYSIS", "READY", "RUNNING", "DRAINING"]

        while self.running:
            # ---- sistema global ----
            sys_state = random.choice(system_states)
            self.engine.set_system_state(sys_state)

            # ---- slots ----
            for slot_id in range(1, 13):
                state = random.choice(slot_states)
                mode = random.choice(["ANÁLISE", "OBSERVAÇÃO", "STANDBY"])

                self.engine.set_slot_state(slot_id, state)
                self.engine.set_slot_mode(slot_id, mode)

            # tempo de ciclo
            time.sleep(3)
