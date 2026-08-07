import customtkinter as ctk

TEXT_PRIMARY = "#e8e8e8"
TEXT_SECONDARY = "#8b949e"

GREEN = "#2ea043"
YELLOW = "#d29922"
RED = "#da3633"


class SlotCard(ctk.CTkFrame):

    def __init__(self, parent, slot_id):
        super().__init__(parent, fg_color="#252a31", corner_radius=12)

        self.slot_id = slot_id

        title = ctk.CTkLabel(
            self,
            text=f"SLOT {slot_id}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_PRIMARY
        )
        title.pack(pady=(12, 6))

        self.pair_label = ctk.CTkLabel(
            self,
            text="---",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_PRIMARY
        )
        self.pair_label.pack()

        self.state_label = ctk.CTkLabel(
            self,
            text="IDLE",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_SECONDARY
        )
        self.state_label.pack()

        self.str_label = ctk.CTkLabel(
            self,
            text="STR 0%",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_SECONDARY
        )
        self.str_label.pack(pady=(0, 10))

    def update_slot(self, pair, state, strength):

        self.pair_label.configure(text=pair)

        state_color = TEXT_SECONDARY

        if state == "ANALYZING":
            state_color = YELLOW
        elif state == "TRADING":
            state_color = GREEN
        elif state == "EXIT":
            state_color = RED

        self.state_label.configure(
            text=state,
            text_color=state_color
        )

        self.str_label.configure(text=f"STR {strength}%")