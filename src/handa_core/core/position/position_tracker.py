# ============================================================
# core/position/position_tracker.py
# Rastreamento de posição aberta
# ============================================================


class PositionTracker:

    def __init__(self):

        self.symbol = None
        self.entry_price = None
        self.quantity = None
        self.active = False

    # ---------------------------------------------------------
    # Registrar entrada
    # ---------------------------------------------------------

    def open_position(self, symbol, entry_price, quantity):

        self.symbol = symbol
        self.entry_price = entry_price
        self.quantity = quantity
        self.active = True

    # ---------------------------------------------------------
    # Fechar posição
    # ---------------------------------------------------------

    def close_position(self):

        self.symbol = None
        self.entry_price = None
        self.quantity = None
        self.active = False

    # ---------------------------------------------------------
    # Calcular PnL
    # ---------------------------------------------------------

    def calculate_pnl(self, current_price):

        if not self.active:
            return 0.0

        pnl = (current_price - self.entry_price) * self.quantity

        return pnl

    # ---------------------------------------------------------
    # Calcular PnL %
    # ---------------------------------------------------------

    def calculate_pnl_percent(self, current_price):

        if not self.active:
            return 0.0

        pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100

        return pnl_percent