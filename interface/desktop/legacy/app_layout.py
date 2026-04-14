import tkinter as tk

from .adapters.core_adapter import CoreAdapter
from .state.slot_registry import SlotRegistry
from .state.ui_state import UIState
from .state.risk_state import RiskState

from .components.slots_grid import SlotsGrid
from .components.slot_focus_panel import SlotFocusPanel
from .components.footer_status import FooterStatus


class AppLayout(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("H&A — Control Panel")

        # ---------------------------------
        # Core / States
        # ---------------------------------
        self.adapter = CoreAdapter()
        self.registry = SlotRegistry()
        self.ui_state = UIState()
        self.risk_state = RiskState()

        # ---------------------------------
        # UI Components
        # ---------------------------------
        self.slots_grid = SlotsGrid(self, self.registry, self.ui_state)
        self.slots_grid.pack(side="left", fill="y")

        self.focus_panel = SlotFocusPanel(self, self.registry, self.ui_state)
        self.focus_panel.pack(side="right", fill="both", expand=True)

        self.footer = FooterStatus(self, self.risk_state)
        self.footer.pack(side="bottom", fill="x")

        # ---------------------------------
        # Loop
        # ---------------------------------
        self.after(500, self.refresh)

    # ---------------------------------
    # Refresh Loop (BOOT SAFE)
    # ---------------------------------
    def refresh(self):
        slots = self.adapter.get_slots_state()
        risk = self.adapter.get_global_risk()

        # 🛡️ BOOT SAFE:
        # só atualiza o registry quando
        # os 12 slots estiverem disponíveis
        if len(slots) == 12:
            self.registry.update(slots)

            self.slots_grid.render()
            self.focus_panel.refresh()
        else:
            # fase inicial: ainda aguardando eventos reais
            pass

        self.risk_state.update(risk)
        self.footer.refresh()

        self.after(500, self.refresh)


# ---------------------------------
# Entry point
# ---------------------------------
if __name__ == "__main__":
    app = AppLayout()
    app.mainloop()
