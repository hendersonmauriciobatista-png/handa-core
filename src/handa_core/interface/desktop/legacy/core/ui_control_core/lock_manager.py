# lock_manager.py
# ==============================
# UI Control Core — Lock Manager
# FASE 1: Controle Humano
# Sistema: H&A / ALFRED IA
# ==============================

from .slot_state import SlotControlState


class LockManager:
    """
    Gerencia proteção lógica dos slots.
    Implementa lock real (não apenas visual).
    """

    # ==============================
    # Lock / Unlock
    # ==============================

    def lock(self, slot_state: SlotControlState, reason: str = "manual"):
        """
        Bloqueia o slot.
        reason: manual | system | policy
        """
        if not slot_state:
            return

        slot_state.lock(reason)
        slot_state.validate()

    def unlock(self, slot_state: SlotControlState):
        """
        Desbloqueia o slot.
        """
        if not slot_state:
            return

        slot_state.unlock()
        slot_state.validate()

    # ==============================
    # Estado
    # ==============================

    def is_locked(self, slot_state: SlotControlState) -> bool:
        """Retorna se o slot está bloqueado."""
        return slot_state.locked

    def get_lock_reason(self, slot_state: SlotControlState):
        """Retorna o motivo do lock."""
        return slot_state.lock_reason
