import tkinter as tk
from tkinter import messagebox


class HeaderKeys(tk.Frame):
    """
    Header KEYS — H&A
    Controle de Conectar / Desconectar chaves
    com feedback visual (UI antiga restaurada)
    """

    def __init__(self, master, key_manager, on_state_change=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        self.key_manager = key_manager
        self.on_state_change = on_state_change

        self._build_ui()
        self._update_status()

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):
        self.status_label = tk.Label(
            self,
            text="SEM CHAVES",
            fg="#888888"
        )
        self.status_label.pack(side="left", padx=6)

        self.btn_connect = tk.Button(
            self,
            text="Conectar",
            command=self._on_connect,
            width=10
        )
        self.btn_connect.pack(side="left", padx=4)

        self.btn_disconnect = tk.Button(
            self,
            text="Desconectar",
            command=self._on_disconnect,
            width=12
        )
        self.btn_disconnect.pack(side="left", padx=4)

    # =====================================================
    # AÇÕES
    # =====================================================

    def _on_connect(self):
        # ⚠️ Aqui é conexão lógica (UI antiga)
        ok = self.key_manager.connect_keys(
            self.key_manager.api_key,
            self.key_manager.api_secret
        )

        if ok:
            messagebox.showinfo(
                "H&A — Segurança",
                "CHAVES CONECTADAS COM SUCESSO\nSistema pronto para LIVE"
            )
            self._update_status()
            if self.on_state_change:
                self.on_state_change()
        else:
            messagebox.showerror(
                "H&A — Segurança",
                "Falha ao conectar chaves"
            )

    def _on_disconnect(self):
        if not self.key_manager.keys_loaded:
            return

        self.key_manager.disconnect_keys()

        messagebox.showwarning(
            "H&A — Segurança",
            "CHAVES DESCONECTADAS\nSistema em modo MOCK"
        )

        self._update_status()
        if self.on_state_change:
            self.on_state_change()

    # =====================================================
    # STATUS
    # =====================================================

    def _update_status(self):
        if self.key_manager.keys_loaded:
            self.status_label.config(
                text="CONECTADO",
                fg="#2ecc71"
            )
        else:
            self.status_label.config(
                text="SEM CHAVES",
                fg="#888888"
            )
