# interface/desktop/icfactory/views/slot_panel.py

import tkinter as tk


class SlotPanel(tk.Frame):
    """
    Painel visual premium dos 12 slots.
    Destaque elegante para slot ativo.
    """

    TOTAL_SLOTS = 12

    COLOR_BG_DEFAULT = "#2F2F2F"
    COLOR_BG_HOVER = "#3A3A3A"
    COLOR_BG_ACTIVE = "#1E8E3E"      # Verde institucional profundo
    COLOR_BORDER_ACTIVE = "#66FF99"  # Borda luminosa suave
    COLOR_TEXT = "white"

    def __init__(self, parent, viewmodel, slot_manager):
        super().__init__(parent, bg="#1E1E1E")

        self.viewmodel = viewmodel
        self.slot_manager = slot_manager
        self.slot_buttons = {}

        self._build_slots()
        self._auto_refresh()

    # ==========================
    # Construção dos Slots
    # ==========================

    def _build_slots(self):
        for i in range(1, self.TOTAL_SLOTS + 1):
            frame = tk.Frame(self, bg=self.COLOR_BG_DEFAULT, highlightthickness=0)

            btn = tk.Button(
                frame,
                text=f"Slot {i}",
                width=18,
                height=3,
                bg=self.COLOR_BG_DEFAULT,
                fg=self.COLOR_TEXT,
                relief="flat",
                bd=0,
                activebackground=self.COLOR_BG_HOVER,
                command=lambda slot_id=i: self._activate(slot_id)
            )

            btn.pack(fill="both", expand=True)

            row = (i - 1) // 4
            col = (i - 1) % 4

            frame.grid(row=row, column=col, padx=12, pady=12)

            self.slot_buttons[i] = (frame, btn)

    # ==========================
    # Ativação
    # ==========================

    def _activate(self, slot_id):
        self.slot_manager.set_active_slot(slot_id)

    # ==========================
    # Atualização
    # ==========================

    def _auto_refresh(self):
        self.refresh()
        self.after(500, self._auto_refresh)

    def refresh(self):
        slots_view = self.viewmodel.get_slots_view()
        active_id = self.slot_manager.active_slot_id

        for slot_data in slots_view:
            pair = self.slot_buttons.get(slot_data.slot_id)

            if not pair:
                continue

            frame, btn = pair
            is_active = slot_data.slot_id == active_id

            if is_active:
                frame.config(
                    bg=self.COLOR_BORDER_ACTIVE,
                    highlightthickness=2,
                    highlightbackground=self.COLOR_BORDER_ACTIVE
                )
                btn.config(
                    bg=self.COLOR_BG_ACTIVE,
                    activebackground=self.COLOR_BG_ACTIVE
                )
            else:
                frame.config(
                    bg=self.COLOR_BG_DEFAULT,
                    highlightthickness=0
                )
                btn.config(
                    bg=self.COLOR_BG_DEFAULT,
                    activebackground=self.COLOR_BG_HOVER
                )

            btn.config(
                text=f"Slot {slot_data.slot_id}\n{slot_data.status_text}"
            )
