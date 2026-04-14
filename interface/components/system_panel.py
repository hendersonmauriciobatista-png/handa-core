import customtkinter as ctk

TEXT_PRIMARY = "#e8e8e8"
TEXT_SECONDARY = "#8b949e"

GREEN = "#2ea043"
YELLOW = "#d29922"
RED = "#da3633"


class SystemPanel(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        # GRID 2x2
        self.grid_rowconfigure((0, 1), weight=1)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        # -------------------------
        # STATUS
        # -------------------------

        self.status_card = self._create_status_card()
        self.status_card.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # -------------------------
        # LATENCY
        # -------------------------

        self.latency_card = self._create_latency_card()
        self.latency_card.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        # -------------------------
        # ACTIVITY
        # -------------------------

        self.activity_card = self._create_activity_card()
        self.activity_card.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # -------------------------
        # MARKET STRENGTH
        # -------------------------

        self.market_strength_card = self._create_market_strength_card()
        self.market_strength_card.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

    # =========================================================
    # STATUS CARD
    # =========================================================

    def _create_status_card(self):

        card = ctk.CTkFrame(self, fg_color="#252a31", corner_radius=12)

        title = ctk.CTkLabel(
            card,
            text="SYSTEM STATUS",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_SECONDARY
        )
        title.pack(pady=(10, 5))

        self.state_label = ctk.CTkLabel(
            card,
            text="STATE IDLE",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_PRIMARY
        )
        self.state_label.pack(pady=(4, 2))

        self.mode_label = ctk.CTkLabel(
            card,
            text="MODE MOCK",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY
        )
        self.mode_label.pack()

        self.uptime_label = ctk.CTkLabel(
            card,
            text="UPTIME 00:00",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY
        )
        self.uptime_label.pack(pady=(0, 10))

        return card

    # =========================================================
    # LATENCY CARD
    # =========================================================

    def _create_latency_card(self):

        card = ctk.CTkFrame(self, fg_color="#252a31", corner_radius=12)

        title = ctk.CTkLabel(
            card,
            text="LATENCY",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_SECONDARY
        )
        title.pack(pady=(10, 5))

        self.api_latency = ctk.CTkLabel(
            card,
            text="API -- ms",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_PRIMARY
        )
        self.api_latency.pack()

        self.market_latency = ctk.CTkLabel(
            card,
            text="MARKET -- ms",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_PRIMARY
        )
        self.market_latency.pack()

        self.exec_latency = ctk.CTkLabel(
            card,
            text="EXECUTION -- ms",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_PRIMARY
        )
        self.exec_latency.pack(pady=(0, 10))

        return card

    # =========================================================
    # ACTIVITY CARD
    # =========================================================

    def _create_activity_card(self):

        card = ctk.CTkFrame(self, fg_color="#252a31", corner_radius=12)

        title = ctk.CTkLabel(
            card,
            text="H&A ACTIVITY",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_SECONDARY
        )
        title.pack(pady=(10, 5))

        self.cycle_label = ctk.CTkLabel(
            card,
            text="CYCLE 0",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_PRIMARY
        )
        self.cycle_label.pack()

        self.last_cycle_label = ctk.CTkLabel(
            card,
            text="LAST CYCLE -- s",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_PRIMARY
        )
        self.last_cycle_label.pack(pady=(0, 10))

        return card

    # =========================================================
    # MARKET STRENGTH CARD
    # =========================================================

    def _create_market_strength_card(self):

        card = ctk.CTkFrame(self, fg_color="#252a31", corner_radius=12)

        title = ctk.CTkLabel(
            card,
            text="MARKET STRENGTH",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_SECONDARY
        )
        title.pack(pady=(10, 5))

        self.market_symbol = ctk.CTkLabel(
            card,
            text="BTCUSDC",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY
        )
        self.market_symbol.pack()

        self.market_strength_value = ctk.CTkLabel(
            card,
            text="0 %",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=GREEN
        )
        self.market_strength_value.pack(pady=(5, 10))

        return card

    # =========================================================
    # UPDATE MARKET STRENGTH
    # =========================================================

    def update_market_strength(self, value: float):

        self.market_strength_value.configure(text=f"{value:.0f} %")

        if value < 30:
            color = RED
        elif value < 60:
            color = YELLOW
        else:
            color = GREEN

        self.market_strength_value.configure(text_color=color)