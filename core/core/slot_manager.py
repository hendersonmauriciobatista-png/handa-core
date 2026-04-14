# core/slot_manager.py
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.slot import Slot




class SlotManager:
    """
    Autoridade oficial dos Slots.
    Responsável por:
    - Gerenciar slots
    - Definir slot ativo
    - Expor snapshots para ViewModel
    """

    def __init__(self):
        self.slots: dict[int, "Slot"] = {}
        self._active_slot_id: Optional[int] = None

    # ==========================
    # Gestão de Slots
    # ==========================

    def add_slot(self, slot_id: int, slot: "Slot") -> None:
        self.slots[slot_id] = slot

    def remove_slot(self, slot_id: int) -> None:
        if slot_id in self.slots:
            del self.slots[slot_id]

            if self._active_slot_id == slot_id:
                self._active_slot_id = None

    # ==========================
    # Slot Ativo
    # ==========================

    @property
    def active_slot_id(self) -> Optional[int]:
        return self._active_slot_id

    def set_active_slot(self, slot_id: int) -> None:
        if slot_id not in self.slots:
            raise ValueError(f"Slot {slot_id} does not exist.")

        self._active_slot_id = slot_id

    def get_active_slot(self) -> Optional["Slot"]:
        if self._active_slot_id is None:
            return None
        return self.slots.get(self._active_slot_id)

    # ==========================
    # Compatibilidade ViewModel
    # ==========================

    def snapshot_all(self) -> dict:
        """
        Retorna snapshots estruturais para o ViewModel.
        """
        return {
            slot_id: slot.snapshot()
            for slot_id, slot in self.slots.items()
        }
