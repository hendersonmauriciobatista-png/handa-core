import customtkinter as ctk


BG_PANEL = "#1e2126"
COLOR_TEXT = "#e6e6e6"
COLOR_MUTED = "#9aa0a6"


class ConfigModal(ctk.CTkToplevel):

    def __init__(self, master):
        super().__init__(master)

        self.title("Configuration")
        self.geometry("500x420")
        self.resizable(False, False)

        self.configure(fg_color=BG_PANEL)

        self.grab_set()  # modal real
        self.focus()

        self.grid_columnconfigure(0, weight=1)

        self._build_layout()

    # =====================================================
    # LAYOUT
    # =====================================================

    def _build_layout(self):

        # Título
        title = ctk.CTkLabel(
            self,
            text="SYSTEM CONFIGURATION",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXT
        )
        title.grid(row=0, column=0, pady=(20, 15))

        # Exchange (fixo por enquanto)
        exchange_label = ctk.CTkLabel(
            self,
            text="Exchange",
            text_color=COLOR_MUTED
        )
        exchange_label.grid(row=1, column=0, sticky="w", padx=40)

        self.exchange_value = ctk.CTkLabel(
            self,
            text="Binance",
            font=ctk.CTkFont(weight="bold"),
            text_color=COLOR_TEXT
        )
        self.exchange_value.grid(row=2, column=0, sticky="w", padx=40, pady=(0, 15))

        # API KEY
        api_label = ctk.CTkLabel(self, text="API Key", text_color=COLOR_MUTED)
        api_label.grid(row=3, column=0, sticky="w", padx=40)

        self.api_entry = ctk.CTkEntry(self, width=400)
        self.api_entry.grid(row=4, column=0, padx=40, pady=(0, 15))

        # SECRET KEY
        secret_label = ctk.CTkLabel(self, text="Secret Key", text_color=COLOR_MUTED)
        secret_label.grid(row=5, column=0, sticky="w", padx=40)

        self.secret_entry = ctk.CTkEntry(self, width=400, show="*")
        self.secret_entry.grid(row=6, column=0, padx=40, pady=(0, 15))

        # MODO MOCK / LIVE
        mode_label = ctk.CTkLabel(self, text="Mode", text_color=COLOR_MUTED)
        mode_label.grid(row=7, column=0, sticky="w", padx=40)

        self.mode_toggle = ctk.CTkSegmentedButton(
            self,
            values=["MOCK", "LIVE"]
        )
        self.mode_toggle.set("MOCK")
        self.mode_toggle.grid(row=8, column=0, padx=40, pady=(0, 20))

        # Indicador de conexão
        self.connection_status = ctk.CTkLabel(
            self,
            text="Not Connected",
            text_color="#ffb300"
        )
        self.connection_status.grid(row=9, column=0, pady=(0, 15))

        # Botões
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=10, column=0, pady=(0, 20))

        save_btn = ctk.CTkButton(
            button_frame,
            text="Save",
            command=self._save_config
        )
        save_btn.pack(side="left", padx=10)

        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            fg_color="#2f343c",
            command=self.destroy
        )
        cancel_btn.pack(side="left", padx=10)

        # Enter confirma
        self.bind("<Return>", lambda e: self._save_config())

    # =====================================================
    # SAVE
    # =====================================================

    def _save_config(self):

        api = self.api_entry.get()
        secret = self.secret_entry.get()
        mode = self.mode_toggle.get()

        print("CONFIG SAVED:")
        print("API:", api)
        print("SECRET:", "*" * len(secret))
        print("MODE:", mode)

        self.connection_status.configure(
            text="Configuration Saved",
            text_color="#00c853"
        )


# =========================================================
# TESTE ISOLADO
# =========================================================

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    app = ctk.CTk()
    app.geometry("300x200")

    def open_modal():
        ConfigModal(app)

    btn = ctk.CTkButton(app, text="Open Config", command=open_modal)
    btn.pack(expand=True)

    app.mainloop()
