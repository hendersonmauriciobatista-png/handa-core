# control_bus.py
# ==============================
# UI Control Core — Control Bus
# FASE 1: Controle Humano
# Sistema: H&A / ALFRED IA
# ==============================

from typing import List, Callable, Any


class ControlEvent:
    """
    Evento padrão do sistema de controle.
    Representa uma intenção ou ação normalizada.
    """

    def __init__(self, name: str, source: str, payload: dict | None = None):
        self.name = name
        self.source = source  # operator | policy | system
        self.payload = payload or {}

    def __repr__(self):
        return f"<ControlEvent name={self.name} source={self.source} payload={self.payload}>"



class ControlBus:
    """
    Barramento central de eventos.
    Responsável por:
    - desacoplamento de módulos
    - broadcast
    - roteamento
    - padronização de tráfego
    """

    def __init__(self):
        self.subscribers: List[Any] = []

    # ==============================
    # Subscrição
    # ==============================

    def subscribe(self, handler: Any):
        """
        Registra um handler no barramento.
        O handler deve implementar: handle(event)
        """
        if handler not in self.subscribers:
            self.subscribers.append(handler)

    def unsubscribe(self, handler: Any):
        if handler in self.subscribers:
            self.subscribers.remove(handler)

    # ==============================
    # Dispatch
    # ==============================

    def dispatch(self, event: ControlEvent):
        """
        Dispara evento para todos os handlers.
        """
        for handler in self.subscribers:
            if hasattr(handler, "handle"):
                handler.handle(event)

    # ==============================
    # Broadcast utilitário
    # ==============================

    def broadcast(self, name: str, source: str, payload: dict | None = None):
        """
        Cria e dispara evento diretamente.
        """
        event = ControlEvent(name=name, source=source, payload=payload)
        self.dispatch(event)
