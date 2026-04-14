class UIStateStore:
    def __init__(self):
        self._slots = {}

    def update(self, slot_state):
        self._slots[slot_state.slot_id] = slot_state

    def get(self, slot_id):
        return self._slots.get(slot_id)

    def all(self):
        return list(self._slots.values())
