import tkinter as tk
from typing import Optional


class SlotView(tk.Frame):
    """
    Slot visual de trading (UI-only).
    """

    def __init__(self, parent, slot_id: int, ui_advisor: Optional[object] = None):
        super().__init__(parent, bg="white", bd=1, relief="solid")

        self.slot_id = slot_id
        self.ui_advisor = ui_advisor
        self.state = "AGUARDANDO NOVO CICLO"

        self._build()
        self._notify_state()

    def _build(self):
        tk.Label(
            self,
            text=f"SLOT {self.slot_id}",
            bg="white",
            fg="black",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=10, pady=(8, 2))

        self.status_label = tk.Label(
            self,
            text=self.state,
            bg="white",
            fg="black",
            font=("Segoe UI", 9)
        )
        self.status_label.pack(anchor="w", padx=10, pady=(0, 8))

        self.btn = tk.Button(
            self,
            text="SIMULAR CICLO",
            bg="white",
            fg="black",
            command=self._simulate
        )
        self.btn.pack(anchor="w", padx=10, pady=(0, 10))

    def _simulate(self):
        if self.state == "AGUARDANDO NOVO CICLO":
            self.set_state("TRADING EM EXECUÇÃO")
            self.after(2000, lambda: self.set_state("TRADING FINALIZADO"))
        else:
            self.set_state("AGUARDANDO NOVO CICLO")

    def set_state(self, state: str):
        self.state = state
        self.status_label.config(text=state)
        self._notify_state()

    def _notify_state(self):
        if self.ui_advisor:
            self.ui_advisor.on_slot_state(
                slot_id=self.slot_id,
                state=self.state
            )

