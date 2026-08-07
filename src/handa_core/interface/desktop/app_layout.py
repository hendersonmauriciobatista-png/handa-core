"""
H&A Control Panel — CustomTkinter Premium Redesign
Instalar dependências: pip install customtkinter
"""

import os
import ctypes
import customtkinter as ctk
import threading
import time

from binance.client import Client


from core.slot_controller import SlotController
from interface.components.api_settings import APISettings

# ── TEMA GLOBAL ────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ── PALETA ─────────────────────────────────────────────────────
BG_BASE = "#080C14"
BG_PANEL = "#0D1420"
BG_CARD = "#111827"
BG_CARD2 = "#0F1923"
BORDER = "#1E2D45"
ACCENT = "#00D4FF"
ACCENT_DIM = "#0099BB"
GREEN = "#00FF88"
GREEN_DIM = "#00CC6A"
YELLOW = "#FFD700"
RED = "#FF4060"
TEXT_PRI = "#E8F0FE"
TEXT_SEC = "#9FB3D1"
TEXT_MUT = "#6E86A8"

FONT_TITLE = ("Courier New", 11, "bold")
FONT_LABEL = ("Courier New", 10)
FONT_VALUE = ("Courier New", 22, "bold")
FONT_VALUE_SM = ("Courier New", 14, "bold")
FONT_BTN = ("Courier New", 9, "bold")
FONT_SMALL = ("Courier New", 10)
FONT_MONO = ("Courier New", 10)


# ── COMPONENTES CUSTOMIZADOS ────────────────────────────────────


class SectionCard(ctk.CTkFrame):
    """Card com borda sutil e label de cabeçalho."""

    def __init__(self, parent, label="", **kwargs):
        kwargs.setdefault("fg_color", BG_CARD)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", BORDER)
        kwargs.setdefault("corner_radius", 6)
        super().__init__(parent, **kwargs)

        if label:
            ctk.CTkLabel(
                self,
                text=f"◆  {label.upper()}",
                font=FONT_LABEL,
                text_color=TEXT_MUT,
                anchor="w",
            ).pack(anchor="w", padx=14, pady=(10, 4))


class ValueLabel(ctk.CTkLabel):
    """Label de valor grande com cor destaque."""

    def __init__(self, parent, text="0.00", color=TEXT_PRI, size=22, **kwargs):
        super().__init__(
            parent,
            text=text,
            font=("Courier New", size, "bold"),
            text_color=color,
            **kwargs,
        )


class StatusBadge(ctk.CTkLabel):
    """Badge de status pill."""

    def __init__(self, parent, text="IDLE", color=TEXT_MUT, bg=BG_CARD2, **kwargs):
        super().__init__(
            parent,
            text=text,
            font=FONT_SMALL,
            text_color=color,
            fg_color=bg,
            corner_radius=3,
            padx=8,
            pady=3,
            **kwargs,
        )


class GlowButton(ctk.CTkButton):
    """Botão com estilo premium."""

    def __init__(
        self, parent, text, fg, hover, text_color="#000000", width=90, **kwargs
    ):
        super().__init__(
            parent,
            text=text,
            fg_color=fg,
            hover_color=hover,
            text_color=text_color,
            font=FONT_BTN,
            corner_radius=3,
            width=width,
            height=30,
            border_width=0,
            **kwargs,
        )


# ── JANELA PRINCIPAL ────────────────────────────────────────────


