import tkinter as tk

from core.slot_manager import SlotManager
from dummy_executor import DummyExecutor
from interface.viewmodel.app_viewmodel import AppViewModel
from interface.desktop.icfactory.views.slot_panel import SlotPanel
from interface.desktop.icfactory.views.slot_detail_panel import SlotDetailPanel


class ICFactoryApp:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ICFactory - H&A")
        self.root.configure(bg="#1E1E1E")

        self.slot_manager = SlotManager()

        from core.slot import Slot

        for i in range(1, 13):
            self.slot_manager.add_slot(i, Slot(i))

        self.viewmodel = AppViewModel(self.slot_manager)

        # Layout horizontal
        self.container = tk.Frame(self.root, bg="#1E1E1E")
        self.container.pack(padx=20, pady=20)

        self.slot_panel = SlotPanel(
            parent=self.container,
            viewmodel=self.viewmodel,
            slot_manager=self.slot_manager
        )
        self.slot_panel.pack(side="left", padx=20)

        self.detail_panel = SlotDetailPanel(
            parent=self.container,
            viewmodel=self.viewmodel
        )
        self.detail_panel.pack(side="right", padx=20)

    def start(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ICFactoryApp()
    app.start()
