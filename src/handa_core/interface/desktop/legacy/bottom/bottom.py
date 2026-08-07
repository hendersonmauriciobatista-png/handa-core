import tkinter as tk


class BottomArea(tk.Frame):
    """
    Bottom do H&A Desktop
    UI BURRA — layout congelado
    """

    def __init__(self, master):
        super().__init__(master, bg="#f2f2f2")
        self._build_ui()

    def _build_ui(self):
        container = tk.Frame(self, bg="#f2f2f2")
        container.pack(fill="x", padx=10, pady=(0, 6))

        # =========================
        # ATIVIDADE DO H&A
        # =========================
        activity = self._metric_box(container, "Atividade do H&A")
        activity.pack(side="left", fill="both", expand=True, padx=(0, 6))

        # =========================
        # LATÊNCIA
        # =========================
        latency = self._metric_box(container, "Latência do Sistema")
        latency.pack(side="right", fill="both", expand=True, padx=(6, 0))

    def _metric_box(self, parent, title):
        box = tk.Frame(
            parent,
            bg="#f2f2f2",
            highlightbackground="#c0c0c0",
            highlightthickness=1,
            height=120
        )
        box.pack_propagate(False)

        tk.Label(
            box,
            text=title,
            bg="#f2f2f2",
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", padx=6, pady=(4, 2))

        body = tk.Frame(box, bg="#f2f2f2")
        body.pack(fill="both", expand=True, padx=6, pady=4)

        # Escala lateral
        scale = tk.Frame(body, bg="#f2f2f2", width=30)
        scale.pack(side="left", fill="y")

        for val in (100, 75, 50, 25, 0):
            tk.Label(
                scale,
                text=str(val),
                bg="#f2f2f2",
                fg="#555555",
                font=("Segoe UI", 8)
            ).pack(anchor="e")

        # Área visual vazia
        tk.Frame(body, bg="#e8e8e8").pack(side="left", fill="both", expand=True, padx=(6, 0))

        return box
