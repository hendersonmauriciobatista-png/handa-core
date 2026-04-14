# core_bridge/events.py
from typing import Callable, Dict, Any, List


class CoreEvents:
    """
    Gerenciador de eventos vindos do Core (push).
    """

    def __init__(self):
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._subscribers.append(callback)

    def emit(self, event: Dict[str, Any]) -> None:
        for callback in self._subscribers:
            callback(event)
