import tkinter as tk
from interface.desktop.theme.theme import BG_PANEL, FG_MUTED, BORDER


class TelemetryGraphPanel(tk.Frame):
    """
    Caixa de telemetria com mini-gráfico (0–100).
    Apenas leitura — sem botões, sem interação.
    """

    def __init__(
        self,
        parent,
        title: str,
        values: list[int],
        color: str,
        width=160,
        height=46
    ):
        super().__init__(
            parent,
            bg=BG_PANEL,
            bd=1,
            relief="solid",
            highlightthickness=1,
            highlightbackground=BORDER
        )

        self.values = values[-20:]
        self.color = color
        self.width = width
        self.height = height

        self._build(title)

    def _build(self, title):
        container = tk.Frame(self, bg=BG_PANEL)
        container.pack(padx=8, pady=6)

        # Título
        tk.Label(
            container,
            text=title,
            bg=BG_PANEL,
            fg=FG_MUTED,
            font=("Segoe UI", 8)
        ).pack(anchor="w")

        # Canvas do gráfico
        self.canvas = tk.Canvas(
            container,
            width=self.width,
            height=self.height,
            bg=BG_PANEL,
            highlightthickness=0
        )
        self.canvas.pack(pady=(4, 2))

        self._draw_graph()

    def _draw_graph(self):
        self.canvas.delete("all")

        h = self.height

        # Escala implícita 0–100
        self.canvas.create_line(0, 1, self.width, 1, fill="#2e2e2e")        # 100
        self.canvas.create_line(0, h / 2, self.width, h / 2, fill="#2a2a2a") # 50
        self.canvas.create_line(0, h - 1, self.width, h - 1, fill="#2e2e2e") # 0

        if len(self.values) < 2:
            return

        step_x = self.width / (len(self.values) - 1)
        points = []

        for i, value in enumerate(self.values):
            v = max(0, min(100, value))  # clamp de segurança
            x = i * step_x
            y = h - (v / 100) * h
            points.extend([x, y])

        self.canvas.create_line(
            points,
            fill=self.color,
            width=2,
            smooth=True
        )

