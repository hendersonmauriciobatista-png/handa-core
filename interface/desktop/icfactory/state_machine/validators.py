# state_machine/validators.py
from state_machine.system_states import SystemState
from state_machine.slot_states import SlotState


# =========================
# VALIDADORES DE SISTEMA
# =========================

def can_start_system(current_state: SystemState) -> bool:
    return current_state in {
        SystemState.SYSTEM_READY,
        SystemState.SYSTEM_STOPPED,
    }


def can_pause_system(current_state: SystemState) -> bool:
    return current_state == SystemState.SYSTEM_RUNNING


def can_resume_system(current_state: SystemState) -> bool:
    return current_state == SystemState.SYSTEM_PAUSED


def can_stop_system(current_state: SystemState) -> bool:
    # Stop é sempre permitido (Policy decide o efeito)
    return True


# =========================
# VALIDADORES DE SLOT
# =========================

def can_stop_slot(slot_state: SlotState) -> bool:
    return slot_state in {
        SlotState.READY,
        SlotState.TRADING,
    }


def can_reset_slot(slot_state: SlotState) -> bool:
    return slot_state in {
        SlotState.COMPLETED,
        SlotState.ERROR,
        SlotState.BLOCKED,
    }


def is_illegal_transition(from_state: SlotState, to_state: SlotState) -> bool:
    """
    Define transições TERMINANTEMENTE proibidas.
    """
    illegal_transitions = {
        (SlotState.IDLE, SlotState.TRADING),
        (SlotState.ANALYZING, SlotState.TRADING),
        (SlotState.QA_CHECK, SlotState.TRADING),
        (SlotState.BLOCKED, SlotState.TRADING),
        (SlotState.ERROR, SlotState.TRADING),
        (SlotState.DRAINING, SlotState.TRADING),
        (SlotState.TRADING, SlotState.STOPPED),
    }

    return (from_state, to_state) in illegal_transitions


def validate_slot_transition(from_state: SlotState, to_state: SlotState) -> None:
    """
    Lança exceção se a transição for ilegal.
    """
    if is_illegal_transition(from_state, to_state):
        raise ValueError(
            f"Illegal slot state transition: {from_state.value} → {to_state.value}"
        )
