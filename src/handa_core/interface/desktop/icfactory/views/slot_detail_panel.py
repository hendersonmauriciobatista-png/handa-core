# interface/desktop/icfactory/views/slot_detail_panel.py

import tkinter as tk


class SlotDetailPanel(tk.Frame):
    """
    Painel de detalhes do Slot.
    Agora 100% baseado no estado estrutural do SlotManager.
    """

    def __init__(self, parent, viewmodel):
        super().__init__(parent, bg="#2A2A2A", padx=20, pady=20)

        self.viewmodel = viewmodel

        tk.Label(
            self,
            text="Detalhes do Slot",
            fg="white",
            bg="#2A2A2A",
            font=("Arial", 14, "bold")
        ).pack(pady=(0, 15))

        self.slot_id_label = self._create_label()
        self.state_label = self._create_label()
        self.strength_label = self._create_label()
        self.pair_label = self._create_label()

        self._auto_refresh()

    # ==========================
    # UI Helpers
    # ==========================

    def _create_label(self):
        label = tk.Label(
            self,
            text="—",
            fg="white",
            bg="#2A2A2A",
            font=("Arial", 11)
        )
        label.pack(anchor="w", pady=2)
        return label

    # ==========================
    # Atualização automática
    # ==========================

    def _auto_refresh(self):
        self.refresh()
        self.after(1000, self._auto_refresh)

    def refresh(self):
        active_snapshot = self.viewmodel.get_active_slot_snapshot()

        if not active_snapshot:
            self.slot_id_label.config(text="Nenhum slot ativo")
            self.state_label.config(text="")
            self.strength_label.config(text="")
            self.pair_label.config(text="")
            return

        self.slot_id_label.config(
            text=f"Slot ID: {active_snapshot['slot_id']}"
        )

        self.state_label.config(
            text=f"Estado: {active_snapshot['analysis_state']}"
        )

        strength = active_snapshot.get("analysis_strength")
        self.strength_label.config(
            text=f"Força: {strength if strength is not None else '-'}"
        )

        self.pair_label.config(
            text=f"Par: {active_snapshot['pair'] if active_snapshot['pair'] else '-'}"
        )
