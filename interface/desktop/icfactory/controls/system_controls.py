# controls/system_controls.py
from state_machine.system_states import SystemState
from state_machine.validators import (
    can_start_system,
    can_pause_system,
    can_resume_system,
    can_stop_system,
)
from controls.confirmations import require_confirmation


class SystemControls:
    def __init__(self, core_commands):
        self._commands = core_commands

    def start(self, current_state: SystemState):
        if not can_start_system(current_state):
            return {"accepted": False, "reason": "INVALID_STATE"}
        return self._commands.start_system()

    def pause(self, current_state: SystemState):
        if not can_pause_system(current_state):
            return {"accepted": False, "reason": "INVALID_STATE"}
        return self._commands.pause_system()

    def resume(self, current_state: SystemState):
        if not can_resume_system(current_state):
            return {"accepted": False, "reason": "INVALID_STATE"}
        return self._commands.resume_system()

    def stop(self, current_state: SystemState, confirmed: bool):
        require_confirmation("SYSTEM_STOP", confirmed)
        if not can_stop_system(current_state):
            return {"accepted": False, "reason": "INVALID_STATE"}
        return self._commands.stop_system()
