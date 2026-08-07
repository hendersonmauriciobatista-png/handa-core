from h_a.core.state.system_state import SlotUIState, SlotStatus

class StateEmitter:

    def emit(self, slot) -> SlotUIState:
        return SlotUIState(
            slot_id=slot.id,
            status=SlotStatus(slot.state),
            symbol=slot.symbol,
            last_event=slot.last_event,
            error=slot.error
        )
