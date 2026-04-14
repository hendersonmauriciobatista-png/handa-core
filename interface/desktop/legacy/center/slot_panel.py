# interface/desktop/center/slot_panel.py

import tkinter as tk
from interface.viewmodel.slot_viewmodel import SlotViewModel, SlotViewData


class SlotPanel(tk.Frame):
    """
    Slot visual do H&A
    View pura (MVVM)
    Visual premium:
    - fundo neutro
    - cor como acento lateral
    - texto sempre legível
    - clique reativo
    - persistência visual de foco
    """

    HEIGHT = 110

    BG_NEUTRAL = "#F7F7F7"
    BORDER_NEUTRAL = "#D0D0D0"

    ACTIVE_BG = "#ECEFF4"        # destaque leve
    ACTIVE_BORDER = "#3B82F6"    # azul institucional sutil

    def __init__(self, master, slot_id: int, on_select=None):
        super().__init__(
            master,
            bg=self.BG_NEUTRAL,
            highlightbackground=self.BORDER_NEUTRAL,
            highlightthickness=1,
            height=self.HEIGHT
        )

        self.slot_id = slot_id
        self.on_select = on_select
        self.pack_propagate(False)

        self._current_view: SlotViewData | None = None
        self._is_active = False

        self._build_ui()
        self._bind_events()

    # =====================================================
    # UI
    # =====================================================
    def _build_ui(self):

        self.inner = tk.Frame(self, bg=self.BG_NEUTRAL)
        self.inner.pack(fill="both", expand=True)

        # faixa lateral de estado
        self.state_bar = tk.Frame(
            self.inner,
            bg="#CCCCCC",
            width=6
        )
        self.state_bar.pack(side="left", fill="y")

        # conteúdo
        self.content = tk.Frame(self.inner, bg=self.BG_NEUTRAL)
        self.content.pack(side="left", fill="both", expand=True)

        # HEADER
        self.header = tk.Label(
            self.content,
            text=f"SLOT {str(self.slot_id).zfill(2)}",
            bg=self.BG_NEUTRAL,
            fg="#222222",
            font=("Segoe UI", 9, "bold"),
            anchor="w"
        )
        self.header.pack(fill="x", padx=8, pady=(4, 2))

        # STATUS
        self.status_label = tk.Label(
            self.content,
            text="—",
            bg=self.BG_NEUTRAL,
            fg="#333333",
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.status_label.pack(fill="x", padx=8, pady=(0, 4))

        # PROGRESS BAR
        self.progress_frame = tk.Frame(
            self.content,
            bg="#E0E0E0",
            height=6
        )
        self.progress_frame.pack(fill="x", padx=8, pady=(0, 6))

        self.progress_bar = tk.Frame(
            self.progress_frame,
            bg="#999999",
            width=0,
            height=6
        )
        self.progress_bar.pack(side="left", fill="y")

    # =====================================================
    # EVENTS
    # =====================================================
    def _bind_events(self):
        widgets = [self, self.inner, self.content, self.header, self.status_label, self.progress_frame]

        for w in widgets:
            w.bind("<Button-1>", self._on_click)
            w.bind("<Enter>", lambda e: self.config(cursor="hand2"))
            w.bind("<Leave>", lambda e: self.config(cursor=""))

    def _on_click(self, event):
        if self.on_select:
            self.on_select(self.slot_id)

    # =====================================================
    # UPDATE
    # =====================================================
    def update_from_snapshot(self, snapshot: dict):
        vm = SlotViewModel(snapshot)
        view_data: SlotViewData = vm.build()

        if self._current_view == view_data:
            return

        self._current_view = view_data
        self._render(view_data)

    # =====================================================
    # RENDER
    # =====================================================
    def _render(self, view: SlotViewData):

        self.status_label.config(text=view.status_text)

        # cor como acento
        self.state_bar.config(bg=view.color)
        self.progress_bar.config(bg=view.color)

        self._set_progress(view.progress)

        if view.is_locked:
            self._apply_locked()
        else:
            self._apply_unlocked()

        # reaplica foco se ativo
        self.set_active(self._is_active)

    # =====================================================
    # PROGRESS
    # =====================================================
    def _set_progress(self, value: int):
        value = max(0, min(100, value))
        total_width = self.progress_frame.winfo_width()

        if total_width <= 1:
            self.after(50, lambda: self._set_progress(value))
            return

        width = int((value / 100) * total_width)
        self.progress_bar.config(width=width)

    # =====================================================
    # LOCK
    # =====================================================
    def _apply_locked(self):
        self.content.config(bg="#E0E0E0")
        self.inner.config(bg="#E0E0E0")
        self.header.config(bg="#E0E0E0")
        self.status_label.config(bg="#E0E0E0")

    def _apply_unlocked(self):
        base = self.ACTIVE_BG if self._is_active else self.BG_NEUTRAL
        self.content.config(bg=base)
        self.inner.config(bg=base)
        self.header.config(bg=base)
        self.status_label.config(bg=base)

    # =====================================================
    # ACTIVE STATE
    # =====================================================
    def set_active(self, active: bool):
        self._is_active = active

        if active:
            self.config(highlightbackground=self.ACTIVE_BORDER, highlightthickness=2)
            self.inner.config(bg=self.ACTIVE_BG)
            self.content.config(bg=self.ACTIVE_BG)
            self.header.config(bg=self.ACTIVE_BG)
            self.status_label.config(bg=self.ACTIVE_BG)
        else:
            self.config(highlightbackground=self.BORDER_NEUTRAL, highlightthickness=1)
            self.inner.config(bg=self.BG_NEUTRAL)
            self.content.config(bg=self.BG_NEUTRAL)
            self.header.config(bg=self.BG_NEUTRAL)
            self.status_label.config(bg=self.BG_NEUTRAL)
