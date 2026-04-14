# test_controls.py

from controls.system_controls import SystemControls
from controls.slot_controls import SlotControls
from state_machine.system_states import SystemState
from state_machine.slot_states import SlotState
from controls.confirmations import ConfirmationRequired


# Mock do CoreCommands
class MockCoreCommands:
    def start_system(self):
        return {"accepted": True}

    def pause_system(self):
        return {"accepted": True}

    def resume_system(self):
        return {"accepted": True}

    def stop_system(self):
        return {"accepted": True}

    def stop_slot(self, slot_id):
        return {"accepted": True, "slot_id": slot_id}

    def reset_slot(self, slot_id):
        return {"accepted": True, "slot_id": slot_id}


core = MockCoreCommands()

system = SystemControls(core)
slot = SlotControls(core)

# ---- Sistema ----
assert system.start(SystemState.SYSTEM_READY)["accepted"] is True
assert system.pause(SystemState.SYSTEM_RUNNING)["accepted"] is True

try:
    system.stop(SystemState.SYSTEM_RUNNING, confirmed=False)
    raise RuntimeError("ERRO: stop sem confirmação passou")
except ConfirmationRequired:
    pass

assert system.stop(SystemState.SYSTEM_RUNNING, confirmed=True)["accepted"] is True

print("✔ SystemControls OK")

# ---- Slot ----
assert slot.stop("S1", SlotState.READY, confirmed=True)["accepted"] is True
assert slot.reset("S1", SlotState.COMPLETED)["accepted"] is True

try:
    slot.stop("S1", SlotState.READY, confirmed=False)
    raise RuntimeError("ERRO: slot stop sem confirmação passou")
except ConfirmationRequired:
    pass

print("✔ SlotControls OK")

print("🎉 BLOCO 3 VALIDADO COM SUCESSO")
