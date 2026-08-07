import tkinter as tk
from interface.desktop.center.slots_area import SlotsArea


class HANDA_LayoutBase(tk.Frame):

    # =====================
    # PALETA (CINZA NEUTRO)
    # =====================
    BG_MAIN = "#E5E7EB"
    BG_AREA = "#F9FAFB"
    BG_CENTER = "#F3F4F6"

    TEXT_PRIMARY = "#111827"
    TEXT_MUTED = "#6B7280"

    GREEN = "#2E5F3E"
    WATERMARK_COLOR = "#8B93A1"

    CENTER_TIMEOUT = 8000  # ms

    def __init__(self, master, ui_bus):
        super().__init__(master, bg=self.BG_MAIN)

        self.ui_bus = ui_bus

        self.active_slot_id = None
        self.center_active = False
        self.center_timer = None

        self.slots_area_left = None
        self.slots_area_right = None

        self._last_snapshots = {}

        self.pack(fill="both", expand=True)
        self._build_structure()

    # =====================================================
    # PLANTA GERAL
    # =====================================================
    def _build_structure(self):

        # ================= HEADER (UMA LINHA) =================
        header = tk.Frame(self, bg=self.BG_AREA, height=64, bd=1, relief="solid")
        header.pack(fill="x", padx=8, pady=6)
        header.pack_propagate(False)

        header.grid_columnconfigure(0, weight=1)  # logo
        header.grid_columnconfigure(1, weight=4)  # api
        header.grid_columnconfigure(2, weight=3)  # financeiro
        header.grid_columnconfigure(3, weight=4)  # controles
        header.grid_columnconfigure(4, weight=1)  # status

        # --- LOGO ---
        h_logo = tk.Frame(header, bg=self.BG_AREA)
        h_logo.grid(row=0, column=0, sticky="w", padx=12)

        tk.Label(
            h_logo,
            text="H&A",
            bg=self.BG_AREA,
            fg=self.TEXT_PRIMARY,
            font=("Segoe UI", 14, "bold")
        ).pack(anchor="w")

        # --- API KEYS ---
        h_api = tk.Frame(header, bg=self.BG_AREA)
        h_api.grid(row=0, column=1, sticky="w")

        api_style = {
            "font": ("Segoe UI", 9),
            "bd": 1,
            "relief": "solid"
        }

        self.api_key_entry = tk.Entry(h_api, width=26, **api_style)
        self.api_key_entry.pack(side="left", padx=(0, 6))
        self.api_key_entry.insert(0, "API KEY")
        self.api_key_entry.bind("<Return>", lambda e: self._emit_and_touch("API_KEY_SUBMIT"))

        self.api_secret_entry = tk.Entry(h_api, width=26, show="*", **api_style)
        self.api_secret_entry.pack(side="left")
        self.api_secret_entry.insert(0, "API SECRET")
        self.api_secret_entry.bind("<Return>", lambda e: self._emit_and_touch("API_SECRET_SUBMIT"))

        # --- FINANCEIRO ---
        h_fin = tk.Frame(header, bg=self.BG_AREA)
        h_fin.grid(row=0, column=2, sticky="w")

        self.balance_label = tk.Label(
            h_fin,
            text="Saldo: --",
            bg=self.BG_AREA,
            fg=self.TEXT_PRIMARY,
            font=("Segoe UI", 9, "bold")
        )
        self.balance_label.pack(anchor="w")

        self.profit_label = tk.Label(
            h_fin,
            text="Lucro: -- (USDC)",
            bg=self.BG_AREA,
            fg=self.TEXT_MUTED,
            font=("Segoe UI", 9)
        )
        self.profit_label.pack(anchor="w")

        # --- CONTROLES ---
        h_ctrl = tk.Frame(header, bg=self.BG_AREA)
        h_ctrl.grid(row=0, column=3, sticky="e")

        btn_style = {
            "font": ("Segoe UI", 9, "bold"),
            "height": 1,
            "bd": 1,
            "relief": "solid",
            "padx": 8
        }

        tk.Button(
            h_ctrl,
            text="START",
            command=lambda: self._emit_and_touch("SYSTEM_START"),
            **btn_style
        ).pack(side="left", padx=4)

        tk.Button(
            h_ctrl,
            text="SAFE",
            command=lambda: self._emit_and_touch("SYSTEM_SAFE_STOP"),
            **btn_style
        ).pack(side="left", padx=4)

        tk.Button(
            h_ctrl,
            text="EMERG",
            command=lambda: self._emit_and_touch("SYSTEM_EMERGENCY_STOP"),
            **btn_style
        ).pack(side="left", padx=4)

        # --- STATUS ---
        h_status = tk.Frame(header, bg=self.BG_AREA)
        h_status.grid(row=0, column=4, sticky="e", padx=12)

        self.status_label = tk.Label(
            h_status,
            text="IDLE",
            bg=self.BG_AREA,
            fg=self.GREEN,
            font=("Segoe UI", 10, "bold")
        )
        self.status_label.pack(anchor="e")

        # ================= BODY =================
        body = tk.Frame(self, bg=self.BG_MAIN)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=4)
        body.grid_columnconfigure(2, weight=3)

        left = tk.Frame(body, bg=self.BG_AREA, bd=1, relief="solid")
        left.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self.center = tk.Frame(body, bg=self.BG_CENTER, bd=1, relief="solid")
        self.center.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)

        right = tk.Frame(body, bg=self.BG_AREA, bd=1, relief="solid")
        right.grid(row=0, column=2, sticky="nsew", padx=6, pady=6)

        # Slots
        self.slots_area_left = SlotsArea(left, [1, 2, 3, 4, 5, 6], on_select=self.set_active_slot)
        self.slots_area_left.pack(fill="both", expand=True)

        self.slots_area_right = SlotsArea(right, [7, 8, 9, 10, 11, 12], on_select=self.set_active_slot)
        self.slots_area_right.pack(fill="both", expand=True)

        self._show_watermark()

    # =====================================================
    # TIMER
    # =====================================================
    def _reset_center_timer(self):
        if self.center_timer:
            self.after_cancel(self.center_timer)
        self.center_timer = self.after(self.CENTER_TIMEOUT, self._show_watermark)

    # =====================================================
    # WATERMARK
    # =====================================================
    def _show_watermark(self):
        if self.center_timer:
            self.after_cancel(self.center_timer)
            self.center_timer = None

        self.center_active = False
        self.active_slot_id = None

        self.slots_area_left.set_active(-1)
        self.slots_area_right.set_active(-1)

        for w in self.center.winfo_children():
            w.destroy()

        tk.Label(
            self.center,
            text="H&A",
            font=("Segoe UI", 72, "bold"),
            fg=self.WATERMARK_COLOR,
            bg=self.BG_CENTER
        ).pack(expand=True)

    # =====================================================
    # RENDER CENTRO
    # =====================================================
    def render_center(self, snapshot: dict):
        if not self.center_active:
            return

        for w in self.center.winfo_children():
            w.destroy()

        slot_id = snapshot.get("slot_id")
        pair = snapshot.get("pair", "---")
        state = snapshot.get("analysis_state", "—")
        progress = snapshot.get("progress", 0)
        locked = snapshot.get("locked", False)

        container = tk.Frame(self.center, bg=self.BG_CENTER)
        container.pack(expand=True)

        def line(label, value):
            row = tk.Frame(container, bg=self.BG_CENTER)
            row.pack(anchor="w", pady=6)
            tk.Label(row, text=label, bg=self.BG_CENTER,
                     fg=self.TEXT_MUTED,
                     font=("Segoe UI", 10, "bold")).pack(side="left")
            tk.Label(row, text=value, bg=self.BG_CENTER,
                     fg=self.TEXT_PRIMARY,
                     font=("Segoe UI", 10)).pack(side="left")

        tk.Label(container, text=f"SLOT {str(slot_id).zfill(2)}",
                 bg=self.BG_CENTER, fg=self.TEXT_PRIMARY,
                 font=("Segoe UI", 26, "bold")).pack(anchor="w", pady=(0, 20))

        line("Par: ", pair)
        line("Estado: ", state)
        line("Progresso: ", f"{progress}%")
        line("Lock: ", "Sim" if locked else "Não")

    # =====================================================
    # UPDATE
    # =====================================================
    def update_slots(self, snapshots: dict):
        self._last_snapshots = snapshots

        left = {}
        right = {}

        for slot_id, snap in snapshots.items():
            snap["slot_id"] = slot_id
            if slot_id <= 6:
                left[slot_id] = snap
            else:
                right[slot_id] = snap

        self.slots_area_left.update_from_snapshots(left)
        self.slots_area_right.update_from_snapshots(right)

        core_state = self.ui_bus.get_core_state()
        active_center = core_state.active_center

        if active_center and active_center in snapshots:
            self.center_active = True
            self.active_slot_id = active_center
            self.render_center(snapshots[active_center])
        else:
            self._show_watermark()

    # =====================================================
    # EVENTOS
    # =====================================================
    def _emit_and_touch(self, event, data=None):
        self.ui_bus.emit(event, data)
        self._reset_center_timer()

    def set_active_slot(self, slot_id: int):
        self.ui_bus.emit("SLOT_SELECT", {"slot_id": slot_id})
        self.center_active = True
        self._reset_center_timer()
