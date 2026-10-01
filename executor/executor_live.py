# ============================================================
# executor/executor_live.py
# Executor LIVE v2.0
# Fluxo BUY por quoteOrderQty + SELL automático com ajuste LOT_SIZE
# ============================================================

from datetime import datetime
from math import floor
from binance.client import Client
from binance.exceptions import BinanceAPIException
from core.execution_boundary import is_bound_live_capability
from core.execution.execution_fact import ExecutionFact, normalize_external_execution

def format_buy_telegram(pair: str, entry: float, capital: float) -> str:
    return (
        f"BUY | {pair}\n"
        f"{entry:.8f} | {capital:.2f} USDC"
    )

class ExecutorLive:

    def __init__(self, client: Client, notifier=None, live_capability=None):
        if client is None:
            raise ValueError("Client Binance não pode ser None.")
        if not is_bound_live_capability(live_capability, client):
            raise RuntimeError(
                "ExecutorLive exige capability LIVE vinculada ao client emitido pela fronteira institucional"
            )
        self._client = client
        self.exchange = "BINANCE_SPOT"
        self.notifier = notifier

    # --------------------------------------------------------
    # MARKET BUY POR VALOR (USDC)
    # --------------------------------------------------------

    def place_market_buy_quote(self, symbol: str, quote_amount: float) -> ExecutionFact:

        try:
            order = self._client.create_order(
                symbol=symbol,
                side="BUY",
                type="MARKET",
                quoteOrderQty=quote_amount
            )

            if self.notifier and order.get("status") == "FILLED":
                fills = order.get("fills", [])
                total_cost = sum(float(f["price"]) * float(f["qty"]) for f in fills)
                total_qty = sum(float(f["qty"]) for f in fills)
                avg_price = total_cost / total_qty if total_qty > 0 else 0.0
                msg = format_buy_telegram(
                    pair=symbol,
                    entry=avg_price,
                    capital=quote_amount,
                )
                self.notifier.send(msg)

            return normalize_external_execution(
                order,
                symbol=symbol,
                side="BUY",
                rawSourceReference=self.exchange,
            )

        except BinanceAPIException as e:
            return normalize_external_execution(
                {
                    "symbol": symbol,
                    "side": "BUY",
                    "ambiguous_response": True,
                    "rawSourceReference": f"{self.exchange}:binance-api:{e.code}",
                }
            )

        except Exception as e:
            return normalize_external_execution(
                {
                    "symbol": symbol,
                    "side": "BUY",
                    "ambiguous_response": True,
                    "rawSourceReference": f"{self.exchange}:exception:{type(e).__name__}",
                }
            )

    # --------------------------------------------------------
    # MARKET SELL AJUSTANDO LOT_SIZE
    # --------------------------------------------------------

    def place_market_sell_all(self, symbol: str) -> ExecutionFact:

        try:
            asset = symbol.replace("USDC", "")
            balance = self._client.get_asset_balance(asset=asset)

            if not balance:
                return normalize_external_execution(
                    {"symbol": symbol, "side": "SELL", "rawSourceReference": "balance-not-found"}
                )

            free_qty = float(balance["free"])

            # Buscar stepSize
            info = self._client.get_symbol_info(symbol)
            step_size = None

            for f in info["filters"]:
                if f["filterType"] == "LOT_SIZE":
                    step_size = float(f["stepSize"])
                    break

            if step_size is None:
                return normalize_external_execution(
                    {"symbol": symbol, "side": "SELL", "rawSourceReference": "lot-size-not-found"}
                )

            qty = floor(free_qty / step_size) * step_size

            if qty <= 0:
                return normalize_external_execution(
                    {"symbol": symbol, "side": "SELL", "rawSourceReference": "invalid-quantity"}
                )

            order = self._client.create_order(
                symbol=symbol,
                side="SELL",
                type="MARKET",
                quantity=qty
            )

            return normalize_external_execution(
                order,
                symbol=symbol,
                side="SELL",
                rawSourceReference=self.exchange,
            )

        except BinanceAPIException as e:
            return normalize_external_execution(
                {
                    "symbol": symbol,
                    "side": "SELL",
                    "ambiguous_response": True,
                    "rawSourceReference": f"{self.exchange}:binance-api:{e.code}",
                }
            )

        except Exception as e:
            return normalize_external_execution(
                {
                    "symbol": symbol,
                    "side": "SELL",
                    "ambiguous_response": True,
                    "rawSourceReference": f"{self.exchange}:exception:{type(e).__name__}",
                }
            )
