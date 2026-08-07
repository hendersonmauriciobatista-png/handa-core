import tkinter as tk

from interface.desktop.center.slot_panel import SlotPanel


class CenterArea(tk.Frame):
    """
    Área de slots.
    Não contém métricas.
    Não contém lógica.
    """

    def __init__(self, master, slot_controller, side: str):
        super().__init__(master, bg="#ECECEC")
        self.slot_controller = slot_controller
        self.side = side

        self._build_ui()

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):
        slots = (1, 2, 3) if self.side == "left" else (4, 5, 6)

        for slot_id in slots:
            panel = SlotPanel(self, slot_id)
            panel.pack(fill="x", pady=6)
