from typing import Dict, Any
from h_a.core.exchange_adapter.base_adapter import ExchangeAdapter


class MockAdapter(ExchangeAdapter):
    def send_order(self, order_payload: Dict[str, Any]) -> Dict[str, Any]:
        # Simula execução perfeita
        return {
            "status": "EXECUTED",
            "exchange_order_id": "MOCK-123",
            "executed_price": 100.0,
            "executed_qty": order_payload.get("quantity", 0),
            "exchange_timestamp": 0
        }
