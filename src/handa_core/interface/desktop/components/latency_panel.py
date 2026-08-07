import customtkinter as ctk


COLOR_OK = "#00c853"
COLOR_WARNING = "#ffb300"
COLOR_ERROR = "#d50000"
COLOR_TEXT = "#e6e6e6"
COLOR_MUTED = "#9aa0a6"
BG_PANEL = "#1e2126"


class LatencyPanel(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color=BG_PANEL, corner_radius=18)

        self.grid_columnconfigure(0, weight=1)

        # Título
        self.title = ctk.CTkLabel(
            self,
            text="LATENCY",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_TEXT
        )
        self.title.grid(row=0, column=0, sticky="w", padx=20, pady=(15, 5))

        # Valor atual
        self.current_value = ctk.CTkLabel(
            self,
            text="0 ms",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=COLOR_OK
        )
        self.current_value.grid(row=1, column=0, sticky="w", padx=20)

        # Média
        self.avg_value = ctk.CTkLabel(
            self,
            text="avg 0 ms",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_MUTED
        )
        self.avg_value.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 15))

    # =====================================================
    # Atualizar valores
    # =====================================================

    def update_latency(self, current, avg):

        # Atualiza texto
        self.current_value.configure(text=f"{current} ms")
        self.avg_value.configure(text=f"avg {avg} ms")

        # Define cor
        if current < 50:
            color = COLOR_OK
        elif current < 120:
            color = COLOR_WARNING
        else:
            color = COLOR_ERROR

        self.current_value.configure(text_color=color)


# =========================================================
# TESTE ISOLADO
# =========================================================

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    app = ctk.CTk()
    app.geometry("300x200")

    panel = LatencyPanel(app)
    panel.pack(fill="both", expand=True, padx=20, pady=20)

    # Teste manual
    panel.update_latency(32, 41)

    app.mainloop()
