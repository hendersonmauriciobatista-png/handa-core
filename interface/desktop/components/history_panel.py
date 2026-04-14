import customtkinter as ctk
import tkinter as tk
from tkinter import ttk


BG_PANEL = "#1e2126"
BG_TREE = "#20242a"
BG_HEADER = "#262a30"

COLOR_TEXT = "#e6e6e6"
COLOR_MUTED = "#9aa0a6"
COLOR_POSITIVE = "#00c853"
COLOR_NEGATIVE = "#d50000"


class HistoryPanel(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color=BG_PANEL, corner_radius=18)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ======================
        # TÍTULO
        # ======================
        title = ctk.CTkLabel(
            self,
            text="HISTORY",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT
        )
        title.grid(row=0, column=0, sticky="w", padx=20, pady=(15, 5))

        # ======================
        # STYLE TREEVIEW
        # ======================
        style = ttk.Style()
        style.theme_use("default")

        style.configure("Treeview",
                        background=BG_TREE,
                        foreground=COLOR_TEXT,
                        fieldbackground=BG_TREE,
                        rowheight=26,
                        borderwidth=0)

        style.configure("Treeview.Heading",
                        background=BG_HEADER,
                        foreground=COLOR_MUTED,
                        font=("Segoe UI", 10, "bold"))

        style.map("Treeview",
                  background=[("selected", "#2f343c")])

        # ======================
        # TREEVIEW
        # ======================
        columns = ("slot", "pair", "result", "time", "type", "hour")

        self.tree = ttk.Treeview(
            self,
            columns=columns,
            show="headings"
        )

        for col in columns:
            self.tree.heading(col, text=col.upper())
            self.tree.column(col, anchor="center", stretch=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.grid(row=1, column=0, sticky="nsew", padx=(20, 0), pady=(0, 15))
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(0, 15), padx=(0, 20))

    # =====================================================
    # ADICIONAR CICLO
    # =====================================================

    def add_cycle(self, slot, pair, result, duration, cycle_type, hour):

        item_id = self.tree.insert(
            "",
            0,
            values=(slot, pair, result, duration, cycle_type, hour)
        )

        # Cor do resultado
        if result.startswith("-"):
            self.tree.item(item_id, tags=("negative",))
        else:
            self.tree.item(item_id, tags=("positive",))

        self.tree.tag_configure("positive", foreground=COLOR_POSITIVE)
        self.tree.tag_configure("negative", foreground=COLOR_NEGATIVE)

    # =====================================================
    # LIMPAR HISTÓRICO
    # =====================================================

    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)


# =========================================================
# TESTE ISOLADO
# =========================================================

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")

    app = ctk.CTk()
    app.geometry("900x400")

    panel = HistoryPanel(app)
    panel.pack(fill="both", expand=True, padx=20, pady=20)

    # Simulação
    panel.add_cycle("1", "BTCUSDC", "+1.42%", "02:14", "META", "21:43")
    panel.add_cycle("3", "SOLUSDC", "-0.32%", "05:11", "STOP", "20:58")
    panel.add_cycle("2", "ETHUSDC", "+0.89%", "01:33", "META", "20:10")

    app.mainloop()
