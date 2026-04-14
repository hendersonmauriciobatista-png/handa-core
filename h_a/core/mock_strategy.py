import itertools
from .base_strategy import (
    BaseStrategy,
    StrategyDecision,
    StrategyAction,
)


class MockStrategy(BaseStrategy):

    def __init__(self):
        self._cycle = itertools.cycle([
            StrategyDecision.ANALYZING,
            StrategyDecision.ENTERING,
            StrategyDecision.TRADING,
            StrategyDecision.IDLE,
        ])

    def decide(self, market_data=None) -> StrategyDecision:
        return next(self._cycle)

    def action(self) -> StrategyAction:
        return StrategyAction.NONE
