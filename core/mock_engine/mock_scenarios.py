# core/mock_engine/mock_scenarios.py

import random
import time


class MockScenarios:
    """
    Cenários simulados de comportamento do sistema.
    Aqui não é aleatório puro: é fluxo lógico.
    """

    def __init__(self, engine):
        self.engine = engine
        self.running = False

    def start(self):
        self.running = True
        self.engine.start()
        self._scenario_loop()

    def stop(self):
        self.running = False
        self.engine.stop()

    def _scenario_loop(self):
        """
        Loop principal de cenários
        """
        while self.running:

            # =========================
            # CENÁRIO 1 — BOOT
            # =========================
            self.engine.set_system_state("RUNNING")
            time.sleep(2)

            # =========================
            # CENÁRIO 2 — ANÁLISE
            # =========================
            for sid in range(1, 13):
                self.engine.set_slot_state(sid, "ANALYSIS")
                self.engine.set_slot_mode(sid, "ANÁLISE")
                time.sleep(0.2)

            time.sleep(2)

            # =========================
            # CENÁRIO 3 — PREPARAÇÃO
            # =========================
            for sid in range(1, 13):
                self.engine.set_slot_state(sid, "READY")
                self.engine.set_slot_mode(sid, "OBSERVAÇÃO")
                time.sleep(0.15)

            time.sleep(2)

            # =========================
            # CENÁRIO 4 — EXECUÇÃO
            # =========================
            active_slots = random.sample(range(1, 13), k=4)

            for sid in active_slots:
                self.engine.set_slot_state(sid, "RUNNING")
                self.engine.set_slot_mode(sid, "EXECUÇÃO")

            time.sleep(3)

            # =========================
            # CENÁRIO 5 — DRAINING
            # =========================
            self.engine.set_system_state("DRAINING")

            for sid in active_slots:
                self.engine.set_slot_state(sid, "DRAINING")
                self.engine.set_slot_mode(sid, "ENCERRANDO")

            time.sleep(3)

            # =========================
            # CENÁRIO 6 — RESET
            # =========================
            for sid in range(1, 13):
                self.engine.set_slot_state(sid, "IDLE")
                self.engine.set_slot_mode(sid, "STANDBY")

            self.engine.set_system_state("RUNNING")

            time.sleep(3)
