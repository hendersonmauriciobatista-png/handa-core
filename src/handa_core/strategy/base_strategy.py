# =====================================================
# h_a/core/strategy/base_strategy.py
# Strategy Base – contrato oficial
# =====================================================

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any


class StrategyAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class StrategyDecision:
    """
    Resultado padronizado de uma Strategy.
    """

    def __init__(
        self,
        action: StrategyAction,
        confidence: float = 1.0,
        metadata: Dict[str, Any] | None = None,
    ):
        self.action = action
        self.confidence = confidence
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return (
            f"<StrategyDecision action={self.action} "
            f"confidence={self.confidence}>"
        )


class BaseStrategy(ABC):
    """
    Classe base abstrata para qualquer Strategy.

    Regras:
    - NÃO acessa UI
    - NÃO acessa exchange
    - NÃO altera estado diretamente
    - Apenas ANALISA e DECIDE
    """

    @abstractmethod
    def analyze(self, market_data: Dict[str, Any]) -> StrategyDecision:
        """
        Recebe dados de mercado e retorna uma decisão.

        market_data: dict genérico (price, volume, indicators, etc)
        """
        raise NotImplementedError
