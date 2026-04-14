# interface/desktop/center/slots_area.py

import tkinter as tk
from typing import Dict, List

from interface.desktop.center.slot_panel import SlotPanel


class SlotsArea(tk.Frame):
    """
    Área de slots — versão viva, reativa e global.
    Com persistência visual de foco.
    """

    def __init__(self, master, slot_ids: List[int], on_select):
        super().__init__(
            master,
            bg="#f2f2f2"
        )

        self.slot_ids = slot_ids
        self.on_select = on_select
        self._slots: Dict[int, SlotPanel] = {}

        self.pack(fill="both", expand=True)
        self._build_ui()

    # =====================================================
    # UI
    # =====================================================
    def _build_ui(self):
        for slot_id in self.slot_ids:
            slot = SlotPanel(
                self,
                slot_id=slot_id,
                on_select=self.on_select
            )

            slot.pack(
                pady=8,
                padx=16,
                fill="x"
            )

            self._slots[slot_id] = slot

    # =====================================================
    # UPDATE GLOBAL
    # =====================================================
    def update_from_snapshots(self, snapshots: Dict[int, dict]):
        for slot_id, snapshot in snapshots.items():
            panel = self._slots.get(slot_id)
            if panel:
                panel.update_from_snapshot(snapshot)

    # =====================================================
    # ACTIVE CONTROL
    # =====================================================
    def set_active(self, slot_id: int):
        for sid, panel in self._slots.items():
            if sid == slot_id:
                panel.set_active(True)
            else:
                panel.set_active(False)
