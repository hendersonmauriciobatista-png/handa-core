from enum import Enum, auto


class AnalysisState(Enum):
    ANALYSIS_IDLE = auto()
    ANALYSIS_RUNNING = auto()
    ANALYSIS_FINALIZED = auto()


class TradingState(Enum):
    TRADING_WAITING_ANALYSIS = auto()
    TRADING_RUNNING = auto()
    TRADING_FINISHED = auto()

