# ============================================================
# core/execution/execution_plan.py
# Plano de execução de ordens do sistema H&A
# ============================================================


class ExecutionPlan:
    """
    Representa um plano de execução de trade.

    Esse objeto padroniza as ordens antes de chegar ao Executor.
    """

    VALID_SIDES = {"BUY", "SELL"}

    def __init__(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float | None = None,
        reason: str = "UNSPECIFIED"
    ):

        if not symbol:
            raise ValueError("INVALID_SYMBOL")

        if side not in self.VALID_SIDES:
            raise ValueError("INVALID_SIDE")

        if quantity <= 0:
            raise ValueError("INVALID_QUANTITY")

        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.reason = reason

    # --------------------------------------------------------
    # REPRESENTAÇÃO
    # --------------------------------------------------------

    def __repr__(self):

        return (
            f"ExecutionPlan("
            f"symbol={self.symbol}, "
            f"side={self.side}, "
            f"quantity={self.quantity}, "
            f"price={self.price}, "
            f"reason={self.reason})"
        )

    # --------------------------------------------------------
    # SERIALIZAÇÃO
    # --------------------------------------------------------

    def to_dict(self):

        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "reason": self.reason
        }