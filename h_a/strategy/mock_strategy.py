# =====================================================
# h_a/core/strategy/mock_strategy.py
# Strategy simples para testes
# =====================================================

from .base_strategy import (
    BaseStrategy,
    StrategyDecision,
    StrategyAction,
)


class MockStrategy(BaseStrategy):
    """
    Strategy de teste:
    - Sempre retorna BUY
    """

    def analyze(self, market_data):
        return StrategyDecision(
            action=StrategyAction.BUY,
            confidence=0.5,
            metadata={"source": "mock"},
        )
