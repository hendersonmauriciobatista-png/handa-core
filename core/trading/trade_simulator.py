import random
import time
from dataclasses import dataclass


@dataclass
class TradeResult:
    entry_price: float
    exit_price: float
    pnl_pct: float
    outcome: str   # TP | SL | TIMEOUT
    duration_sec: float


class TradeSimulator:
    """
    Simula um trade com TP / SL / TIMEOUT
    """

    def __init__(
        self,
        tp_pct: float = 0.01,     # +1%
        sl_pct: float = 0.005,    # -0.5%
        timeout_sec: int = 5
    ):
        self.tp_pct = tp_pct
        self.sl_pct = sl_pct
        self.timeout_sec = timeout_sec

    def run(self) -> TradeResult:
        entry_price = round(random.uniform(90, 110), 2)
        price = entry_price

        tp_price = entry_price * (1 + self.tp_pct)
        sl_price = entry_price * (1 - self.sl_pct)

        start = time.time()

        while True:
            # Simula movimento de preço
            price *= random.uniform(0.998, 1.002)

            # Take Profit
            if price >= tp_price:
                return TradeResult(
                    entry_price=entry_price,
                    exit_price=round(price, 2),
                    pnl_pct=round((price - entry_price) / entry_price * 100, 2),
                    outcome="TP",
                    duration_sec=round(time.time() - start, 2)
                )

            # Stop Loss
            if price <= sl_price:
                return TradeResult(
                    entry_price=entry_price,
                    exit_price=round(price, 2),
                    pnl_pct=round((price - entry_price) / entry_price * 100, 2),
                    outcome="SL",
                    duration_sec=round(time.time() - start, 2)
                )

            # Timeout
            if time.time() - start >= self.timeout_sec:
                return TradeResult(
                    entry_price=entry_price,
                    exit_price=round(price, 2),
                    pnl_pct=round((price - entry_price) / entry_price * 100, 2),
                    outcome="TIMEOUT",
                    duration_sec=round(time.time() - start, 2)
                )
