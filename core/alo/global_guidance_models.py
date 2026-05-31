from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class MacroLeaderSnapshot:
    symbol: str
    trend: str = "UNKNOWN"
    momentum: str = "UNKNOWN"
    market_state: str = "UNKNOWN"
    volume_ratio: float = 0.0


@dataclass(frozen=True)
class ALOGlobalGuidance:
    symbol: str
    cycle_id: str
    timestamp: str
    source: str = "ALO_GLOBAL_GUIDANCE"
    mode: str = "READ_ONLY"
    operational_effect_count: int = 0

    guidance: str = "NEUTRAL"
    confidence_score: float = 0.0
    confidence_label: str = "UNKNOWN"
    reason_codes: Tuple[str, ...] = field(default_factory=tuple)
    explainability: str = ""

    macro_alignment: float = 0.0
    macro_state: str = "UNKNOWN"
    macro_mode: str = "PASSIVE_OBSERVER"

    btc_trend: str = "UNKNOWN"
    eth_trend: str = "UNKNOWN"
    bnb_trend: str = "UNKNOWN"
    btc_momentum: str = "UNKNOWN"
    eth_momentum: str = "UNKNOWN"
    bnb_momentum: str = "UNKNOWN"
    btc_market_state: str = "UNKNOWN"
    eth_market_state: str = "UNKNOWN"
    bnb_market_state: str = "UNKNOWN"
    btc_volume_ratio: float = 0.0
    eth_volume_ratio: float = 0.0
    bnb_volume_ratio: float = 0.0

    macro_reason_codes: Tuple[str, ...] = field(default_factory=tuple)
    macro_explainability: str = ""
