from h_a.core.slot import Slot


class EngineMock:
    """
    Engine mínimo para orquestrar Slots.
    Não decide, não dorme, não loopa.
    """

    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.slots = {}

    def create_slot(self, slot_id: int) -> Slot:
        slot = Slot(slot_id=slot_id, event_bus=self.event_bus)
        self.slots[slot_id] = slot
        return slot

    def tick(self):
        for slot in self.slots.values():
            slot.step()

    def tick_n(self, n: int):
        for _ in range(n):
            self.tick()
