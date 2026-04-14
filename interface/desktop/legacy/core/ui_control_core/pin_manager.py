# pin_manager.py
# ==============================
# UI Control Core — Pin Manager
# FASE 1: Controle Humano
# Sistema: H&A / ALFRED IA
# ==============================

from typing import Optional
from .state import UIControlState


class PinManager:
    """
    Gerencia o pin lógico de slots.
    Controla foco manual, override humano e centro da UI.
    """

    def __init__(self, ui_state: UIControlState):
        self.ui_state = ui_state

    # ==============================
    # Pin / Unpin
    # ==============================

    def pin(self, slot_id: str):
        """
        Fixa manualmente um slot no centro.
        Ativa foco manual e override humano.
        """
        if not slot_id:
            return

        self.ui_state.set_manual_focus(slot_id)
        self.ui_state.validate()

    def unpin(self):
        """
        Remove foco manual.
        Retorna sistema para foco automático.
        """
        self.ui_state.clear_manual_focus()
        self.ui_state.validate()

    # ==============================
    # Estado
    # ==============================

    def is_pinned(self) -> bool:
        """Retorna se há slot pinado."""
        return self.ui_state.pinned_slot is not None

    def get_pinned_slot(self) -> Optional[str]:
        """Retorna o slot pinado atual."""
        return self.ui_state.pinned_slot

    # ==============================
    # Override
    # ==============================

    def override_pin(self, slot_id: str):
        """
        Substitui o pin atual por outro slot.
        """
        self.pin(slot_id)
