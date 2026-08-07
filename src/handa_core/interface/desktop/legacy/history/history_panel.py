import tkinter as tk
from tkinter import ttk


class HistoryPanel(tk.Frame):
    """
    Histórico de Trades — H&A
    UI PURA (layout congelável)
    """

    def __init__(self, master):
        super().__init__(master, bg="#ECECEC")
        self._build_ui()

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):
        container = tk.Frame(self, bg="#ECECEC")
        container.pack(fill="x", padx=10, pady=(6, 4))


        # -------------------------
        # Título
        # -------------------------
        tk.Label(
            container,
            text="Histórico de Trades",
            font=("Segoe UI", 9, "bold"),
            bg="#ECECEC",
            fg="#333333"
        ).pack(anchor="w", pady=(0, 6))

        # -------------------------
        # Tabela
        # -------------------------
        columns = (
            "hora",
            "slot",
            "par",
            "acao",
            "preco",
            "resultado",
            "variacao",
        )

        self.tree = ttk.Treeview(
            container,
            columns=columns,
            show="headings",
            height=5
        )

        # Cabeçalhos
        self.tree.heading("hora", text="Hora")
        self.tree.heading("slot", text="Slot")
        self.tree.heading("par", text="Par")
        self.tree.heading("acao", text="Ação")
        self.tree.heading("preco", text="Preço")
        self.tree.heading("resultado", text="Resultado")
        self.tree.heading("variacao", text="Var%")

        # Larguras (ajuste fino depois)
        self.tree.column("hora", width=80, anchor="center")
        self.tree.column("slot", width=50, anchor="center")
        self.tree.column("par", width=90, anchor="center")
        self.tree.column("acao", width=120, anchor="center")
        self.tree.column("preco", width=90, anchor="e")
        self.tree.column("resultado", width=90, anchor="e")
        self.tree.column("variacao", width=70, anchor="e")

        self.tree.pack(side="left", fill="both", expand=True)

        # Scroll vertical
        scrollbar = ttk.Scrollbar(
            container,
            orient="vertical",
            command=self.tree.yview
        )
        scrollbar.pack(side="right", fill="y")

        self.tree.configure(yscrollcommand=scrollbar.set)

        # -------------------------
        # MOCK (visual apenas)
        # -------------------------
        for i in range(5):
            self.tree.insert(
                "",
                "end",
                values=(
                    "21:15:3{}".format(i),
                    i + 1,
                    "BTC/USDC",
                    "TRADE_START",
                    "—",
                    "—",
                    "—"
                )
            )
