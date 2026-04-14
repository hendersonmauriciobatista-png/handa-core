import tkinter as tk


class MetricsPanel(tk.Frame):
    """
    Caixa de métrica visual (layout fixo).
    Usada no BodyArea.
    """

    def __init__(self, master, title: str, value: int):
        super().__init__(master, bg="white", bd=1, relief="solid")
        self.title = title
        self.value = max(0, min(100, value))  # clamp 0–100

        self.configure(width=260, height=68)
        self.pack_propagate(False)

        self._build_ui()

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):
        # -------------------------
        # TÍTULO
        # -------------------------
        tk.Label(
            self,
            text=self.title,
            font=("Segoe UI", 9, "bold"),
            bg="white",
            anchor="w"
        ).pack(fill="x", padx=8, pady=(6, 2))

        # -------------------------
        # BARRA
        # -------------------------
        bar_bg = tk.Frame(self, bg="#E0E0E0", height=10)
        bar_bg.pack(fill="x", padx=8)

        bar_fg = tk.Frame(
            bar_bg,
            bg="#4CAF50",
            width=int(2.4 * self.value),
            height=10
        )
        bar_fg.pack(side="left")

        # -------------------------
        # ESCALA + VALOR
        # -------------------------
        bottom = tk.Frame(self, bg="white")
        bottom.pack(fill="x", padx=8, pady=(4, 6))

        tk.Label(
            bottom,
            text="0",
            font=("Segoe UI", 8),
            fg="#777777",
            bg="white"
        ).pack(side="left")

        tk.Label(
            bottom,
            text=f"{self.value}%",
            font=("Segoe UI", 9, "bold"),
            bg="white"
        ).pack(side="left", expand=True)

        tk.Label(
            bottom,
            text="100",
            font=("Segoe UI", 8),
            fg="#777777",
            bg="white"
        ).pack(side="right")
