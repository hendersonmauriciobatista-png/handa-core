from enum import Enum, auto


class SystemMode(Enum):
    MOCK = auto()
    LIVE = auto()


class ConnectionState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()


class AnalysisState(Enum):
    IDLE = auto()
    ANALYSING = auto()
    SIGNAL_FOUND = auto()
    REJECTED = auto()
    FINALIZED = auto()


class TradingState(Enum):
    WAITING_ANALYSIS = auto()
    READY = auto()
    RUNNING = auto()
    COMPLETED = auto()
    ABORTED = auto()
