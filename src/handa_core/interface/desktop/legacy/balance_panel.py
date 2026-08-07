import tkinter as tk


class BalancePanel(tk.Frame):
    """
    Painel Financeiro H&A
    SOMENTE LEITURA
    Saldo + Lucro + Performance
    """

    BG = "#151515"
    FG = "#dddddd"
    TITLE = "#00acc1"
    LINE = "#2a2a2a"
    GREEN = "#2ecc71"
    RED = "#e53935"
    YELLOW = "#f1c40f"

    def __init__(self, master, core=None, mode="MOCK"):
        super().__init__(master, bg=self.BG, width=280)
        self.pack_propagate(False)

        self.core = core
        self.mode = mode

        self.visible = False
        self.currency_var = tk.StringVar(value="USDC")

        self._build_ui()

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):

        # Título
        title = tk.Label(
            self, text="FINANCEIRO",
            bg=self.BG, fg=self.TITLE,
            font=("Segoe UI", 10, "bold")
        )
        title.pack(pady=(12, 6))

        # Subtítulo
        subtitle = tk.Label(
            self, text="Saldo & Performance",
            bg=self.BG, fg="#888888",
            font=("Segoe UI", 8)
        )
        subtitle.pack(pady=(0, 8))

        # Linha
        tk.Frame(self, bg=self.LINE, height=1).pack(fill="x", padx=12, pady=(0, 10))

        # Moeda
        tk.Label(self, text="MOEDA BASE", bg=self.BG, fg=self.FG,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12)

        self.currency_menu = tk.OptionMenu(
            self, self.currency_var,
            "USDC", "USDT", "BTC", "BNB"
        )
        self.currency_menu.config(width=10)
        self.currency_menu.pack(anchor="w", padx=12, pady=(4, 10))

        # =========================
        # SALDO
        # =========================
        tk.Label(self, text="SALDO", bg=self.BG, fg=self.TITLE,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(6, 4))

        self.total_lbl = self._make_row("Saldo Total:")
        self.available_lbl = self._make_row("Disponível:")
        self.allocated_lbl = self._make_row("Alocado:")
        self.free_lbl = self._make_row("Livre:")

        # Linha
        tk.Frame(self, bg=self.LINE, height=1).pack(fill="x", padx=12, pady=(10, 8))

        # =========================
        # LUCRO / PERFORMANCE
        # =========================
        tk.Label(self, text="PERFORMANCE", bg=self.BG, fg=self.TITLE,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(6, 4))

        self.profit_total_lbl = self._make_row("Lucro Total:", color=self.GREEN)
        self.profit_day_lbl = self._make_row("Lucro do Dia:", color=self.GREEN)
        self.profit_week_lbl = self._make_row("Lucro da Semana:", color=self.GREEN)
        self.roi_lbl = self._make_row("ROI (%):", color=self.YELLOW)

        # Linha
        tk.Frame(self, bg=self.LINE, height=1).pack(fill="x", padx=12, pady=(10, 8))

        # Status
        self.status_lbl = tk.Label(
            self,
            text=f"Status: {self.mode} | Fonte: Binance Spot",
            bg=self.BG, fg="#aaaaaa",
            font=("Segoe UI", 8, "bold")
        )
        self.status_lbl.pack(anchor="w", padx=12, pady=(4, 8))

    def _make_row(self, label, color=None):
        frame = tk.Frame(self, bg=self.BG)
        frame.pack(fill="x", padx=12, pady=2)

        tk.Label(frame, text=label, bg=self.BG, fg=self.FG,
                 font=("Segoe UI", 8)).pack(side="left")

        value = tk.Label(
            frame,
            text="--",
            bg=self.BG,
            fg=color if color else self.FG,
            font=("Consolas", 8, "bold")
        )
        value.pack(side="right")

        return value

    # =====================================================
    # VISIBILITY
    # =====================================================

    def show(self):
        if not self.visible:
            self.pack(side="right", fill="y")
            self.visible = True

    def hide(self):
        if self.visible:
            self.pack_forget()
            self.visible = False

    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    # =====================================================
    # UPDATE
    # =====================================================

    def update_data(self):
        """
        Atualiza dados financeiros
        SOMENTE LEITURA
        """
        currency = self.currency_var.get()

        if self.core:
            data = self.core.get_financial_snapshot(currency)
        else:
            # MOCK
            data = {
                "balance": {
                    "total": 10000,
                    "available": 7200,
                    "allocated": 2800,
                    "free": 7200
                },
                "profit": {
                    "total": 1350,
                    "day": 120,
                    "week": 410,
                    "roi": 13.5
                }
            }

        bal = data["balance"]
        prof = data["profit"]

        # Saldo
        self.total_lbl.config(text=str(bal["total"]))
        self.available_lbl.config(text=str(bal["available"]))
        self.allocated_lbl.config(text=str(bal["allocated"]))
        self.free_lbl.config(text=str(bal["free"]))

        # Lucro
        self.profit_total_lbl.config(text=str(prof["total"]))
        self.profit_day_lbl.config(text=str(prof["day"]))
        self.profit_week_lbl.config(text=str(prof["week"]))
        self.roi_lbl.config(text=str(prof["roi"]))
