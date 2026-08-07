from enum import Enum


class SystemState(Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    DRAINING = "DRAINING"
    LOCKED = "LOCKED"


class StateController:

    def __init__(self):
        self._state = SystemState.IDLE
        self._listeners = []

    # =====================================================
    # LISTENERS (UI observers)
    # =====================================================

    def add_listener(self, callback):
        """
        callback(new_state: SystemState)
        """
        self._listeners.append(callback)

    def _notify(self):
        for callback in self._listeners:
            callback(self._state)

    # =====================================================
    # GET STATE
    # =====================================================

    @property
    def state(self):
        return self._state

    # =====================================================
    # TRANSITIONS
    # =====================================================

    def start(self):
        if self._state == SystemState.IDLE:
            self._state = SystemState.RUNNING
            self._notify()

    def stop(self):
        if self._state == SystemState.RUNNING:
            self._state = SystemState.DRAINING
            self._notify()

    def finish_drain(self):
        if self._state == SystemState.DRAINING:
            self._state = SystemState.IDLE
            self._notify()

    def lock(self):
        self._state = SystemState.LOCKED
        self._notify()

    def reset(self):
        if self._state == SystemState.LOCKED:
            self._state = SystemState.IDLE
            self._notify()
    # =====================================================
# TESTE ISOLADO
# =====================================================

if __name__ == "__main__":

    def listener(new_state):
        print(f"STATE CHANGED → {new_state.value}")

    controller = StateController()
    controller.add_listener(listener)

    print("Initial:", controller.state.value)

    controller.start()
    controller.stop()
    controller.finish_drain()
    controller.lock()
    controller.reset()
