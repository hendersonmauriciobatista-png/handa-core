import tkinter as tk

class SlotFocusPanel(tk.Frame):
    def __init__(self, master, registry, ui_state):
        super().__init__(master, relief="sunken", borderwidth=1)
        self.registry = registry
        self.ui_state = ui_state
        self.label = tk.Label(self, text="Nenhum slot selecionado")
        self.label.pack(fill="both", expand=True)

    def refresh(self):
        slot_id = self.ui_state.active_slot_id
        if not slot_id:
            self.label.config(text="Nenhum slot selecionado")
            return

        slot = self.registry.get(slot_id)
        if not slot:
            self.label.config(text="Slot não encontrado")
            return

        self.label.config(
            text=(
                f"SLOT EM FOCO\n\n"
                f"ID: {slot['slot_id']}\n"
                f"PAR: {slot['symbol']}\n"
                f"STATUS: {slot['status']}\n"
                f"ÚLTIMO EVENTO: {slot['last_event']}"
            )
        )
