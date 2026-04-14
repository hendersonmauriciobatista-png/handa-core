# ============================================================
# ui_event_bridge_adapter.py
# Adaptador de eventos CORE → UI
# Sistema: H&A + ALFRED IA
# ============================================================

from h_a.enums.states import SlotState
from h_a.core.event_bus import event_bus


class UIEventBridgeAdapter:
    """
    Traduz eventos do CORE para o EventBus da UI.
    A UI apenas reage — nunca decide estado.
    """

    def subscribe(self, callback):
        """
        UI se registra para receber eventos traduzidos.
        """
        event_bus.subscribe("STATE_CHANGED", callback)

    # ========================================================
    # CORE → UI
    # ========================================================

    def on_slot_update(self, payload: dict):
        """
        Recebe eventos do CORE e traduz para formato de UI.
        """
        slot_id = payload.get("slot_id")
        state = payload.get("state")

        ui_state = self._translate_state(state)

        event_bus.emit(
            "STATE_CHANGED",
            entity_type="Slot",
            entity_id=slot_id,
            state=ui_state,
        )

    # ========================================================
    # TRADUÇÃO DE ESTADOS
    # ========================================================

    def _translate_state(self, state: str) -> SlotState:
        if state in (
            "ANALYZING",
            "READY",
            "ENTERING",
            "TRADING",
            "EXITING",
            "FINALIZING",
        ):
            return SlotState.RUNNING

        if state in ("IDLE", "STOPPED"):
            return SlotState.STOPPED

        return SlotState.ERROR


# ============================================================
# INSTÂNCIA GLOBAL (USADA PELA UI)
# ============================================================

event_bridge = UIEventBridgeAdapter()
