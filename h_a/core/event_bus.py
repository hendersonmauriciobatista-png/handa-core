# h_a/core/event_bus.py

class EventBus:
    """
    Barramento de eventos global do Core.
    Comunicação desacoplada entre Core, UI, Logger, etc.
    """

    def __init__(self):
        self._subscribers = {}

    def subscribe(self, event_name: str, callback):
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []

        self._subscribers[event_name].append(callback)

    def emit(self, event_name: str, **data):
        callbacks = self._subscribers.get(event_name, [])

        for callback in callbacks:
            callback(data)


# =====================================================
# SINGLETON GLOBAL
# =====================================================

event_bus = EventBus()
