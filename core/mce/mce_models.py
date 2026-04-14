# ============================================================
# MCE MODELS
# ============================================================

from enum import Enum
from dataclasses import dataclass


class MCEStatus(Enum):
    IDLE = "IDLE"
    ARMED = "ARMED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


@dataclass
class MCECandidate:
    symbol: str
    reference_price: float
    reference_volume_ratio: float
    reference_rsi: float
    armed_cycle: int
    status: MCEStatus = MCEStatus.ARMED