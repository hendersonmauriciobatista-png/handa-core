"""Transport/recovery adapter for the simulated MOCK venue.

This module deliberately does not authorize effects or apply positions.  It
only requires a caller-supplied client identity, delegates one submission to
MockExecutor, and normalizes durable venue evidence during recovery.
"""

from core.execution.execution_fact import ExecutionFact, normalize_external_execution


class GovernedMockSubmissionGateway:
    """Narrow MOCK submission and read-only recovery boundary."""

    def __init__(self, executor):
        self.executor = executor

    @staticmethod
    def _required_client_order_id(client_order_id):
        if not isinstance(client_order_id, str) or not client_order_id.strip():
            raise ValueError("client_order_id must be non-empty")
        return client_order_id.strip()

    def submit_buy(self, signal, *, client_order_id: str) -> ExecutionFact:
        client_order_id = self._required_client_order_id(client_order_id)
        return self.executor.execute_buy(
            signal,
            client_order_id=client_order_id,
        )

    def recover_by_client_order_id(self, client_order_id: str):
        client_order_id = self._required_client_order_id(client_order_id)
        evidence = self.executor.get_order_by_client_order_id(client_order_id)
        return (
            normalize_external_execution(evidence)
            if evidence is not None
            else None
        )

    def recover_by_external_order_id(self, external_order_id: str):
        if not isinstance(external_order_id, str) or not external_order_id.strip():
            raise ValueError("external_order_id must be non-empty")
        evidence = self.executor.get_order_by_external_order_id(external_order_id)
        return (
            normalize_external_execution(evidence)
            if evidence is not None
            else None
        )


__all__ = ["GovernedMockSubmissionGateway"]
