class SlotRegistry:
    def __init__(self):
        self._slots = {}

    def update(self, slots_state: list):
        if len(slots_state) != 12:
            raise ValueError(f"Slots incompletos: {len(slots_state)}/12")

        self._slots = {slot["slot_id"]: slot for slot in slots_state}

    def get_all(self):
        return list(self._slots.values())

    def get(self, slot_id: str):
        return self._slots.get(slot_id)
