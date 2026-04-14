import tkinter as tk


class SlotCard(tk.Frame):
    def __init__(self, master, slot_data: dict, on_select):
        super().__init__(
            master,
            relief="ridge",
            borderwidth=1,
            padx=6,
            pady=4
        )

        self.on_select = on_select
        self.slot_data = None

        self.label = tk.Label(
            self,
            justify="left",
            anchor="w"
        )
        self.label.pack(fill="both", expand=True)

        # clique em qualquer parte do card
        self.bind("<Button-1>", self._clicked)
        self.label.bind("<Button-1>", self._clicked)

        # primeira renderização
        self.update(slot_data)

    def _clicked(self, _event):
        if self.slot_data:
            self.on_select(self.slot_data["slot_id"])

    def update(self, slot_data: dict):
        """
        Atualiza o conteúdo do card SEM recriar widget.
        """
        self.slot_data = slot_data
        self.label.config(text=self._format_text())

    def _format_text(self) -> str:
        return (
            f"{self.slot_data['slot_id']}\n"
            f"{self.slot_data['symbol']}\n"
            f"{self.slot_data['status']}"
        )
