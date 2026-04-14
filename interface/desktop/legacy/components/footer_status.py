import tkinter as tk

class FooterStatus(tk.Frame):
    def __init__(self, master, risk_state):
        super().__init__(master, relief="raised", borderwidth=1)
        self.risk_state = risk_state
        self.label = tk.Label(self, text=self._text())
        self.label.pack(fill="x")

    def refresh(self):
        self.label.config(text=self._text())

    def _text(self):
        return (
            f"Risco: {self.risk_state.status} | "
            f"Evento: {self.risk_state.last_event or '-'}"
        )
