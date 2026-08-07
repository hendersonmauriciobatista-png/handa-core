class UIState:
    def __init__(self):
        self.active_slot_id = None

    def set_active_slot(self, slot_id: str):
        self.active_slot_id = slot_id
