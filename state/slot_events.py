from enum import Enum, auto


class SlotEvent(Enum):
    EV_ANALYSIS_START = auto()
    EV_ANALYSIS_SCORE_UPDATE = auto()
    EV_ANALYSIS_APPROVED = auto()

    EV_TRADING_START = auto()
    EV_TRADING_FINISH = auto()

    EV_RESET_PAIR = auto()
