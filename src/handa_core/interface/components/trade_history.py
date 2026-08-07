import customtkinter as ctk

TEXT_PRIMARY = "#e8e8e8"
TEXT_SECONDARY = "#8b949e"

GREEN = "#2ea043"
RED = "#da3633"


class TradeHistory(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color="#252a31", corner_radius=12)

        self.trades = []

        title = ctk.CTkLabel(
            self,
            text="TRADE HISTORY",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_SECONDARY
        )
        title.pack(pady=(10, 5))

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.labels = []

        for _ in range(10):

            label = ctk.CTkLabel(
                self.container,
                text="--",
                font=ctk.CTkFont(size=12),
                text_color=TEXT_PRIMARY,
                anchor="w"
            )

            label.pack(fill="x")

            self.labels.append(label)

    def add_trade(self, time, pair, side, pnl=None):

        if pnl is None:
            text = f"{time}  {pair}  {side}"
            color = TEXT_PRIMARY
        else:
            text = f"{time}  {pair}  {side}  {pnl:+.2f}%"
            color = GREEN if pnl >= 0 else RED

        self.trades.insert(0, (text, color))

        if len(self.trades) > 10:
            self.trades.pop()

        self._refresh()

    def _refresh(self):

        for i, label in enumerate(self.labels):

            if i < len(self.trades):
                text, color = self.trades[i]

                label.configure(
                    text=text,
                    text_color=color
                )
            else:
                label.configure(text="--", text_color=TEXT_PRIMARY)