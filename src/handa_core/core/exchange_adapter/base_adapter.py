from abc import ABC, abstractmethod
from typing import Dict, Any


class ExchangeAdapter(ABC):
    """
    Interface base para qualquer exchange.
    O ExecutorLive conversa SOMENTE com esta interface.
    """

    @abstractmethod
    def send_order(self, order_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envia uma ordem MARKET para a exchange.

        Deve SEMPRE retornar:
        - status: EXECUTED | FAILED
        - demais campos padronizados

        Nunca pode retornar silêncio.
        """
        pass
