from enum import Enum


class SlotState(Enum):
    IDLE = "IDLE"
    ANALYZING = "ANALYZING"
    ARMED = "ARMED"
    TRADING = "TRADING"
    COOLDOWN = "COOLDOWN"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


class TradingMode(Enum):
    NORMAL = "NORMAL"
    PROTECTING = "PROTECTING"
    EXITING = "EXITING"


class CooldownType(Enum):
    DEFENSIVE = "DEFENSIVE"
    NEUTRAL = "NEUTRAL"
    STRUCTURAL = "STRUCTURAL"
