import customtkinter as ctk

from h_a.state_controller import StateController, SystemState
from h_a.system_state_assembler import SystemStateAssembler
from h_a.execution_mode import ExecutionMode
from h_a.slot_engine.slot_manager import SlotManager

from interface.desktop.components.health_panel import HealthPanel
from interface.desktop.components.latency_panel import LatencyPanel
from interface.desktop.components.history_panel import HistoryPanel


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG_WINDOW = "#16181c"
BG_PANEL = "#1e2126"
BG_SLOT = "#20242a"
BG_CORE = "#23272e"

TEXT_PRIMARY = "#e6e6e6"
TEXT_SECONDARY = "#9aa0a6"


class MainLayout(ctk.CTk):

    def __init__(self):
        super().__init__()

        # ==============================
        # SISTEMA
        # ==============================

        self.controller = StateController()
        self.assembler = SystemStateAssembler(self.controller)
        self.slot_manager = SlotManager()

        self.controller.add_listener(self._on_state_change)

        # ==============================
        # UI
        # ==============================

        self.title("H&A CONTROL PANEL")
        self.geometry("1300x900")
        self.configure(fg_color=BG_WINDOW)

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_main()
        self._build_status()

        self.after(1000, self._system_tick)

        self._update_buttons(SystemState.IDLE)
        self._update_status_bar()

    # =====================================================
    # SISTEMA
    # =====================================================

    def _on_state_change(self, new_state):

        if new_state == SystemState.RUNNING:
            self.slot_manager.start()

        elif new_state == SystemState.DRAINING:
            self.slot_manager.drain()

        elif new_state == SystemState.IDLE:
            self.slot_manager.stop()

        elif new_state == SystemState.LOCKED:
            self.slot_manager.stop()

        self._update_buttons(new_state)
        self._update_status_bar()

    def _system_tick(self):
        self.slot_manager.tick()
        self._update_status_bar()
        self.after(1000, self._system_tick)

    def _update_status_bar(self):
        state = self.assembler.build()
        status = state["system"]["system_status"]
        mode = state["system"]["mode"]
        self.status_label.configure(text=f"SYSTEM STATUS: {status} | MODE: {mode}")

    # =====================================================
    # SWITCH MOCK / LIVE
    # =====================================================

    def _toggle_mode(self):
        if self.mode_switch.get() == 1:
            self.assembler.set_mode(ExecutionMode.LIVE)
        else:
            self.assembler.set_mode(ExecutionMode.MOCK)

        self._update_status_bar()

    # =====================================================
    # CONTROLE DE BOTÕES
    # =====================================================

    def _update_buttons(self, state):

        if state == SystemState.IDLE:
            self.start_btn.configure(state="normal")
            self.drain_btn.configure(state="disabled")
            self.reset_btn.configure(state="disabled")
            self.lock_btn.configure(state="normal")

        elif state == SystemState.RUNNING:
            self.start_btn.configure(state="disabled")
            self.drain_btn.configure(state="normal")
            self.reset_btn.configure(state="disabled")
            self.lock_btn.configure(state="normal")

        elif state == SystemState.DRAINING:
            self.start_btn.configure(state="disabled")
            self.drain_btn.configure(state="disabled")
            self.reset_btn.configure(state="normal")
            self.lock_btn.configure(state="disabled")

        elif state == SystemState.LOCKED:
            self.start_btn.configure(state="disabled")
            self.drain_btn.configure(state="disabled")
            self.reset_btn.configure(state="disabled")
            self.lock_btn.configure(state="normal")

    # =====================================================
    # HEADER
    # =====================================================

    def _build_header(self):

        header = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=60)
        header.grid(row=0, column=0, sticky="nsew")

        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)
        header.grid_columnconfigure(2, weight=0)

        title = ctk.CTkLabel(
            header,
            text="H&A CONTROL PANEL",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=TEXT_PRIMARY
        )
        title.grid(row=0, column=0, pady=15, sticky="w", padx=20)

        # ========================
        # SWITCH MOCK / LIVE
        # ========================

        self.mode_switch = ctk.CTkSwitch(
            header,
            text="LIVE MODE",
            command=self._toggle_mode
        )
        self.mode_switch.grid(row=0, column=1, padx=20)

        # ========================
        # BOTÕES
        # ========================

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=2, padx=20)

        self.start_btn = ctk.CTkButton(
            controls,
            text="START",
            fg_color="#1f6f43",
            command=self.controller.start
        )
        self.start_btn.pack(side="left", padx=5)

        self.drain_btn = ctk.CTkButton(
            controls,
            text="DRAIN",
            fg_color="#8a6d1d",
            command=self.controller.stop
        )
        self.drain_btn.pack(side="left", padx=5)

        self.reset_btn = ctk.CTkButton(
            controls,
            text="RESET",
            fg_color="#6c757d",
            command=self.controller.finish_drain
        )
        self.reset_btn.pack(side="left", padx=5)

        self.lock_btn = ctk.CTkButton(
            controls,
            text="LOCK",
            fg_color="#7a1f1f",
            command=self.controller.lock
        )
        self.lock_btn.pack(side="left", padx=5)

    # =====================================================
    # RESTANTE DA UI
    # =====================================================

    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=20)
        main.grid(row=1, column=0, sticky="nsew", padx=40, pady=25)

        main.grid_rowconfigure(0, weight=3)
        main.grid_rowconfigure(1, weight=3)
        main.grid_rowconfigure(2, weight=2)
        main.grid_rowconfigure(3, weight=3)

        main.grid_columnconfigure(0, weight=1)

        self._build_slots(main)
        self._build_core(main)
        self._build_health_latency(main)
        self._build_history(main)

    def _build_slots(self, parent):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.grid(row=0, column=0, sticky="nsew", padx=40, pady=20)

        container.grid_rowconfigure((0, 1), weight=1)
        container.grid_columnconfigure((0, 1), weight=1)

        for i in range(4):
            row = i // 2
            col = i % 2
            slot = self._create_slot(container, i + 1)
            slot.grid(row=row, column=col, sticky="nsew", padx=20, pady=20)

    def _create_slot(self, parent, number):
        slot = ctk.CTkFrame(parent, fg_color=BG_SLOT, corner_radius=18)

        title = ctk.CTkLabel(
            slot,
            text=f"SLOT {number}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_PRIMARY
        )
        title.pack(pady=(15, 5))

        state = ctk.CTkLabel(
            slot,
            text="IDLE",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=TEXT_SECONDARY
        )
        state.pack()

        footer = ctk.CTkLabel(
            slot,
            text="—",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY
        )
        footer.pack(pady=(5, 15))

        return slot

    def _build_core(self, parent):
        core = ctk.CTkFrame(parent, fg_color=BG_CORE, corner_radius=25)
        core.grid(row=1, column=0, sticky="nsew", padx=60, pady=10)

        watermark = ctk.CTkLabel(
            core,
            text="H&A",
            font=ctk.CTkFont(size=110, weight="bold"),
            text_color="#2f343c"
        )
        watermark.place(relx=0.5, rely=0.5, anchor="center")

    def _build_health_latency(self, parent):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.grid(row=2, column=0, sticky="nsew", padx=60, pady=10)

        container.grid_columnconfigure((0, 1), weight=1)

        self.health_panel = HealthPanel(container)
        self.health_panel.grid(row=0, column=0, sticky="nsew", padx=10)

        self.latency_panel = LatencyPanel(container)
        self.latency_panel.grid(row=0, column=1, sticky="nsew", padx=10)

    def _build_history(self, parent):
        self.history_panel = HistoryPanel(parent)
        self.history_panel.grid(row=3, column=0, sticky="nsew", padx=60, pady=(10, 20))

    def _build_status(self):
        status = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=0, height=40)
        status.grid(row=2, column=0, sticky="nsew")

        self.status_label = ctk.CTkLabel(
            status,
            text="SYSTEM STATUS: IDLE | MODE: MOCK",
            text_color=TEXT_SECONDARY
        )
        self.status_label.pack(pady=10)


if __name__ == "__main__":
    app = MainLayout()
    app.mainloop()
