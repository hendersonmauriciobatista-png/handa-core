# ui_control_adapter.py
# ==============================
# UI → UIControlCore Adapter
# Integração FASE 1
# Sistema: H&A / ALFRED IA
# ==============================

from interface.desktop.core.ui_control_core.core import UIControlCore
from interface.desktop.core.ui_control_core.authority_manager import ActionSource


class UIControlAdapter:
    """
    Adaptador entre UI Controller e UIControlCore.
    Traduz eventos visuais em eventos lógicos.
    """

    def __init__(self):
        self.core = UIControlCore()

    # ==============================
    # Slots
    # ==============================

    def register_slot(self, slot_id: str):
        self.core.register_slot(slot_id)

    def remove_slot(self, slot_id: str):
        self.core.remove_slot(slot_id)

    # ==============================
    # Eventos de UI
    # ==============================

    def pin_slot(self, slot_id: str):
        self.core.dispatch(
            name="PIN",
            source=ActionSource.OPERATOR,
            payload={"slot_id": slot_id}
        )

    def unpin(self):
        self.core.dispatch(
            name="UNPIN",
            source=ActionSource.OPERATOR
        )

    def lock_slot(self, slot_id: str):
        self.core.dispatch(
            name="LOCK",
            source=ActionSource.OPERATOR,
            payload={"slot_id": slot_id, "reason": "manual"}
        )

    def unlock_slot(self, slot_id: str):
        self.core.dispatch(
            name="UNLOCK",
            source=ActionSource.OPERATOR,
            payload={"slot_id": slot_id}
        )

    def auto_focus(self, slot_id: str):
        self.core.dispatch(
            name="AUTO_FOCUS",
            source=ActionSource.SYSTEM,
            payload={"slot_id": slot_id}
        )

    def override_on(self):
        self.core.dispatch(
            name="OVERRIDE_ON",
            source=ActionSource.OPERATOR
        )

    def override_off(self):
        self.core.dispatch(
            name="OVERRIDE_OFF",
            source=ActionSource.OPERATOR
        )

    def reset(self):
        self.core.dispatch(
            name="RESET",
            source=ActionSource.OPERATOR
        )

    # ==============================
    # Estado para UI
    # ==============================

    def get_ui_state(self):
        return self.core.get_ui_state()

    def get_slot_state(self, slot_id: str):
        return self.core.get_slot_state(slot_id)
