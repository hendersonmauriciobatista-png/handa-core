import customtkinter as ctk

TEXT_PRIMARY = "#e8e8e8"
TEXT_SECONDARY = "#8b949e"

GREEN = "#2ea043"
YELLOW = "#d29922"
RED = "#da3633"


class Header(ctk.CTkFrame):

    def __init__(self, parent, controller, exchange="BINANCE"):
        super().__init__(parent, height=50, fg_color="#1e2228")

        self.controller = controller
        self.exchange = exchange

        self.grid_columnconfigure(0, weight=1)

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20)

        left = ctk.CTkFrame(container, fg_color="transparent")
        left.pack(side="left")

        title = ctk.CTkLabel(
            left,
            text="H&A",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_PRIMARY
        )
        title.pack(side="left", padx=(0, 10))

        exchange_label = ctk.CTkLabel(
            left,
            text=exchange,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_SECONDARY
        )
        exchange_label.pack(side="left", padx=(0, 15))

        self.mode_switch = ctk.CTkSwitch(
            left,
            text="LIVE",
            width=60
        )
        self.mode_switch.pack(side="left")

        center = ctk.CTkFrame(container, fg_color="transparent")
        center.pack(side="left", padx=40)

        self.start_btn = ctk.CTkButton(
            center,
            text="START",
            width=70,
            height=28,
            fg_color=GREEN,
            command=self.controller.start
        )
        self.start_btn.pack(side="left", padx=4)

        self.drain_btn = ctk.CTkButton(
            center,
            text="DRAIN",
            width=70,
            height=28,
            fg_color=YELLOW,
            command=self.controller.stop
        )
        self.drain_btn.pack(side="left", padx=4)

        self.reset_btn = ctk.CTkButton(
            center,
            text="RESET",
            width=70,
            height=28,
            fg_color="#444c56",
            command=self.controller.finish_drain
        )
        self.reset_btn.pack(side="left", padx=4)

        self.lock_btn = ctk.CTkButton(
            center,
            text="LOCK",
            width=70,
            height=28,
            fg_color=RED,
            command=self.controller.lock
        )
        self.lock_btn.pack(side="left", padx=4)

        right = ctk.CTkFrame(container, fg_color="transparent")
        right.pack(side="right")

        self.api_button = ctk.CTkButton(
            right,
            text="API",
            width=60
        )
        self.api_button.pack(side="right")