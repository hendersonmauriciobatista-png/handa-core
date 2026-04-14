# =====================================================
# h_a/core/event_bridge.py
# EventBridge — CORE NOVO (FINAL, THREAD-SAFE)
# =====================================================

import threading
from collections import defaultdict


class EventBridge:
    """
    Barramento simples de eventos para o CORE.
    Permite subscribe(event_name, callback)
    e emit(event_name, payload).

    Thread-safe e tolerante a erro em listeners.
    """

    def __init__(self):
        self._listeners = defaultdict(list)
        self._lock = threading.Lock()

    # -------------------------------------------------
    # SUBSCRIBE
    # -------------------------------------------------

    def subscribe(self, event_name: str, callback):
        with self._lock:
            self._listeners[event_name].append(callback)

    # -------------------------------------------------
    # EMIT
    # -------------------------------------------------

    def emit(self, event_name: str, payload: dict):
        listeners = []

        with self._lock:
            listeners = list(self._listeners.get(event_name, []))

        for callback in listeners:
            try:
                callback(payload)
            except Exception as e:
                # nunca quebra o core por erro de listener
                print(f"EventBridge listener error: {e}")
