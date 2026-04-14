import tkinter as tk


class HeaderStatus(tk.Frame):
    """
    Status visual do sistema.
    Mostra estado do AUTO (ON / OFF).
    """

    def __init__(self, master, auto_controller, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        self.auto_controller = auto_controller

        self._build_ui()
        self.sync()

    def _build_ui(self):
        self.lbl_auto = tk.Label(
            self,
            text="AUTO: OFF",
            fg="#aa4444"
        )
        self.lbl_auto.pack(padx=8, pady=6)

    def sync(self):
        """
        Sincroniza o status visual com o estado real do AUTO.
        """
        if self.auto_controller.is_running:
            self.lbl_auto.config(text="AUTO: ON", fg="#44aa44")
        else:
            self.lbl_auto.config(text="AUTO: OFF", fg="#aa4444")
