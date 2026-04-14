from core.slot import Slot
from core.decision_cycle import DecisionCycle


class SlotManager:

    TOTAL_SLOTS = 12

    # =====================================================
    # INIT
    # =====================================================
    def __init__(self, executor_factory):
        self.executor_factory = executor_factory
        self.slots = {}
        self._initialize_slots()

    # =====================================================
    # CRIAÇÃO DOS 12 SLOTS FIXOS
    # =====================================================
    def _initialize_slots(self):
        for i in range(1, self.TOTAL_SLOTS + 1):
            executor = self.executor_factory()
            slot = Slot(slot_id=i)
            decision_cycle = DecisionCycle(executor)

            self.slots[i] = {
                "slot": slot,
                "decision_cycle": decision_cycle,
                "executor": executor,
                "state": "IDLE"
            }

    # =====================================================
    # CONTROLE DE ATIVAÇÃO
    # =====================================================
    def activate_slot(self, slot_id: int):
        for i in self.slots:
            if i == slot_id:
                self.slots[i]["state"] = "RUNNING"
            else:
                self.slots[i]["state"] = "PAUSED"

    def set_state(self, slot_id: int, state: str):
        if slot_id in self.slots:
            self.slots[slot_id]["state"] = state

    def get_slot(self, slot_id: int):
        return self.slots.get(slot_id)

    # =====================================================
    # EXECUÇÃO CONTROLADA
    # =====================================================
    def run_slot_cycle(self, slot_id: int, **kwargs):
        slot_data = self.slots.get(slot_id)

        if not slot_data:
            return None

        if slot_data["state"] != "RUNNING":
            return None

        return slot_data["decision_cycle"].run_cycle(**kwargs)

    # =====================================================
    # SNAPSHOT PARA UI (COMPATÍVEL COM AppViewModel)
    # =====================================================
    def snapshot_all(self):
        """
        Retorna dict indexado por slot_id.
        Compatível com AppViewModel.
        """

        snapshots = {}

        for slot_id, data in self.slots.items():
            state = data["state"]

            if state == "RUNNING":
                analysis_state = "TRADING"
            elif state == "PAUSED":
                analysis_state = "ANALYZED"
            else:
                analysis_state = "IDLE"

            snapshots[slot_id] = {
                "slot_id": slot_id,
                "analysis_state": analysis_state,
                "analysis_strength": None,
                "trade_state": None,
                "symbol": None,
                "locked": False
            }

        return snapshots
