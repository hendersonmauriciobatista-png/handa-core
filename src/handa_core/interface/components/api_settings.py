# ============================================================
# API SETTINGS COMPONENT
# Caixa de configuração das chaves Binance
# ============================================================

import customtkinter as ctk


class APISettings(ctk.CTkToplevel):

    def __init__(self, master, ctx):

        super().__init__(master)

        self.ctx = ctx

        self.title("API Settings")
        self.geometry("420x240")

        # =====================================================
        # API KEY
        # =====================================================

        self.label_key = ctk.CTkLabel(self, text="API Key")
        self.label_key.pack(pady=(20, 5))

        self.entry_key = ctk.CTkEntry(self, width=340)
        self.entry_key.pack()

        # =====================================================
        # API SECRET
        # =====================================================

        self.label_secret = ctk.CTkLabel(self, text="API Secret")
        self.label_secret.pack(pady=(10, 5))

        self.entry_secret = ctk.CTkEntry(self, width=340, show="*")
        self.entry_secret.pack()

        # =====================================================
        # STATUS
        # =====================================================

        self.status_label = ctk.CTkLabel(self, text="")
        self.status_label.pack(pady=12)

        # =====================================================
        # ENTER salva automaticamente
        # =====================================================

        self.entry_key.bind("<Return>", self.save_keys)
        self.entry_secret.bind("<Return>", self.save_keys)

    # =========================================================
    # SALVAR CHAVES
    # =========================================================

    def save_keys(self, event=None):

        api_key = self.entry_key.get().strip()
        api_secret = self.entry_secret.get().strip()

        self.status_label.configure(text="Conectando...")

        try:

            self.ctx.executor.set_api_keys(api_key, api_secret)

            balance = self.ctx.executor.get_balance("USDC")

            self.status_label.configure(
                text=f"✓ Conectado | Saldo: {balance} USDC"
            )

        except Exception as e:

            self.status_label.configure(text=f"Erro: {e}")
