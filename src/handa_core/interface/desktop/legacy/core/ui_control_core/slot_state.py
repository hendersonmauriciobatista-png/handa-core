# slot_state.py
# ==============================
# UI Control Core — Estado por Slot
# FASE 1: Controle Humano
# Sistema: H&A / ALFRED IA
# ==============================

from typing import Optional


class SlotControlState:
    """
    Estado de controle individual por slot.
    Governa lock, interação, proteção e autoridade local.
    """

    def __init__(self, slot_id: str):
        self.slot_id: str = slot_id

        # Proteção do slot
        self.locked: bool = False

        # manual | system | policy | None
        self.lock_reason: Optional[str] = None

        # Controle de interação
        self.interaction_enabled: bool = True

    # ==============================
    # Lock / Unlock
    # ==============================

    def lock(self, reason: str = "manual"):
        """
        Bloqueia o slot.
        reason: manual | system | policy
        """
        self.locked = True
        self.lock_reason = reason
        self.interaction_enabled = False

    def unlock(self):
        """
        Desbloqueia o slot.
        """
        self.locked = False
        self.lock_reason = None
        self.interaction_enabled = True

    # ==============================
    # Validações de consistência
    # ==============================

    def validate(self):
        """
        Garante consistência lógica do estado do slot.
        """

        # Estado impossível: lock sem motivo
        if self.locked and self.lock_reason is None:
            self.lock_reason = "system"

        # Estado impossível: desbloqueado com reason
        if not self.locked and self.lock_reason is not None:
            self.lock_reason = None

        # Estado impossível: lock com interação ativa
        if self.locked and self.interaction_enabled:
            self.interaction_enabled = False

        # Estado impossível: unlock com interação bloqueada
        if not self.locked and not self.interaction_enabled:
            self.interaction_enabled = True

    # ==============================
    # Serialização (futuro: persistência)
    # ==============================

    def to_dict(self):
        return {
            "slot_id": self.slot_id,
            "locked": self.locked,
            "lock_reason": self.lock_reason,
            "interaction_enabled": self.interaction_enabled,
        }

    def from_dict(self, data: dict):
        self.locked = data.get("locked", False)
        self.lock_reason = data.get("lock_reason", None)
        self.interaction_enabled = data.get("interaction_enabled", True)

        self.validate()
