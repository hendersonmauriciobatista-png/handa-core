import tkinter as tk
from .slot_card import SlotCard

class SlotsGrid(tk.Frame):
    def __init__(self, master, registry, ui_state):
        super().__init__(master)
        self.registry = registry
        self.ui_state = ui_state
        self.cards = {}

    def render(self):
        slots = self.registry.get_all()

        for idx, slot in enumerate(slots):
            slot_id = slot["slot_id"]

            if slot_id not in self.cards:
                card = SlotCard(
                    self,
                    slot,
                    on_select=self.ui_state.set_active_slot
                )
                card.grid(
                    row=idx // 2,
                    column=idx % 2,
                    sticky="nsew",
                    padx=4,
                    pady=4
                )
                self.cards[slot_id] = card
            else:
                # atualização SEM recriar
                self.cards[slot_id].update(slot)
