class DummyExecutor:
    def has_open_position(self):
        return False

    def buy(self, symbol, quantity, price):
        return {"status": "ok"}

    def sell(self, price):
        return {"status": "ok"}
