import tkinter as tk


# ==============================
# DARK INDUSTRIAL PROPORCIONAL
# ==============================

BG_WINDOW = "#1e1f23"
BG_HEADER = "#24262b"
BG_PANEL = "#24262b"
BG_CENTER = "#2c2f35"
BG_SLOT = "#2a2d33"

BORDER_COLOR = "#3a3d44"
GREEN_ACTIVE = "#00c853"

TEXT_PRIMARY = "#e4e6eb"
TEXT_SECONDARY = "#9aa0a6"

STATE_COLORS = {
    "IDLE": "#9aa0a6",
    "ANALYZING": "#2979ff",
    "TRADING": "#00c853",
    "ERROR": "#d50000",
}


class MainLayout(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG_WINDOW)
        self.pack(fill="both", expand=True)

        self.slot_widgets = {}
        self.slot_states = {}
        self.selected_slot = None
        self.center_timer = None

        self._build_layout()

    # =====================================================
    # LAYOUT BASE
    # =====================================================

    def _build_layout(self):

        self.rowconfigure(0, weight=0)   # header
        self.rowconfigure(1, weight=1)   # main
        self.rowconfigure(2, weight=0)   # status

        self.columnconfigure(0, weight=1)

        self._build_header()
        self._build_main_panel()
        self._build_status_bar()

    # =====================================================
    # HEADER
    # =====================================================

    def _build_header(self):

        header = tk.Frame(self, bg=BG_HEADER, height=60,
                          highlightbackground=BORDER_COLOR,
                          highlightthickness=1)
        header.grid(row=0, column=0, sticky="nsew")

        tk.Label(
            header,
            text="H&A CONTROL PANEL",
            bg=BG_HEADER,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 14, "bold")
        ).pack(side="left", padx=20)

    # =====================================================
    # MAIN PANEL
    # =====================================================

    def _build_main_panel(self):

        main = tk.Frame(
            self,
            bg=BG_PANEL,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1
        )
        main.grid(row=1, column=0, sticky="nsew", padx=40, pady=20)

        # 40 - 30 - 40 proporcional
        
        main.columnconfigure(0, weight=4)
        main.columnconfigure(1, weight=3)
        main.columnconfigure(2, weight=4)


        main.rowconfigure(0, weight=1)

        self._build_left(main)
        self._build_center(main)
        self._build_right(main)

    # =====================================================
    # LEFT COL
    # =====================================================

    def _build_left(self, parent):

        left = tk.Frame(parent, bg=BG_PANEL)
        left.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        for i in range(6):
            left.rowconfigure(i, weight=1)
            slot = self._create_slot(left, i + 1)
            slot.grid(row=i, column=0, sticky="nsew", pady=6)

    # =====================================================
    # CENTER
    # =====================================================

    def _build_center(self, parent):

        center = tk.Frame(
            parent,
            bg=BG_CENTER,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1
        )
        center.grid(row=0, column=1, sticky="nsew", padx=(30, 30), pady=20)


        self.center_panel = center

        self.watermark = tk.Label(
            center,
            text="H&A",
            bg=BG_CENTER,
            fg="#3a3d44",
            font=("Segoe UI", 100, "bold")
        )
        self.watermark.place(relx=0.5, rely=0.5, anchor="center")

        self.center_info = tk.Label(
            center,
            text="",
            bg=BG_CENTER,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 16, "bold")
        )
        self.center_info.place(relx=0.5, rely=0.85, anchor="center")

    # =====================================================
    # RIGHT COL
    # =====================================================

    def _build_right(self, parent):

        right = tk.Frame(parent, bg=BG_PANEL)
        right.grid(row=0, column=2, sticky="nsew", padx=20, pady=20)

        for i in range(6):
            right.rowconfigure(i, weight=1)
            slot = self._create_slot(right, i + 7)
            slot.grid(row=i, column=0, sticky="nsew", pady=6)

    # =====================================================
    # SLOT PROPORCIONAL
    # =====================================================

    def _create_slot(self, parent, number):

        container = tk.Frame(parent, bg=BG_PANEL)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        active_border = tk.Frame(container, bg=BG_PANEL, width=4)
        active_border.grid(row=0, column=0, sticky="ns")

        slot = tk.Frame(
            container,
            bg=BG_SLOT,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1
        )
        slot.grid(row=0, column=1, sticky="nsew")

        self.slot_widgets[number] = (container, active_border)
        self.slot_states[number] = "IDLE"

        slot.columnconfigure(0, weight=1)
        slot.rowconfigure(0, weight=1)
        slot.rowconfigure(1, weight=2)
        slot.rowconfigure(2, weight=1)

        tk.Label(
            slot,
            text=f"SLOT {number}",
            bg=BG_SLOT,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 9, "bold")
        ).grid(row=0, column=0, sticky="w", padx=10)

        state_label = tk.Label(
            slot,
            text="IDLE",
            bg=BG_SLOT,
            fg=STATE_COLORS["IDLE"],
            font=("Segoe UI", 11, "bold")
        )
        state_label.grid(row=1, column=0)

        tk.Label(
            slot,
            text="—",
            bg=BG_SLOT,
            fg=TEXT_SECONDARY,
            font=("Segoe UI", 8)
        ).grid(row=2, column=0)

        self.slot_widgets[number] += (state_label,)
        self._bind_recursive(container, number)

        return container

    # =====================================================

    def _bind_recursive(self, widget, number):
        widget.bind("<Button-1>", lambda e: self._cycle_state(number))
        for child in widget.winfo_children():
            self._bind_recursive(child, number)

    # =====================================================

    def _cycle_state(self, number):

        states = ["IDLE", "ANALYZING", "TRADING", "ERROR"]
        current = self.slot_states[number]
        next_state = states[(states.index(current) + 1) % len(states)]
        self.slot_states[number] = next_state

        for n in self.slot_widgets:
            _, border, state_label = self.slot_widgets[n]
            border.config(bg=BG_PANEL)

        container, border, state_label = self.slot_widgets[number]
        state_label.config(text=next_state, fg=STATE_COLORS[next_state])
        border.config(bg=GREEN_ACTIVE)

        self._show_center_focus(number, next_state)

    # =====================================================

    def _show_center_focus(self, number, state):

        if self.center_timer:
            self.after_cancel(self.center_timer)

        self.watermark.place_forget()
        self.center_info.config(text=f"SLOT {number} — {state}")

        self.center_timer = self.after(8000, self._restore_center)

    # =====================================================

    def _restore_center(self):
        self.center_info.config(text="")
        self.watermark.place(relx=0.5, rely=0.5, anchor="center")
        self.center_timer = None

    # =====================================================

    def _build_status_bar(self):

        status = tk.Frame(
            self,
            bg=BG_HEADER,
            height=40,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1
        )
        status.grid(row=2, column=0, sticky="nsew")

        tk.Label(
            status,
            text="ATIVIDADE DO SISTEMA",
            bg=BG_HEADER,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 9)
        ).pack(side="left", padx=20)

        tk.Label(
            status,
            text="LATÊNCIA: 0ms",
            bg=BG_HEADER,
            fg=TEXT_SECONDARY,
            font=("Consolas", 9)
        ).pack(side="right", padx=20)
