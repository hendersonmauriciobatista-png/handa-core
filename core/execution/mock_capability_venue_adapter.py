"""Capability-neutral BUY adapter for the durable MOCK transport proof."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from core.execution.execution_fact import ExecutionFact, ExternalOrderStatus, normalize_external_execution


class MockVenueRejected(RuntimeError):
    """A typed MOCK rejection that proves no simulated venue effect."""


class MockCapabilityVenueAdapter:
    """Translate exact transport fields into the narrow MOCK venue primitive."""

    def __init__(self, executor):
        self._executor = executor

    def submit_buy(
        self,
        *,
        symbol: str,
        requested_quote_amount: Decimal,
        client_order_id: str,
    ) -> ExecutionFact:
        if not isinstance(requested_quote_amount, Decimal):
            raise TypeError("requested_quote_amount must be Decimal")
        if not requested_quote_amount.is_finite() or requested_quote_amount <= 0:
            raise ValueError("requested_quote_amount must be positive and finite")
        return self._executor.execute_authorized_buy(
            symbol=symbol,
            requested_quote_amount=requested_quote_amount,
            client_order_id=client_order_id,
        )

    def recover_by_client_order_id(
        self, client_order_id: str
    ) -> Optional[ExecutionFact]:
        order = self._executor.get_order_by_client_order_id(client_order_id)
        if order is None:
            return None
        return normalize_external_execution(order)


__all__ = ["MockCapabilityVenueAdapter", "MockVenueRejected"]
