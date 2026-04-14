import tkinter as tk


class HeaderAutoControl(tk.Frame):
    """
    Controle AUTO do HEADER.

    Responsabilidade única:
    - Iniciar / Parar o AutoLoop
    - Refletir o estado real via auto_controller.is_running
    """

    def __init__(self, master, auto_controller, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        self.auto_controller = auto_controller

        self._build_ui()
        self.sync_state()

    def _build_ui(self):
        self.btn_auto = tk.Button(
            self,
            text="▶ INICIAR AUTO",
            width=18,
            command=self.toggle_auto
        )
        self.btn_auto.pack(padx=8, pady=6)

    def toggle_auto(self):
        """
        Alterna o estado do AUTO.
        Nenhuma lógica aqui — apenas repasse ao controller.
        """
        if self.auto_controller.is_running:
            self.auto_controller.stop()
        else:
            self.auto_controller.start()

        self.sync_state()

    def sync_state(self):
        """
        Sincroniza o texto do botão com o estado real do AUTO.
        """
        if self.auto_controller.is_running:
            self.btn_auto.config(text="⏸ PARAR AUTO")
        else:
            self.btn_auto.config(text="▶ INICIAR AUTO")
