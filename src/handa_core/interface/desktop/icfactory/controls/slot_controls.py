# controls/slot_controls.py
from state_machine.slot_states import SlotState
from state_machine.validators import can_stop_slot, can_reset_slot
from controls.confirmations import require_confirmation


class SlotControls:
    def __init__(self, core_commands):
        self._commands = core_commands

    def stop(self, slot_id: str, slot_state: SlotState, confirmed: bool):
        require_confirmation("SLOT_STOP", confirmed)

        if not can_stop_slot(slot_state):
            return {"accepted": False, "reason": "INVALID_STATE"}

        return self._commands.stop_slot(slot_id)

    def reset(self, slot_id: str, slot_state: SlotState):
        if not can_reset_slot(slot_state):
            return {"accepted": False, "reason": "INVALID_STATE"}

        return self._commands.reset_slot(slot_id)
