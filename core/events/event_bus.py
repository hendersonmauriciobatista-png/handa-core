# core/events/event_bus.py

class EventBus:
    """
    Router central de eventos do sistema.
    Nada chama UI direto.
    Tudo vira evento.
    """

    def __init__(self):
        self._listeners = {}

    # --------- REGISTRATION ---------

    def on(self, event_type, callback):
        """
        Registra listener para um tipo de evento
        """
        if event_type not in self._listeners:
            self._listeners[event_type] = []

        if callback not in self._listeners[event_type]:
            self._listeners[event_type].append(callback)

    def off(self, event_type, callback):
        if event_type in self._listeners:
            if callback in self._listeners[event_type]:
                self._listeners[event_type].remove(callback)

    # --------- EMISSION ---------

    def emit(self, event_type, payload=None):
        """
        Dispara evento para todos os listeners
        """
        if event_type not in self._listeners:
            return

        for cb in self._listeners[event_type]:
            cb(payload)
