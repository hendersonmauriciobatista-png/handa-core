from HANDA_CORE.core.slot import Slot



class AnalysisEngine:
    UNLOCK_THRESHOLD = 80

    def __init__(self, slot: Slot):
        self.slot = slot

    def update_analysis(self, token: str, strength: int):
        self.slot.token = token
        self.slot.strength = max(0, min(100, strength))

        if self.slot.strength >= self.UNLOCK_THRESHOLD:
            self.slot.unlock()
            return True  # pronto para transferência

        self.slot.lock()
        return False
