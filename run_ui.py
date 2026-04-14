import tkinter as tk
from interface.desktop.layout_base import HANDA_LayoutBase
from interface.desktop.ui_bus import UIBus   # ou equivalente real


def main():
    root = tk.Tk()
    root.title("H&A — Control Panel")
    root.geometry("1400x900")

    ui_bus = UIBus()  # o mesmo que já conversa com o core
    HANDA_LayoutBase(root, ui_bus)

    root.mainloop()


if __name__ == "__main__":
    main()
