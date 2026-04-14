from HANDA_CORE.core.slot import Slot



class TransferEngine:
    def transfer(self, analysis_slot: Slot, trading_slot: Slot):
        if analysis_slot.locked:
            return False

        trading_slot.token = analysis_slot.token
        trading_slot.status_text = "AGUARDANDO NOVO CICLO"

        analysis_slot.reset()
        return True
