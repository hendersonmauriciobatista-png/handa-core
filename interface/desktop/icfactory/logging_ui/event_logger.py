# logging_ui/event_logger.py
from typing import List
from logging_ui.event_model import UIEvent


class EventLogger:
    """
    Armazena eventos para auditoria e exibição.
    """

    def __init__(self, max_events: int = 100):
        self._events: List[UIEvent] = []
        self._max_events = max_events

    def log(self, event: UIEvent) -> None:
        self._events.append(event)

        # mantém histórico limitado (UI)
        if len(self._events) > self._max_events:
            self._events.pop(0)

    def get_recent(self) -> List[UIEvent]:
        return list(self._events)
