# exception_handler.py
# ==============================
# UI Control Core — Exception Handler
# FASE 1: Controle Humano
# Sistema: H&A / ALFRED IA
# ==============================

from .state import UIControlState
from .control_bus import ControlEvent


class ExceptionHandler:
    """
    Gerencia exceções, estados inválidos e recuperação do sistema.
    Garante resiliência, fallback e consistência lógica.
    """

    # ==============================
    # Tratamento principal
    # ==============================

    def handle(self, event: ControlEvent | None, ui_state: UIControlState):
        """
        Trata estados inválidos e aplica correções seguras.
        """

        # Evento nulo (bloqueado pelo resolver)
        if event is None:
            self._validate_state(ui_state)
            return

        # Validação geral
        self._validate_state(ui_state)

    # ==============================
    # Validações internas
    # ==============================

    def _validate_state(self, ui_state: UIControlState):
        """
        Valida e corrige estados impossíveis.
        """

        # Estado impossível: manual sem pin
        if ui_state.focus_mode == "manual" and ui_state.pinned_slot is None:
            ui_state.focus_mode = "auto"
            ui_state.operator_override = False

        # Estado impossível: pin sem manual
        if ui_state.pinned_slot is not None and ui_state.focus_mode != "manual":
            ui_state.focus_mode = "manual"

        # Estado impossível: override sem foco manual
        if ui_state.operator_override and ui_state.focus_mode != "manual":
            ui_state.operator_override = False

        # Estado impossível: centro inválido
        if ui_state.active_center is not None and not isinstance(ui_state.active_center, str):
            ui_state.active_center = None

        # Fallback seguro
        if ui_state.focus_mode not in ["auto", "manual"]:
            ui_state.focus_mode = "auto"

    # ==============================
    # Modos de recuperação
    # ==============================

    def safe_mode(self, ui_state: UIControlState):
        """
        Entra em modo seguro.
        """
        ui_state.focus_mode = "auto"
        ui_state.pinned_slot = None
        ui_state.operator_override = False
        ui_state.active_center = None
