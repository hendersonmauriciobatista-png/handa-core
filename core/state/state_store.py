# core/state/state_store.py

class StateStore:
    """
    Fonte única da verdade do sistema.
    Guarda estado global e de slots.
    Notifica assinantes sempre que algo muda.
    """

    def __init__(self):
        self._state = {}
        self._subscribers = []

    # --------- STATE CONTROL ---------

    def set(self, key, value):
        self._state[key] = value
        self._notify()

    def get(self, key, default=None):
        return self._state.get(key, default)

    def get_all(self):
        return self._state.copy()

    def update_bulk(self, data: dict):
        """
        Atualiza múltiplos estados de uma vez
        """
        for k, v in data.items():
            self._state[k] = v
        self._notify()

    # --------- SUBSCRIPTION ---------

    def subscribe(self, callback):
        """
        UI Binder e outros módulos se registram aqui
        """
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback):
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    # --------- INTERNAL ---------

    def _notify(self):
        snapshot = self.get_all()
        for cb in self._subscribers:
            cb(snapshot)
