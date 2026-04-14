import customtkinter as ctk


# ==============================
# CORES PADRÃO HEALTH
# ==============================

COLOR_OK = "#00c853"
COLOR_WARNING = "#ffb300"
COLOR_ERROR = "#d50000"
COLOR_TEXT = "#e6e6e6"
COLOR_MUTED = "#9aa0a6"
BG_PANEL = "#1e2126"


class HealthPanel(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color=BG_PANEL, corner_radius=18)

        self.grid_columnconfigure(0, weight=1)

        # Título
        self.title_label = ctk.CTkLabel(
            self,
            text="SYSTEM HEALTH",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT
        )
        self.title_label.grid(row=0, column=0, sticky="w", padx=20, pady=(15, 10))

        # Componentes monitorados
        self.components = {
            "ENGINE": self._create_row(1, "ENGINE"),
            "BINANCE API": self._create_row(2, "BINANCE API"),
            "WEBSOCKET": self._create_row(3, "WEBSOCKET"),
            "EXECUTOR": self._create_row(4, "EXECUTOR"),
            "SLOTS": self._create_row(5, "SLOTS"),
        }

    # =====================================================
    # Criar linha de indicador
    # =====================================================

    def _create_row(self, row, name):

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=row, column=0, sticky="w", padx=20, pady=4)

        # Bolinha de status
        indicator = ctk.CTkLabel(
            container,
            text="●",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_MUTED
        )
        indicator.pack(side="left")

        # Texto do componente
        label = ctk.CTkLabel(
            container,
            text=f"  {name}: UNKNOWN",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_MUTED
        )
        label.pack(side="left")

        return {"indicator": indicator, "label": label}

    # =====================================================
    # Atualizar status
    # =====================================================

    def update_status(self, component, state):

        if component not in self.components:
            return

        colors = {
            "online": COLOR_OK,
            "warning": COLOR_WARNING,
            "error": COLOR_ERROR
        }

        color = colors.get(state, COLOR_MUTED)

        indicator = self.components[component]["indicator"]
        label = self.components[component]["label"]

        indicator.configure(text_color=color)
        label.configure(text=f"  {component}: {state.upper()}", text_color=color)


# =========================================================
# TESTE ISOLADO (ICFactory)
# =========================================================

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    app = ctk.CTk()
    app.geometry("400x350")

    panel = HealthPanel(app)
    panel.pack(fill="both", expand=True, padx=20, pady=20)

    # Teste manual
    panel.update_status("ENGINE", "online")
    panel.update_status("BINANCE API", "online")
    panel.update_status("WEBSOCKET", "warning")
    panel.update_status("EXECUTOR", "online")
    panel.update_status("SLOTS", "online")

    app.mainloop()
