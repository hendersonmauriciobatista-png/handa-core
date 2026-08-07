# override_manager.py
# ==============================
# UI Control Core — Override Manager
# FASE 1: Controle Humano
# Sistema: H&A / ALFRED IA
# ==============================

from .state import UIControlState


class OverrideManager:
    """
    Gerencia o estado de override humano.
    Representa a autoridade direta do operador sobre o sistema.
    """

    # ==============================
    # Override
    # ==============================

    def activate(self, ui_state: UIControlState):
        """
        Ativa override humano.
        Bloqueia ações automáticas do sistema e policy.
        """
        if not ui_state:
            return

        ui_state.operator_override = True
        ui_state.validate()

    def deactivate(self, ui_state: UIControlState):
        """
        Desativa override humano.
        Retorna controle automático ao sistema.
        """
        if not ui_state:
            return

        ui_state.operator_override = False

        # Se não houver pin, volta para foco automático
        if ui_state.pinned_slot is None:
            ui_state.focus_mode = "auto"

        ui_state.validate()

    # ==============================
    # Estado
    # ==============================

    def is_active(self, ui_state: UIControlState) -> bool:
        """Retorna se override humano está ativo."""
        return ui_state.operator_override
