# ============================================================
# executor/executor_live.py
# Executor LIVE v2.0
# Fluxo BUY por quoteOrderQty + SELL automático com ajuste LOT_SIZE
# ============================================================

from datetime import datetime
from typing import Dict, Any
from math import floor
from binance.client import Client
from binance.exceptions import BinanceAPIException

def format_buy_telegram(pair: str, entry: float, capital: float) -> str:
    return (
        f"BUY | {pair}\n"
        f"{entry:.8f} | {capital:.2f} USDC"
    )

class ExecutorLive:

    def __init__(self, client: Client, notifier=None):
        if client is None:
            raise ValueError("Client Binance não pode ser None.")
        self._client = client
        self.exchange = "BINANCE_SPOT"
        self.notifier = notifier

    # --------------------------------------------------------
    # MARKET BUY POR VALOR (USDC)
    # --------------------------------------------------------

    def place_market_buy_quote(self, symbol: str, quote_amount: float) -> Dict[str, Any]:

        timestamp = datetime.utcnow().isoformat()

        try:
            order = self._client.create_order(
                symbol=symbol,
                side="BUY",
                type="MARKET",
                quoteOrderQty=quote_amount
            )

            executed_qty = float(order.get("executedQty", 0))
            fills = order.get("fills", [])

            avg_price = 0.0
            if fills:
                total_cost = sum(float(f["price"]) * float(f["qty"]) for f in fills)
                total_qty = sum(float(f["qty"]) for f in fills)
                if total_qty > 0:
                    avg_price = total_cost / total_qty

            if self.notifier and order.get("status") == "FILLED":
                msg = format_buy_telegram(
                    pair=symbol,
                    entry=avg_price,
                    capital=quote_amount,
                )
                self.notifier.send(msg)

            return {
                "exchange": self.exchange,
                "symbol": symbol,
                "side": "BUY",
                "status": order.get("status"),
                "executed_qty": executed_qty,
                "avg_price": avg_price,
                "order_id": order.get("orderId"),
                "timestamp": timestamp
            }

        except BinanceAPIException as e:
            return {
                "status": "ERROR",
                "error_code": e.code,
                "error_msg": e.message
            }

        except Exception as e:
            return {
                "status": "ERROR",
                "error_msg": str(e)
            }

    # --------------------------------------------------------
    # MARKET SELL AJUSTANDO LOT_SIZE
    # --------------------------------------------------------

    def place_market_sell_all(self, symbol: str) -> Dict[str, Any]:

        timestamp = datetime.utcnow().isoformat()

        try:
            asset = symbol.replace("USDC", "")
            balance = self._client.get_asset_balance(asset=asset)

            if not balance:
                return {"status": "ERROR", "error_msg": "Saldo não encontrado"}

            free_qty = float(balance["free"])

            # Buscar stepSize
            info = self._client.get_symbol_info(symbol)
            step_size = None

            for f in info["filters"]:
                if f["filterType"] == "LOT_SIZE":
                    step_size = float(f["stepSize"])
                    break

            if step_size is None:
                return {"status": "ERROR", "error_msg": "LOT_SIZE não encontrado"}

            qty = floor(free_qty / step_size) * step_size

            if qty <= 0:
                return {"status": "ERROR", "error_msg": "Quantidade inválida após ajuste"}

            order = self._client.create_order(
                symbol=symbol,
                side="SELL",
                type="MARKET",
                quantity=qty
            )

            return {
                "exchange": self.exchange,
                "symbol": symbol,
                "side": "SELL",
                "status": order.get("status"),
                "executed_qty": float(order.get("executedQty", 0)),
                "order_id": order.get("orderId"),
                "timestamp": timestamp
            }

        except BinanceAPIException as e:
            return {
                "status": "ERROR",
                "error_code": e.code,
                "error_msg": e.message
            }

        except Exception as e:
            return {
                "status": "ERROR",
                "error_msg": str(e)
            }