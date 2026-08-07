from core.lc1.lc1_schema import build_buy_event, build_sell_event
from core.lc1.lc1_writer import LC1Writer


class LC1Logger:

    def __init__(self):
        self.writer = LC1Writer()

    def log_buy(self, data: dict):
        event = build_buy_event(data)
        self.writer.write(event)

    def log_sell(self, data: dict):
        event = build_sell_event(data)
        self.writer.write(event)