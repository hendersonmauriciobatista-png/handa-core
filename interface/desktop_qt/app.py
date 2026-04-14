import tkinter as tk

from core.runtime.auto_loop import AutoLoop
from core.slot_controller import SlotController

from interface.desktop.header.header import HeaderArea
from interface.desktop.body.body import BodyArea
from interface.desktop.history.history_panel import HistoryPanel


def main():
    root = tk.Tk()
    root.title("H&A — Henderson & Alfred")
    root.geometry("1200x800")

    # CORE
    slot_controller = SlotController(slot_ids=[1, 2, 3, 4, 5, 6])
    auto_loop = AutoLoop(slot_controller, interval=1.0)

    # HEADER
    header = HeaderArea(root, auto_loop, slot_controller)
    header.pack(fill="x")

    # BODY (BASE CONGELADA)
    body = BodyArea(root, slot_controller)
    body.pack(fill="both", expand=True)

    # HISTORY
    history = HistoryPanel(root)
    history.pack(fill="x")

    root.mainloop()


if __name__ == "__main__":
    main()
