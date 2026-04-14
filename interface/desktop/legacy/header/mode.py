import tkinter as tk
from core.execution_mode import get_execution_mode


class HeaderMode(tk.Frame):
    """
    Componente visual do modo de execução.
    Apenas REFLETE o estado do core.
    """

    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        self.label = tk.Label(self, font=("Segoe UI", 9, "bold"))
        self.label.pack(padx=8, pady=6)

        self.refresh()

    def refresh(self):
        """
        Atualiza o texto conforme o modo real do sistema.
        """
        mode = get_execution_mode()
        self.label.config(
            text=f"MODE: {mode.value}",
            fg="#aa4444" if mode.value == "LIVE" else "#4444aa"
        )
