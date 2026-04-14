import time

class UILoop:

    def __init__(self, adapter, slots, interval=1.0):
        self.adapter = adapter
        self.slots = slots
        self.interval = interval
        self.running = True

    def start(self):
        while self.running:
            self.adapter.sync(self.slots)
            time.sleep(self.interval)
