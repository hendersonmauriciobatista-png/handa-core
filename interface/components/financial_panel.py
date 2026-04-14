import customtkinter as ctk

TEXT_PRIMARY = "#e8e8e8"
TEXT_SECONDARY = "#8b949e"

GREEN = "#2ea043"
RED = "#da3633"


class FinancialPanel(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        self.grid_columnconfigure((0, 1), weight=1)

        self.balance_card = self._create_balance_card()
        self.balance_card.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.profit_card = self._create_profit_card()
        self.profit_card.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

    def _create_balance_card(self):

        card = ctk.CTkFrame(self, fg_color="#252a31", corner_radius=12)

        title = ctk.CTkLabel(
            card,
            text="BALANCE",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_SECONDARY
        )
        title.pack(pady=(10, 5))

        self.usdc_label = ctk.CTkLabel(
            card,
            text="USDC 0.00",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_PRIMARY
        )
        self.usdc_label.pack()

        self.brl_label = ctk.CTkLabel(
            card,
            text="≈BRL 0.00",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_SECONDARY
        )
        self.brl_label.pack()

        self.eur_label = ctk.CTkLabel(
            card,
            text="≈EUR 0.00",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_SECONDARY
        )
        self.eur_label.pack(pady=(0, 10))

        return card

    def _create_profit_card(self):

        card = ctk.CTkFrame(self, fg_color="#252a31", corner_radius=12)

        title = ctk.CTkLabel(
            card,
            text="PROFIT",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_SECONDARY
        )
        title.pack(pady=(10, 5))

        self.today_label = ctk.CTkLabel(
            card,
            text="TODAY 0.00",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_PRIMARY
        )
        self.today_label.pack()

        self.total_label = ctk.CTkLabel(
            card,
            text="TOTAL 0.00",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_PRIMARY
        )
        self.total_label.pack(pady=(0, 10))

        return card

    def update_balance(self, usdc, brl, eur):

        self.usdc_label.configure(text=f"USDC {usdc:.2f}")
        self.brl_label.configure(text=f"≈BRL {brl:.2f}")
        self.eur_label.configure(text=f"≈EUR {eur:.2f}")

    def update_profit(self, today, total):

        color_today = GREEN if today >= 0 else RED
        color_total = GREEN if total >= 0 else RED

        self.today_label.configure(
            text=f"TODAY {today:.2f}",
            text_color=color_today
        )

        self.total_label.configure(
            text=f"TOTAL {total:.2f}",
            text_color=color_total
        )