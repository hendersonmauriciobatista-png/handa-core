# focus_manager.py
# ==============================
# UI Control Core — Focus Manager
# FASE 1: Controle Humano
# Sistema: H&A / ALFRED IA
# ==============================

from typing import Optional
from .state import UIControlState


class FocusManager:
    """
    Gerencia foco da UI.
    Decide qual slot ocupa o centro com base em:
    - foco manual (pin)
    - foco automático
    - fallback seguro
    """

    # ==============================
    # Atualização de foco
    # ==============================

    def update_focus(
        self,
        ui_state: UIControlState,
        auto_focus_slot: Optional[str] = None
    ):
        """
        Atualiza o centro da UI com base no estado atual.
        """

        # Prioridade absoluta: foco manual (pin)
        if ui_state.pinned_slot:
            ui_state.active_center = ui_state.pinned_slot
            ui_state.focus_mode = "manual"
            return

        # Foco automático
        if auto_focus_slot:
            ui_state.active_center = auto_focus_slot
            ui_state.focus_mode = "auto"
            return

        # Fallback seguro
        ui_state.active_center = None
        ui_state.focus_mode = "auto"

    # ==============================
    # Utilitários
    # ==============================

    def force_focus(self, ui_state: UIControlState, slot_id: str):
        """
        Força foco manual em um slot.
        """
        if not slot_id:
            return

        ui_state.set_manual_focus(slot_id)
        ui_state.validate()

    def clear_focus(self, ui_state: UIControlState):
        """
        Remove foco manual e retorna ao automático.
        """
        ui_state.clear_manual_focus()
        ui_state.validate()

    # ==============================
    # Estado
    # ==============================

    def get_active_center(self, ui_state: UIControlState) -> Optional[str]:
        """Retorna o slot atual no centro."""
        return ui_state.active_center
