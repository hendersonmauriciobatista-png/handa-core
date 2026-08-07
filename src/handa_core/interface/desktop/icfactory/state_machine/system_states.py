# state_machine/system_states.py
from enum import Enum


class SystemState(str, Enum):
    SYSTEM_IDLE = "SYSTEM_IDLE"
    SYSTEM_READY = "SYSTEM_READY"
    SYSTEM_RUNNING = "SYSTEM_RUNNING"
    SYSTEM_PAUSED = "SYSTEM_PAUSED"
    SYSTEM_DRAINING = "SYSTEM_DRAINING"
    SYSTEM_STOPPED = "SYSTEM_STOPPED"
    SYSTEM_ERROR = "SYSTEM_ERROR"


# Estados a partir dos quais o sistema pode iniciar
STARTABLE_STATES = {
    SystemState.SYSTEM_READY,
    SystemState.SYSTEM_STOPPED,
}

# Estados que permitem pausa
PAUSABLE_STATES = {
    SystemState.SYSTEM_RUNNING,
}

# Estados irreversíveis (somente saída por fluxo interno)
IRREVERSIBLE_STATES = {
    SystemState.SYSTEM_DRAINING,
}
