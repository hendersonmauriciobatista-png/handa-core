import customtkinter as ctk

from interface.components.slot_card import SlotCard


class SlotsPanel(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        self.grid_rowconfigure((0, 1), weight=1)
        self.grid_columnconfigure((0, 1), weight=1)

        self.slots = {}

        slot_id = 1

        for row in range(2):
            for col in range(2):

                slot = SlotCard(self, slot_id)

                slot.grid(
                    row=row,
                    column=col,
                    padx=15,
                    pady=15,
                    sticky="nsew"
                )

                self.slots[slot_id] = slot

                slot_id += 1

    def update_slot(self, slot_id, pair, state, strength):

        slot = self.slots.get(slot_id)

        if not slot:
            return

        slot.update_slot(pair, state, strength)