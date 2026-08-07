import tkinter as tk
from core.runtime.auto_state import get_auto_state, AutoState


class AutoStatus(tk.Frame):
    """
    Indicador visual do estado do Auto Loop.
    UI BURRA — apenas leitura de estado.
    """

    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        self.label = tk.Label(
            self,
            font=("Segoe UI", 9, "bold")
        )
        self.label.pack(padx=8, pady=4)

        self.refresh()

    def refresh(self):
        """
        Atualiza o texto conforme o AutoState atual.
        """
        state = get_auto_state()

        if state == AutoState.RUNNING:
            self.label.config(
                text="AUTO: ATIVO",
                fg="#228833"
            )
        else:
            self.label.config(
                text="AUTO: INATIVO",
                fg="#aa3333"
            )
