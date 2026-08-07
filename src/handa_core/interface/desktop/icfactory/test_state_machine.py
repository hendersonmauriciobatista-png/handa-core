# test_state_machine.py

from state_machine.system_states import SystemState
from state_machine.slot_states import SlotState
from state_machine.validators import (
    can_start_system,
    can_pause_system,
    can_stop_slot,
    can_reset_slot,
    validate_slot_transition,
)

print("=== TESTE BLOCO 1 — STATE MACHINE ===")

# -----------------
# TESTES DE SISTEMA
# -----------------
assert can_start_system(SystemState.SYSTEM_READY) is True
assert can_start_system(SystemState.SYSTEM_STOPPED) is True
assert can_start_system(SystemState.SYSTEM_RUNNING) is False

assert can_pause_system(SystemState.SYSTEM_RUNNING) is True
assert can_pause_system(SystemState.SYSTEM_PAUSED) is False

print("✔ Testes de estado global OK")

# -----------------
# TESTES DE SLOT
# -----------------
assert can_stop_slot(SlotState.READY) is True
assert can_stop_slot(SlotState.TRADING) is True
assert can_stop_slot(SlotState.DRAINING) is False

assert can_reset_slot(SlotState.COMPLETED) is True
assert can_reset_slot(SlotState.ERROR) is True
assert can_reset_slot(SlotState.TRADING) is False

print("✔ Testes de comandos de slot OK")

# -----------------
# TESTES DE TRANSIÇÕES ILEGAIS
# -----------------
illegal_cases = [
    (SlotState.IDLE, SlotState.TRADING),
    (SlotState.ANALYZING, SlotState.TRADING),
    (SlotState.DRAINING, SlotState.TRADING),
    (SlotState.TRADING, SlotState.STOPPED),
]

for from_state, to_state in illegal_cases:
    try:
        validate_slot_transition(from_state, to_state)
        raise RuntimeError("ERRO: transição ilegal não bloqueada")
    except ValueError:
        pass  # esperado

print("✔ Transições ilegais bloqueadas corretamente")

# -----------------
# TESTE DE TRANSIÇÃO VÁLIDA
# -----------------
validate_slot_transition(SlotState.READY, SlotState.TRADING)
print("✔ Transição válida aceita")

print("\n🎉 BLOCO 1 VALIDADO COM SUCESSO")
