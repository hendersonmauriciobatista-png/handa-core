import tkinter as tk
from tkinter import ttk
from collections import deque


class BodyArea:
    """
    BodyArea – versão funcional com ANÁLISE + TRADE.
    Visual neutro, foco em fluxo e estabilidade.
    """

    BG_MAIN = "#1e1e1e"
    BG_CARD = "#262626"

    FG_TEXT = "#bdbdbd"
    FG_MUTED = "#8a8a8a"

    COLOR_ANALYZING = "#6f6a1f"
    COLOR_OK = "#1e7f4b"

    COLOR_TRADE_PLAN = "#e0c97f"
    COLOR_TRADING = "#4a90e2"
    COLOR_DONE = "#6aa84f"

    def __init__(self, root, slot_controller):
        self.root = root
        self.slot_controller = slot_controller

        self.frame = tk.Frame(root, bg=self.BG_MAIN)
        self.slot_cards = {}

        self.activity_buf = deque(maxlen=60)
        self.latency_buf = deque(maxlen=60)

        self._setup_styles()
        self._build_ui()

        self.refresh()

    def pack(self, *args, **kwargs):
        self.frame.pack(fill="both", expand=True)

    # =========================
    # STYLES
    # =========================
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("default")

        style.configure(
            "Treeview",
            background=self.BG_MAIN,
            foreground=self.FG_TEXT,
            fieldbackground=self.BG_MAIN,
            rowheight=22,
            borderwidth=0,
            font=("Segoe UI", 9),
        )

    # =========================
    # BUILD UI
    # =========================
    def _build_ui(self):
        container = tk.Frame(self.frame, bg=self.BG_MAIN)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        left = tk.Frame(container, bg=self.BG_MAIN)
        left.grid(row=0, column=0, sticky="n")

        for sid in (1, 2, 3):
            self._create_slot_card(left, sid).pack(pady=10)

        right = tk.Frame(container, bg=self.BG_MAIN)
        right.grid(row=0, column=2, sticky="n")

        for sid in (4, 5, 6):
            self._create_slot_card(right, sid).pack(pady=10)

    # =========================
    # SLOT CARD
    # =========================
    def _create_slot_card(self, parent, slot_id):
        frame = tk.Frame(parent, bg=self.BG_CARD, width=260, height=140)
        frame.pack_propagate(False)

        tk.Label(
            frame,
            text=f"SLOT {slot_id}",
            bg=self.BG_CARD,
            fg=self.FG_MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=12, pady=(8, 4))

        analysis_lbl = tk.Label(
            frame,
            text="ANÁLISE · AGUARDANDO",
            bg=self.BG_CARD,
            fg=self.FG_TEXT,
            font=("Segoe UI", 10),
        )
        analysis_lbl.pack(anchor="w", padx=12)

        trade_lbl = tk.Label(
            frame,
            text="TRADE · —",
            bg=self.BG_CARD,
            fg=self.FG_MUTED,
            font=("Segoe UI", 9),
        )
        trade_lbl.pack(anchor="w", padx=12, pady=(2, 0))

        self.slot_cards[slot_id] = {
            "frame": frame,
            "analysis": analysis_lbl,
            "trade": trade_lbl,
        }

        return frame

    # =========================
    # REFRESH
    # =========================
    def refresh(self):
        snapshots = self.slot_controller.snapshot_all()

        for slot_id, data in snapshots.items():
            card = self.slot_cards.get(slot_id)
            if not card:
                continue

            state = data.get("analysis_state")
            strength = data.get("analysis_strength")
            trade_state = data.get("trade_state")

            # -------------------------
            # ANALYSIS LINE
            # -------------------------
            if state == "IDLE":
                analysis_txt = "ANÁLISE · AGUARDANDO"
                analysis_fg = self.FG_MUTED

            elif state == "ANALYZING":
                analysis_txt = "ANÁLISE · ANALISANDO"
                analysis_fg = self.COLOR_ANALYZING

            elif state == "ANALYZED":
                pct = f"{strength}%" if strength is not None else "--"
                analysis_txt = f"ANÁLISE · OK · {pct}"
                analysis_fg = self.COLOR_OK

            else:
                analysis_txt = "ANÁLISE · —"
                analysis_fg = self.FG_MUTED

            card["analysis"].configure(text=analysis_txt, fg=analysis_fg)

            # -------------------------
            # TRADE LINE
            # -------------------------
            if trade_state == "TRADE_PLANNED":
                trade_txt = "TRADE · PLANEJADO"
                trade_fg = self.COLOR_TRADE_PLAN

            elif trade_state == "TRADING":
                trade_txt = "TRADE · EXECUTANDO (MOCK)"
                trade_fg = self.COLOR_TRADING

            elif trade_state == "DONE":
                trade_txt = "TRADE · FINALIZADO"
                trade_fg = self.COLOR_DONE

            else:
                trade_txt = "TRADE · —"
                trade_fg = self.FG_MUTED

            card["trade"].configure(text=trade_txt, fg=trade_fg)

        self.root.after(500, self.refresh)
