# core/mock_engine/mock_engine.py

class MockEngine:
    """
    Engine mock do sistema.
    Não toca UI.
    Não conhece Tkinter.
    Não conhece widgets.
    Só muda estado.
    """

    def __init__(self, state_store, event_bus=None):
        self.state_store = state_store
        self.event_bus = event_bus
        self.running = False

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def set_system_state(self, state):
        if not self.running:
            return
        self.state_store.set("system_status", state)

    def set_slot_state(self, slot_id, state):
        if not self.running:
            return
        self.state_store.set(f"slot_{slot_id}_state", state)

    def set_slot_mode(self, slot_id, mode):
        if not self.running:
            return
        self.state_store.set(f"slot_{slot_id}_mode", mode)
