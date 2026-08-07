from typing import Dict, Any
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException

from h_a.core.exchange_adapter.base_adapter import ExchangeAdapter


class BinanceSpotAdapter(ExchangeAdapter):
    """
    Adapter concreto para Binance Spot.
    NÃO possui inteligência.
    NÃO faz retry.
    NÃO corrige erro.
    """

    def __init__(self, api_key: str, api_secret: str):
        self.client = Client(api_key, api_secret)

    def send_order(self, order_payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = self.client.create_order(
                symbol=order_payload["symbol"],
                side=order_payload["side"],
                type="MARKET",
                quantity=order_payload["quantity"]
            )

            return {
                "status": "EXECUTED",
                "exchange_order_id": response.get("orderId"),
                "executed_price": self._extract_price(response),
                "executed_qty": float(response.get("executedQty", 0)),
                "exchange_timestamp": response.get("transactTime")
            }

        except (BinanceAPIException, BinanceOrderException) as e:
            return {
                "status": "FAILED",
                "error_code": getattr(e, "code", "BINANCE_ERROR"),
                "error_message": str(e),
                "exchange_timestamp": None
            }

        except Exception as e:
            return {
                "status": "FAILED",
                "error_code": "UNEXPECTED_ERROR",
                "error_message": str(e),
                "exchange_timestamp": None
            }

    @staticmethod
    def _extract_price(response: Dict[str, Any]) -> float:
        fills = response.get("fills", [])
        if not fills:
            return 0.0
        return float(fills[0].get("price", 0))
