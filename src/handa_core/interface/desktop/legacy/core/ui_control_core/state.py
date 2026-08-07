# state.py
# ==============================
# UI Control Core — Estado Global
# FASE 1: Controle Humano
# Sistema: H&A / ALFRED IA
# ==============================

from typing import Optional


class UIControlState:
    """
    Estado global de controle da UI.
    Governa foco, soberania humana e autoridade de decisão.
    """

    def __init__(self):
        # auto | manual
        self.focus_mode: str = "auto"

        # slot_id pinado manualmente
        self.pinned_slot: Optional[str] = None

        # indica se o operador está em controle direto
        self.operator_override: bool = False

        # slot atualmente no centro da UI
        self.active_center: Optional[str] = None

    # ==============================
    # Métodos de controle
    # ==============================

    def set_manual_focus(self, slot_id: str):
        """Ativa foco manual (pin)."""
        self.focus_mode = "manual"
        self.pinned_slot = slot_id
        self.operator_override = True
        self.active_center = slot_id

    def clear_manual_focus(self):
        """Remove foco manual (unpin)."""
        self.focus_mode = "auto"
        self.pinned_slot = None
        self.operator_override = False
        self.active_center = None

    def set_active_center(self, slot_id: Optional[str]):
        """Define slot central atual."""
        self.active_center = slot_id

    # ==============================
    # Validações de consistência
    # ==============================

    def validate(self):
        """
        Garante consistência lógica do estado.
        Corrige estados impossíveis automaticamente.
        """

        # Estado impossível: manual sem pin
        if self.focus_mode == "manual" and self.pinned_slot is None:
            self.focus_mode = "auto"
            self.operator_override = False

        # Estado impossível: pin sem manual
        if self.pinned_slot is not None and self.focus_mode != "manual":
            self.focus_mode = "manual"

        # Estado impossível: override sem foco manual
        if self.operator_override and self.focus_mode != "manual":
            self.operator_override = False

    # ==============================
    # Serialização (futuro: persistência)
    # ==============================

    def to_dict(self):
        return {
            "focus_mode": self.focus_mode,
            "pinned_slot": self.pinned_slot,
            "operator_override": self.operator_override,
            "active_center": self.active_center,
        }

    def from_dict(self, data: dict):
        self.focus_mode = data.get("focus_mode", "auto")
        self.pinned_slot = data.get("pinned_slot", None)
        self.operator_override = data.get("operator_override", False)
        self.active_center = data.get("active_center", None)

        self.validate()
