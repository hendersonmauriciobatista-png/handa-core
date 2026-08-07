from abc import ABC, abstractmethod
from enum import Enum, auto


class StrategyDecision(Enum):
    ANALYZING = auto()
    ENTERING = auto()
    TRADING = auto()
    IDLE = auto()


class StrategyAction(Enum):
    NONE = auto()
    ENTER = auto()
    EXIT = auto()


class BaseStrategy(ABC):

    @abstractmethod
    def decide(self, market_data=None) -> StrategyDecision:
        pass

    @abstractmethod
    def action(self) -> StrategyAction:
        pass
