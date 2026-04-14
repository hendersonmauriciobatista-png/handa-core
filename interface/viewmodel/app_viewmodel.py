# interface/viewmodel/app_viewmodel.py

from typing import List
from interface.viewmodel.slot_viewmodel import SlotViewModel, SlotViewData


class AppViewModel:
    """
    ViewModel principal da aplicação ICFactory.
    Orquestra:
    - Visualização dos slots
    - Exposição do slot ativo
    """

    def __init__(self, slot_controller):
        self.slot_controller = slot_controller

    # ==========================
    # SLOTS (Grid)
    # ==========================

    def get_slots_view(self) -> List[SlotViewData]:
        snapshots = self.slot_controller.snapshot_all()

        view_data: List[SlotViewData] = []

        for slot_id in sorted(snapshots.keys()):
            snapshot = snapshots[slot_id]
            vm = SlotViewModel(snapshot)
            view_data.append(vm.build())

        return view_data

    # ==========================
    # SLOT ATIVO (Detail Panel)
    # ==========================

    def get_active_slot_snapshot(self):
        active = self.slot_controller.get_active_slot()
        if not active:
            return None
        return active.snapshot()
