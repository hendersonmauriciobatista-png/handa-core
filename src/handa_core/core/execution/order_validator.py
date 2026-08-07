# ============================================================
# core/execution/order_validator.py
# Validação de ordens Binance (LOT_SIZE / MIN_NOTIONAL)
# ============================================================

import math


class OrderValidator:

    def __init__(self, client):
        self.client = client
        self.symbol_filters = {}

    # --------------------------------------------------------
    # CARREGAR FILTROS DO PAR
    # --------------------------------------------------------

    def load_symbol_filters(self, symbol):

        if symbol in self.symbol_filters:
            return self.symbol_filters[symbol]

        info = self.client.get_symbol_info(symbol)

        filters = {}

        for f in info["filters"]:

            if f["filterType"] == "LOT_SIZE":
                filters["min_qty"] = float(f["minQty"])
                filters["step_size"] = float(f["stepSize"])

            if f["filterType"] == "MIN_NOTIONAL":
                filters["min_notional"] = float(f["minNotional"])

        self.symbol_filters[symbol] = filters

        return filters

    # --------------------------------------------------------
    # AJUSTAR QUANTIDADE
    # --------------------------------------------------------

    def adjust_quantity(self, symbol, quantity, price):

        filters = self.load_symbol_filters(symbol)

        step = filters["step_size"]
        min_qty = filters["min_qty"]
        min_notional = filters["min_notional"]

        quantity = math.floor(quantity / step) * step

        if quantity < min_qty:
            quantity = min_qty

        if quantity * price < min_notional:
            quantity = min_notional / price

        return float(quantity)