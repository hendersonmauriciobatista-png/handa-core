import random
import time


class Strategy:

    def __init__(self):
        self.price_history = []
        self.last_signal_time = 0
        self.cooldown = 5

    def update_price(self, price):
        self.price_history.append(price)

        if len(self.price_history) > 200:
            self.price_history.pop(0)

    def signal(self):
        now = time.time()

        if now - self.last_signal_time < self.cooldown:
            return False

        decision = random.random() < 0.2

        if decision:
            self.last_signal_time = now

        return decision

    def exit_signal(self):
        return random.random() < 0.1
