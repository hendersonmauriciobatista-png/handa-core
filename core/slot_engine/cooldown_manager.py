from .slot_state_machine import CooldownType


class CooldownManager:

    def __init__(self):
        self._cooldown_type = None
        self._active = False

    def activate(self, cooldown_type: CooldownType):
        self._cooldown_type = cooldown_type
        self._active = True

    def reset(self):
        self._cooldown_type = None
        self._active = False

    def is_active(self) -> bool:
        return self._active

    def get_type(self):
        return self._cooldown_type
