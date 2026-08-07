from enum import Enum, auto


class HandaState(Enum):
    ANALISE = auto()
    TRANSFERENCIA = auto()
    TRADING_AGUARDANDO = auto()
    TRADING_EXECUTANDO = auto()
    TRADING_FINALIZADO = auto()


class StateMachine:
    def __init__(self):
        self.state = HandaState.ANALISE

    def transition_to(self, new_state: HandaState):
        if not self._is_valid_transition(new_state):
            raise ValueError(
                f"Transição inválida: {self.state.name} → {new_state.name}"
            )
        self.state = new_state

    def _is_valid_transition(self, new_state: HandaState) -> bool:
        valid_transitions = {
            HandaState.ANALISE: [HandaState.TRANSFERENCIA],
            HandaState.TRANSFERENCIA: [HandaState.TRADING_AGUARDANDO],
            HandaState.TRADING_AGUARDANDO: [HandaState.TRADING_EXECUTANDO],
            HandaState.TRADING_EXECUTANDO: [HandaState.TRADING_FINALIZADO],
            HandaState.TRADING_FINALIZADO: [HandaState.ANALISE],
        }
        return new_state in valid_transitions[self.state]
