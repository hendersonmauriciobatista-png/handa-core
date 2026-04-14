import queue


class UIController:

    def __init__(self, event_bridge):
        self.slot_cards = {}
        self.event_queue = queue.Queue()

        event_bridge.subscribe("slot_update", self.enqueue_event)

    def enqueue_event(self, payload):
        self.event_queue.put(payload)

    def process_events(self):
        while not self.event_queue.empty():
            payload = self.event_queue.get()
            self.apply_update(payload)

    def apply_update(self, payload):
        slot_id = payload["slot_id"]
        card = self.slot_cards.get(slot_id)

        if card:
            card.update_state(payload)
