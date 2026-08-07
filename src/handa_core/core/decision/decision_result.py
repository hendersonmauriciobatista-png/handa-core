# ============================================================
# H&A - Decision Result
# Representa o resultado da análise da PolicyLayer
# ============================================================

from dataclasses import dataclass
from enum import Enum


class DecisionAction(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    BLOCK = "BLOCK"


@dataclass
class DecisionResult:

    action: DecisionAction
    reason: str
    confidence: float = 1.0

    def is_buy(self) -> bool:
        return self.action == DecisionAction.BUY

    def is_sell(self) -> bool:
        return self.action == DecisionAction.SELL

    def is_hold(self) -> bool:
        return self.action == DecisionAction.HOLD

    def is_block(self) -> bool:
        return self.action == DecisionAction.BLOCK
    
    # ============================================================
# H&A - Decision Result
# Representa o resultado da análise da PolicyLayer
# ============================================================

from dataclasses import dataclass
from enum import Enum


class DecisionAction(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    BLOCK = "BLOCK"


@dataclass
class DecisionResult:

    action: DecisionAction
    reason: str
    confidence: float = 1.0

    def is_buy(self) -> bool:
        return self.action == DecisionAction.BUY

    def is_sell(self) -> bool:
        return self.action == DecisionAction.SELL

    def is_hold(self) -> bool:
        return self.action == DecisionAction.HOLD

    def is_block(self) -> bool:
        return self.action == DecisionAction.BLOCK