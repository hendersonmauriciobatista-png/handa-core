from enum import Enum
from dataclasses import dataclass
from typing import Optional

class SlotStatus(str, Enum):
    IDLE = "IDLE"
    TRADING = "TRADING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"

@dataclass
class SlotUIState:
    slot_id: str
    status: SlotStatus
    symbol: Optional[str] = None
    last_event: Optional[str] = None
    error: Optional[str] = None
