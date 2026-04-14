"""
H&A Main Bootstrap

Camadas:
- StateController
- SystemStateAssembler
- HeaderView
- SlotManager
- SystemLoop
"""

import time
from core.system.state_controller import StateController, SystemState
from h_a.system_state_assembler import SystemStateAssembler
from h_a.interfaces.header_view import HeaderView
from h_a.slot_engine.slot_manager import SlotManager


class HandaApplication:

    def __init__(self):
        self.controller = StateController()
        self.assembler = SystemStateAssembler(self.controller)
        self.header = HeaderView()
        self.slot_manager = SlotManager()

        self.controller.add_listener(self._on_state_change)

        self._running = True

        self._render()

    # ==================================
    # LISTENER DE ESTADO
    # ==================================
    def _on_state_change(self, new_state):

        if new_state == SystemState.RUNNING:
            self.slot_manager.start()

        elif new_state == SystemState.DRAINING:
            self.slot_manager.drain()

        elif new_state == SystemState.IDLE:
            self.slot_manager.stop()

        elif new_state == SystemState.LOCKED:
            self.slot_manager.stop()

        self._render()

    # ==================================
    # RENDER
    # ==================================
    def _render(self):
        state = self.assembler.build()
        self.header.render(state)

    # ==================================
    # LOOP OFICIAL
    # ==================================
    def run_loop(self):
        while self._running:
            time.sleep(1)

            # Tick do motor
            self.slot_manager.tick()

            # Atualiza UI
            self._render()

    def stop_loop(self):
        self._running = False


# ======================================
# ENTRYPOINT
# ======================================

def run():
    app = HandaApplication()

    # Simulação de transições
    time.sleep(1)
    app.controller.start()

    time.sleep(3)
    app.controller.stop()

    time.sleep(3)
    app.controller.finish_drain()

    time.sleep(3)
    app.controller.lock()

    time.sleep(3)
    app.controller.reset()

    app.run_loop()


if __name__ == "__main__":
    run()
