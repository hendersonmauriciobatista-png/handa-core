# state_machine/slot_states.py
from enum import Enum


class SlotState(str, Enum):
    IDLE = "IDLE"
    ANALYZING = "ANALYZING"
    SETUP_READY = "SETUP_READY"
    QA_CHECK = "QA_CHECK"
    BLOCKED = "BLOCKED"
    READY = "READY"
    TRADING = "TRADING"
    DRAINING = "DRAINING"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


# Estados finais que permitem reset
RESETTABLE_STATES = {
    SlotState.COMPLETED,
    SlotState.ERROR,
    SlotState.BLOCKED,
}

# Estados onde o slot pode ser interrompido
STOPPABLE_STATES = {
    SlotState.READY,
    SlotState.TRADING,
}

# Estados críticos (não aceitam comandos humanos)
CRITICAL_STATES = {
    SlotState.DRAINING,
}
