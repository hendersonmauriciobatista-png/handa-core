from typing import Dict
from core_logic.enums import SystemMode, ConnectionState
from legacy.slot import Slot


class SystemState:
    """
    Estado global do H&A.
    Orquestra slots e estados globais.
    Não conhece UI nem executor.
    """

    def __init__(self, slot_count: int = 6):
        # Estados globais
        self.mode = SystemMode.MOCK
        self.connection = ConnectionState.DISCONNECTED

        # Slots
        self.slots: Dict[int, Slot] = {
            i: Slot(i) for i in range(1, slot_count + 1)
        }

        # Métricas globais (derivadas)
        self.balance_usdc: float = 0.0
        self.total_profit_usdc: float = 0.0

    # =========================
    # CONTROLE GLOBAL
    # =========================

    def set_mode(self, mode: SystemMode):
        self.mode = mode

    def set_connection(self, state: ConnectionState):
        self.connection = state

    # =========================
    # SLOTS
    # =========================

    def get_slot(self, slot_id: int) -> Slot:
        if slot_id not in self.slots:
            raise ValueError(f"Slot {slot_id} não existe")
        return self.slots[slot_id]

    def all_slots(self):
        return self.slots.values()

    # =========================
    # SNAPSHOT
    # =========================

    def snapshot(self) -> dict:
        """
        Snapshot global para UI / logs.
        """
        return {
            "mode": self.mode.name,
            "connection": self.connection.name,
            "balance_usdc": self.balance_usdc,
            "total_profit_usdc": self.total_profit_usdc,
            "slots": {
                slot_id: slot.snapshot()
                for slot_id, slot in self.slots.items()
            },
        }