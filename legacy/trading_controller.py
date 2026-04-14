from HANDA_CORE.state.state_machine import HandaState
from HANDA_CORE.core.slot import Slot



class TradingController:
    def __init__(self, slot: Slot):
        self.slot = slot

    def on_state_change(self, state: HandaState):
        if state == HandaState.TRADING_AGUARDANDO:
            self.slot.status_text = "AGUARDANDO NOVO CICLO"

        elif state == HandaState.TRADING_EXECUTANDO:
            self.slot.status_text = "TRADING EM EXECUÇÃO"

        elif state == HandaState.TRADING_FINALIZADO:
            self.slot.status_text = "TRADING FINALIZADO"
