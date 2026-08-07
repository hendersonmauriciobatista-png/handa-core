import tkinter as tk

# UI components
from interface.desktop.header.header import HeaderArea
from interface.desktop.balance_panel import BalancePanel

# ============================
# MOCKS (até plugar no core real)
# ============================

class MockCore:
    def validate_keys(self, api, secret):
        return True

    def get_financial_snapshot(self, currency):
        return {
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

class MockAutoLoop:
    def start(self): pass
    def stop(self): pass

class MockSlotController:
    def start_all(self): pass
    def stop_all(self): pass

# ============================
# APP PRINCIPAL
# ============================

class App(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("H&A Trading System")
        self.geometry("1400x800")
        self.configure(bg="#121212")

        # ============================
        # ESTADO GLOBAL
        # ============================
        self.mode = "MOCK"

        # ============================
        # CORE / CONTROLLERS
        # ============================
        self.core = MockCore()               # depois troca pelo core real
        self.auto_loop = MockAutoLoop()      # depois troca pelo real
        self.slot_controller = MockSlotController()  # depois troca pelo real

        # ============================
        # CONTAINER PRINCIPAL
        # ============================
        self.main_container = tk.Frame(self, bg="#121212")
        self.main_container.pack(fill="both", expand=True)

        # ============================
        # BALANCE PANEL (LATERAL DIREITO)
        # ============================
        self.balance_panel = BalancePanel(
            self.main_container,
            core=self.core,
            mode=self.mode
        )

        # ============================
        # HEADER
        # ============================
        self.header = HeaderArea(
            self.main_container,
            auto_loop=self.auto_loop,
            slot_controller=self.slot_controller,
            core=self.core
        )
        self.header.pack(side="top", fill="x")

        # 🔌 injeção do painel no header
        self.header.balance_panel = self.balance_panel

        # botão SALDO no header
        self.header.balance_btn = tk.Button(
            self.header,
            text="SALDO",
            font=("Segoe UI", 8, "bold"),
            command=self.balance_panel.toggle
        )
        self.header.balance_btn.place(relx=0.99, rely=0.5, anchor="e")

        # ============================
        # ÁREA CENTRAL (SLOTS FUTUROS)
        # ============================
        self.center_area = tk.Frame(self.main_container, bg="#181818")
        self.center_area.pack(fill="both", expand=True)

        self.placeholder = tk.Label(
            self.center_area,
            text="SLOTS AREA",
            fg="#666666",
            bg="#181818",
            font=("Segoe UI", 14, "bold")
        )
        self.placeholder.pack(expand=True)

        # ======================================================
        # 🔗 CORE BINDING — FASE 1 (STATE → UI)
        # ======================================================

        from core.state.state_store import StateStore
        from core.render.renderer import Renderer
        from core.ui_binding.ui_binder import UIBinder

        # Widgets reais da UI (mínimo funcional)
        self.widgets = {
            # usando placeholder central como prova de vida
            "system_label": self.placeholder
        }

        self.state_store = StateStore()
        self.renderer = Renderer(self.widgets)
        self.ui_binder = UIBinder(self.state_store, self.renderer)

        # 🧪 PROVA DE VIDA AUTOMÁTICA (sem clique, sem botão)
        # isso valida que o binding está funcionando
        self.after(1500, lambda: self.state_store.set("system_status", "DRAINING"))
        self.after(3500, lambda: self.state_store.set("system_status", "LOCKDOWN"))
        self.after(5500, lambda: self.state_store.set("system_status", "RUNNING"))

        # ============================
        # UPDATE LOOP FINANCEIRO
        # ============================
        self._start_financial_loop()

    # ============================
    # UPDATE FINANCEIRO
    # ============================

    def _start_financial_loop(self):
        def loop():
            if self.balance_panel.visible:
                self.balance_panel.update_data()
            self.after(3000, loop)

        loop()


# ============================
# RUN
# ============================

if __name__ == "__main__":
    app = App()
    app.mainloop()