class HAControlPanel(ctk.CTk):

    def __init__(self, controller=None, auto_loop=None):

        super().__init__()

        self.controller = controller
        self.auto_loop = auto_loop
        self.ui_running = True

        self.balance_var = ctk.StringVar(value="0.00")
        self.profit_day = ctk.StringVar(value="0.00")
        self.profit_total = ctk.StringVar(value="0.00")
        self.live_var = ctk.BooleanVar(value=False)

        self.slot_vars = []
        for _ in range(4):
            self.slot_vars.append(
                {
                    "ticker": ctk.StringVar(value="--"),
                    "status": ctk.StringVar(value="IDLE"),
                    "price": ctk.StringVar(value="0.0000"),
                    "pnl": ctk.StringVar(value="0.00%"),
                }
            )

        self.state_var = ctk.StringVar(value="STOPPED")
        self.cycle_var = ctk.StringVar(value="0")
        self.last_iter_var = ctk.StringVar(value="--")
        self.mode_var = ctk.StringVar(value="MOCK")

        # ✅ LATÊNCIA
        self.api_lat_var = ctk.StringVar(value="--")
        self.mkt_lat_var = ctk.StringVar(value="--")
        self.exec_lat_var = ctk.StringVar(value="--")

        # MARKET INFO
        self.mkt_pair_var = ctk.StringVar(value="--")
        self.mkt_score_var = ctk.StringVar(value="0.00")

        self._build_ui()
        self.after(300, self._ui_loop)
        self.after(500, self._update_balance)

        # 🔒 FORÇA MOCK
        if self.controller and hasattr(self.controller, "executor_router"):
            self.controller.executor_router.set_mode("MOCK")

        # controle de lock do sistema
        self.locked = False
        self.title("H&A Control Panel")

        # === H&A APP ID (ícone na barra do Windows) ===
        app_id = "handa.core.controlpanel"

        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception as e:
            print(f"[UI] Erro ao definir AppUserModelID: {e}")

        # === H&A ICON ===
        icon_path = os.path.join("assets", "icons", "ha_icon.ico")

        try:
            self.iconbitmap(icon_path)
        except Exception as e:
            print(f"[UI] Erro ao carregar ícone: {e}")

        icon_path = os.path.join("assets", "icons", "ha_icon.ico")

        try:
            self.iconbitmap(icon_path)
        except Exception as e:
            print(f"[UI] Erro ao carregar ícone: {e}")

        self.geometry("900x660")
        self.minsize(860, 620)
        self.configure(fg_color=BG_BASE)
        self.resizable(True, True)

    # ── BUILD ──────────────────────────────────────────────────

    def _build_ui(self):
        # ── TOOLBAR ──────────────────────────────────────────
        tb = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=52)
        tb.pack(fill="x", padx=0, pady=0)
        tb.pack_propagate(False)

        # Logo
        ctk.CTkLabel(
            tb,
            text="H&A",
            font=("Courier New", 13, "bold"),
            text_color=ACCENT,
            fg_color="#0A1628",
            corner_radius=3,
            padx=10,
            pady=4,
        ).pack(side="left", padx=(16, 6), pady=10)

        ctk.CTkLabel(
            tb, text="CONTROL PANEL", font=("Courier New", 8), text_color=TEXT_MUT
        ).pack(side="left", padx=(0, 16), pady=10)

        # Exchange
        ctk.CTkLabel(
            tb,
            text="BINANCE",
            font=("Courier New", 9, "bold"),
            text_color=ACCENT_DIM,
            fg_color=BG_CARD,
            corner_radius=3,
            padx=10,
            pady=4,
        ).pack(side="left", padx=4, pady=10)

        # Live Toggle
        toggle_frame = ctk.CTkFrame(tb, fg_color=BG_CARD, corner_radius=3)
        toggle_frame.pack(side="left", padx=4, pady=10)
        ctk.CTkLabel(
            toggle_frame, text="LIVE", font=FONT_SMALL, text_color=TEXT_SEC
        ).pack(side="left", padx=(8, 4), pady=4)
        ctk.CTkSwitch(
            toggle_frame,
            text="",
            variable=self.live_var,
            onvalue=True,
            offvalue=False,
            progress_color=GREEN,
            button_color=GREEN_DIM,
            fg_color=BORDER,
            width=36,
            height=18,
            command=self._toggle_live,
        ).pack(side="left", padx=(0, 8), pady=4)

        # Buttons
        GlowButton(
            tb, "▶  START", GREEN_DIM, GREEN, "#001a0d", command=self._start
        ).pack(side="left", padx=4, pady=10)
        GlowButton(
            tb, "⇣  DRAIN", "#CC8800", YELLOW, "#1a0e00", command=self._drain
        ).pack(side="left", padx=4, pady=10)
        GlowButton(
            tb, "↺  RESET", BG_CARD, "#1E2D45", TEXT_SEC, command=self._reset
        ).pack(side="left", padx=4, pady=10)
        GlowButton(tb, "⊘  LOCK", "#8B0020", RED, "#ffffff", command=self._lock).pack(
            side="left", padx=4, pady=10
        )

        # API button (right)
        GlowButton(
            tb,
            "API",
            BG_CARD,
            "#1E4080",
            ACCENT,
            width=60,
            command=self._open_api_dialog,
        ).pack(side="right", padx=16, pady=10)
        # ── CONTENT AREA ──────────────────────────────────────
        content = ctk.CTkScrollableFrame(self, fg_color=BG_BASE, corner_radius=0)
        content.pack(fill="both", expand=True, padx=16, pady=12)
        content.columnconfigure(0, weight=1)

        # ── ROW 1: Balance + Profit ───────────────────────────
        r1 = ctk.CTkFrame(content, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 10))
        r1.columnconfigure((0, 1), weight=1)

        self._build_balance_card(r1)
        self._build_profit_card(r1)

        # ── ROW 2: Slots ──────────────────────────────────────
        r2 = ctk.CTkFrame(content, fg_color="transparent")
        r2.pack(fill="x", pady=(0, 10))
        for i in range(4):
            r2.columnconfigure(i, weight=1)
        self._build_slots(r2)

        # ── ROW 3: Status + Latency + Market + History ────────
        r3 = ctk.CTkFrame(content, fg_color="transparent")
        r3.pack(fill="x", pady=(0, 10))
        r3.columnconfigure(0, weight=3)
        r3.columnconfigure(1, weight=2)
        r3.columnconfigure(2, weight=3)

        self._build_status_card(r3)
        self._build_latency_market(r3)
        self._build_history_card(r3)

    # ── CARDS ──────────────────────────────────────────────────

    def _build_balance_card(self, parent):
        card = SectionCard(parent, label="Balance")
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        # Main value
        val_row = ctk.CTkFrame(card, fg_color="transparent")
        val_row.pack(anchor="w", padx=14, pady=(0, 6))

        ctk.CTkLabel(
            val_row, text="USDC ", font=("Courier New", 13, "bold"), text_color=ACCENT
        ).pack(side="left")
        ctk.CTkLabel(
            val_row,
            textvariable=self.balance_var,
            font=("Courier New", 26, "bold"),
            text_color=TEXT_PRI,
        ).pack(side="left")

        # Conversions
        conv = ctk.CTkFrame(card, fg_color=BG_CARD2, corner_radius=4)
        conv.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkLabel(
            conv, text="≈ BRL   0.00", font=FONT_SMALL, text_color=TEXT_SEC, anchor="w"
        ).pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkLabel(
            conv, text="≈ EUR   0.00", font=FONT_SMALL, text_color=TEXT_SEC, anchor="w"
        ).pack(fill="x", padx=10, pady=(0, 6))

    def _build_profit_card(self, parent):
        card = SectionCard(parent, label="Profit")
        card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        for period, var in [("TODAY", self.profit_day), ("TOTAL", self.profit_total)]:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=4)

            ctk.CTkLabel(
                row,
                text=period,
                font=FONT_SMALL,
                text_color=TEXT_MUT,
                width=50,
                anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                row,
                textvariable=var,
                font=("Courier New", 20, "bold"),
                text_color=TEXT_SEC,
            ).pack(side="right")

        # Divider
        ctk.CTkFrame(card, height=1, fg_color=BORDER).pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(
            card, text="No P&L data", font=FONT_SMALL, text_color=TEXT_MUT
        ).pack(pady=(0, 14))

    def _build_slots(self, parent):
        for i in range(4):
            card = ctk.CTkFrame(
                parent,
                fg_color=BG_CARD,
                border_width=1,
                border_color=BORDER,
                corner_radius=6,
            )
            card.grid(row=0, column=i, sticky="nsew", padx=(0, 6) if i < 3 else 0)

            ctk.CTkLabel(
                card, text=f"SLOT 0{i+1}", font=("Courier New", 8), text_color=TEXT_MUT
            ).pack(pady=(12, 6))

            ctk.CTkLabel(
                card,
                textvariable=self.slot_vars[i]["ticker"],
                font=("Courier New", 14, "bold"),
                text_color=TEXT_SEC,
            ).pack(pady=2)

            StatusBadge(card, textvariable=self.slot_vars[i]["status"]).pack(
                pady=(4, 14)
            )

    def _build_status_card(self, parent):
        card = SectionCard(parent, label="System Status")
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        ctk.CTkLabel(
            card,
            textvariable=self.state_var,
            font=("Courier New", 18, "bold"),
            text_color=ACCENT,
        ).pack(anchor="w", padx=14, pady=(0, 2))

        ctk.CTkLabel(
            card,
            textvariable=self.mode_var,
            font=FONT_SMALL,
            text_color=YELLOW,
            fg_color="#1A1200",
            corner_radius=3,
            padx=8,
            pady=3,
        ).pack(anchor="w", padx=14, pady=(0, 12))

        # Divider
        ctk.CTkFrame(card, height=1, fg_color=BORDER).pack(
            fill="x", padx=14, pady=(0, 10)
        )

        # Activity
        ctk.CTkLabel(
            card,
            text="◆  H&A ACTIVITY",
            font=FONT_LABEL,
            text_color=TEXT_MUT,
            anchor="w",
        ).pack(anchor="w", padx=14)

        act = ctk.CTkFrame(card, fg_color="transparent")
        act.pack(fill="x", padx=14, pady=(6, 14))
        act.columnconfigure((0, 1), weight=1)

        for col, (key, var) in enumerate(
            [("CYCLE", self.cycle_var), ("LAST ITER", self.last_iter_var)]
        ):
            f = ctk.CTkFrame(act, fg_color="transparent")
            f.grid(row=0, column=col, sticky="w")
            ctk.CTkLabel(f, text=key, font=FONT_SMALL, text_color=TEXT_MUT).pack(
                anchor="w"
            )
            ctk.CTkLabel(
                f,
                textvariable=var,
                font=("Courier New", 16, "bold"),
                text_color=TEXT_PRI,
            ).pack(anchor="w")

    def _build_latency_market(self, parent):
        col = ctk.CTkFrame(parent, fg_color="transparent")
        col.grid(row=0, column=1, sticky="nsew", padx=6)

        # Latency
        lat_card = SectionCard(col, label="Latency")
        lat_card.pack(fill="both", expand=True, pady=(0, 8))

        for key, var in [
            ("API", self.api_lat_var),
            ("MARKET", self.mkt_lat_var),
            ("EXECUTION", self.exec_lat_var),
        ]:
            row = ctk.CTkFrame(lat_card, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=3)
            ctk.CTkLabel(
                row,
                text=key,
                font=FONT_SMALL,
                text_color=TEXT_MUT,
                anchor="w",
                width=80,
            ).pack(side="left")
            ctk.CTkLabel(
                row, textvariable=var, font=FONT_MONO, text_color=TEXT_SEC
            ).pack(side="right")

        ctk.CTkFrame(lat_card, height=1, fg_color=BORDER).pack(
            fill="x", padx=14, pady=4
        )

        # Liquidez do Mercado
        mkt_card = SectionCard(col, label="Liquidez do Mercado")
        mkt_card.pack(fill="x")
        ctk.CTkLabel(
            mkt_card,
            textvariable=self.mkt_pair_var,
            font=("Courier New", 14, "bold"),
            text_color=ACCENT,
        ).pack(anchor="w", padx=14, pady=(0, 8))

        self.strength_bar = ctk.CTkProgressBar(
            mkt_card, fg_color=BORDER, progress_color=ACCENT, height=4, corner_radius=2
        )
        self.strength_bar.set(0.0)
        self.strength_bar.pack(fill="x", padx=14, pady=(0, 14))

    def _build_history_card(self, parent):
        card = SectionCard(parent, label="Trade History")
        card.grid(row=0, column=2, sticky="nsew", padx=(6, 0))

        self.history_frame = ctk.CTkScrollableFrame(
            card, fg_color="transparent", height=180
        )
        self.history_frame.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        ctk.CTkLabel(
            self.history_frame,
            text="No trades recorded",
            font=FONT_SMALL,
            text_color=TEXT_MUT,
        ).pack(pady=20)

    # ── LOGIC / EVENTS ─────────────────────────────────────────

    def _toggle_live(self):

        if self.live_var.get():

            self.mode_var.set("MODE LIVE")

            if self.controller and hasattr(self.controller, "executor_router"):
                self.controller.executor_router.set_mode("MOCK")

        else:

            self.mode_var.set("MODE MOCK")

            if self.controller and hasattr(self.controller, "executor_router"):
                self.controller.executor_router.set_mode("MOCK")

    def _start(self):

        if self.locked:
            return

        if self.controller and hasattr(self.controller, "start"):
            self.controller.start()
            self.state_var.set("STATE RUNNING")
            return

        if self.auto_loop and not self.auto_loop.running:

            thread = threading.Thread(target=self.auto_loop.start, daemon=True)

            thread.start()

        self.state_var.set("STATE RUNNING")

    def _drain(self):

        if self.controller and hasattr(self.controller, "drain"):
            self.controller.drain()
            self.state_var.set("STATE DRAINING")
            return

        if self.auto_loop:
            self.auto_loop.stop()

        self.state_var.set("STATE DRAINING")

    def _reset(self):

        if self.controller and hasattr(self.controller, "reset"):
            self.controller.reset()

        # para o loop
        if self.auto_loop:
            self.auto_loop.stop()

        # limpa slots
        if self.controller:
            try:
                for slot in self.controller.get_slots().values():
                    slot.reset()

            except Exception as e:
                print("RESET ERROR:", e)

        # reseta UI
        self.state_var.set("STATE IDLE")
        self.cycle_var.set("0")
        self.balance_var.set("0.00")
        self.profit_day.set("0.00")
        self.profit_total.set("0.00")

        for sv in self.slot_vars:
            sv["ticker"].set("—")
            sv["status"].set("IDLE")

    def _lock(self):

        if self.locked:
            self.locked = False

            if self.controller and hasattr(self.controller, "unlock"):
                self.controller.unlock()

            self.state_var.set("STATE IDLE")

        else:
            self.locked = True
            self.state_var.set("⊘ LOCKED")

    def _update_balance(self):

        if self.controller and hasattr(self.controller, "get_balance"):
            try:
                balance = self.controller.get_balance("USDC")

                new_balance = f"{balance:.2f}"
                if self.balance_var.get() != new_balance:
                    self.balance_var.set(new_balance)

                self._update_profit()
            except Exception as e:
                print("[UI] BALANCE UPDATE ERROR:", e)
        else:
            print("[UI] controller sem get_balance")

        self.after(2000, self._update_balance)

    def _update_profit(self):

        if self.controller and hasattr(self.controller, "get_trade_history"):
            history = self.controller.get_trade_history()

            total_profit = sum(pos.net_pnl_usdc for pos in history)

            new_profit = f"{total_profit:.2f}"

            if self.profit_total.get() != new_profit:
                self.profit_total.set(new_profit)

            if self.profit_day.get() != new_profit:
                self.profit_day.set(new_profit)

    def _open_api_dialog(self):

        dialog = ctk.CTkToplevel(self)
        dialog.title("Binance API")
        dialog.geometry("420x260")
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="BINANCE API CONFIG", font=("Courier New", 12, "bold")
        ).pack(pady=(20, 10))

        api_key_var = ctk.StringVar()
        secret_key_var = ctk.StringVar()
        status_var = ctk.StringVar(value="Not connected")
        # -----------------------
        # API KEY
        # -----------------------

        ctk.CTkLabel(dialog, text="API KEY").pack()

        api_entry = ctk.CTkEntry(dialog, textvariable=api_key_var, width=340)

        api_entry.pack(pady=5)
        api_entry.focus()

        # -----------------------
        # SECRET
        # -----------------------

        ctk.CTkLabel(dialog, text="SECRET KEY").pack()

        secret_entry = ctk.CTkEntry(
            dialog, textvariable=secret_key_var, width=340, show="*"
        )

        secret_entry.pack(pady=5)

        # -----------------------
        # STATUS
        # -----------------------

        status_label = ctk.CTkLabel(
            dialog, textvariable=status_var, text_color="yellow"
        )

        status_label.pack(pady=10)

        # -----------------------
        # CONNECT FUNCTION
        # -----------------------

        def connect_api(event=None):

            status_var.set("Connecting...")
            dialog.update()

            try:

                api_key = api_key_var.get().strip()
                secret_key = secret_key_var.get().strip()

                if not api_key or not secret_key:
                    status_var.set("Missing API keys")
                    return

                client = Client(api_key, secret_key)

                account = client.get_account()

                self.client = client

                status_var.set("✓ Connected to Binance")

            except Exception as e:

                status_var.set(f"Error: {str(e)[:60]}")

        # -----------------------
        # PASTE SUPPORT
        # -----------------------

        # -----------------------
        # VALIDAR API
        # -----------------------

        def save():

            api = api_key_var.get().strip()
            secret = secret_key_var.get().strip()

            if not api or not secret:

                status_var.set("Missing API or SECRET")
                status_label.configure(text_color="orange")
                return

            try:

                client = Client(api, secret)

                # chamada real na Binance
                account = client.get_account()

                self.binance_client = client

                status_var.set("API CONNECTED ✓")
                status_label.configure(text_color="green")

                print("BINANCE API VALIDATED")

            except Exception as e:

                status_var.set("API INVALID ✗")
                status_label.configure(text_color="red")

                print("API ERROR:", e)

        # -----------------------
        # SAVE BUTTON
        # -----------------------

        ctk.CTkButton(dialog, text="VALIDATE & CONNECT", command=save).pack(pady=10)

        # ENTER support
        api_entry.bind("<Return>", lambda e: save())
        secret_entry.bind("<Return>", lambda e: save())

        def paste_api(event):
            try:
                api_entry.insert("end", dialog.clipboard_get())
            except:
                pass

        def paste_secret(event):
            try:
                secret_entry.insert("end", dialog.clipboard_get())
            except:
                pass

        api_entry.bind("<Button-3>", paste_api)
        secret_entry.bind("<Button-3>", paste_secret)

    def _sync_from_controller(self):

        if self.controller is None:
            return

        try:
            slots = list(self.controller.get_slots().values())[:4]

            for i, slot in enumerate(slots):

                if i >= 4:
                    break

                symbol = getattr(slot, "pair", getattr(slot, "symbol", "—"))
                state = getattr(slot, "state", "IDLE")

                self.slot_vars[i]["ticker"].set(symbol)
                self.slot_vars[i]["status"].set(state)

            # TRADE HISTORY
            history = []

            if self.controller and hasattr(self.controller, "get_trade_history"):
                history = self.controller.get_trade_history()

            for widget in self.history_frame.winfo_children():
                widget.destroy()

            if history:

                for trade in reversed(history[-10:]):

                    text = f"{trade.symbol}   {trade.net_pnl_usdc:+.2f}"

                    ctk.CTkLabel(
                        self.history_frame,
                        text=text,
                        font=("Courier New", 10),
                        text_color="#00FF88" if trade.net_pnl_usdc >= 0 else "#FF4060",
                    ).pack(anchor="w", padx=6, pady=2)

            else:

                ctk.CTkLabel(
                    self.history_frame,
                    text="No trades recorded",
                    font=("Courier New", 9),
                ).pack(pady=10)

            # ── LIQUIDEZ DO MERCADO ─────────────────────────

            radar = None

            # PRIORIDADE: auto_loop
            if self.auto_loop:
                radar = getattr(self.auto_loop, "market_radar", None)

            if radar is None and self.auto_loop:
                radar = getattr(self.auto_loop, "radar", None)

            # fallback: controller
            if radar is None and self.controller:
                radar = getattr(self.controller, "market_radar", None)

            if radar is None and self.controller:
                radar = getattr(self.controller, "radar", None)
            if radar:

                liquidity = getattr(radar, "market_liquidity", None)

                if liquidity is None:
                    liquidity = getattr(radar, "liquidity_data", None)

                if liquidity:
                    label = str(liquidity.get("liquidity_label", "-"))
                    score = float(liquidity.get("liquidity_score", 0.0))

                    self.mkt_pair_var.set(label)

                    score = max(0.0, min(score, 1.0))
                    self.strength_bar.set(score)

                    print("[UI] MARKET LIQUIDITY:", liquidity)

                else:
                    self.mkt_pair_var.set("-")
                    self.strength_bar.set(0.0)
                    print(
                        "[UI] MARKET LIQUIDITY: radar encontrado, mas sem market_liquidity"
                    )

            else:
                self.mkt_pair_var.set("-")
                self.strength_bar.set(0.0)
                print("[UI] MARKET LIQUIDITY: radar não encontrado")

        except Exception as e:
            print("UI sync error:", e)

    def _ui_loop(self):

        if not self.ui_running:
            return

        try:

            # -----------------------------
            # ESTADO DO SISTEMA
            # -----------------------------
            if self.locked:
                self.state_var.set("⊘ LOCKED")
            elif self.auto_loop and getattr(self.auto_loop, "running", False):
                self.state_var.set("STATE RUNNING")
            else:
                self.state_var.set("STATE IDLE")

            if self.live_var.get():
                self.mode_var.set("MODE LIVE")
            else:
                self.mode_var.set("MODE MOCK")
            # -----------------------------
            # CICLO
            # -----------------------------

            if self.auto_loop:
                self.cycle_var.set(str(self.auto_loop.cycle))
                if self.auto_loop.last_iter:
                    self.last_iter_var.set(self.auto_loop.last_iter)

            # -----------------------------
            # LATÊNCIAS
            # -----------------------------

            if self.auto_loop:

                if hasattr(self.auto_loop, "cycle_latency"):
                    self.api_lat_var.set(f"{self.auto_loop.cycle_latency} ms")

                if hasattr(self.auto_loop, "market_latency"):
                    self.mkt_lat_var.set(f"{self.auto_loop.market_latency} ms")

                if hasattr(self.auto_loop, "execution_latency"):
                    self.exec_lat_var.set(f"{self.auto_loop.execution_latency} ms")

            # -----------------------------
            # SYNC DOS SLOTS
            # -----------------------------

            self._sync_from_controller()

        except Exception as e:

            print("UI loop error:", e)

        # Atualiza UI a cada 1 segundo
        self.after(1000, self._ui_loop)


# ── ENTRY POINT ─────────────────────────────────────────────────

if __name__ == "__main__":
    app = HAControlPanel()
    app.mainloop()
