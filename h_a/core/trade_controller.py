class TradeController:

    def __init__(self):
        self.position_open = False
        self.entry_price = 0.0
        self.quantity = 0.0
        self.current_price = 0.0
        self.pnl = 0.0

    def open_position(self, symbol):
        success = True

        if success:
            self.position_open = True
            self.entry_price = self.current_price
            self.quantity = 1.0
            return True

        return False

    def close_position(self):
        if not self.position_open:
            return False

        success = True

        if success:
            self.calculate_pnl()
            self.reset()
            return True

        return False

    def update_price(self, price):
        self.current_price = price
        if self.position_open:
            self.calculate_pnl()

    def calculate_pnl(self):
        self.pnl = (self.current_price - self.entry_price) * self.quantity

    def get_pnl(self):
        return self.pnl

    def reset(self):
        self.position_open = False
        self.entry_price = 0.0
        self.quantity = 0.0
        self.pnl = 0.0
