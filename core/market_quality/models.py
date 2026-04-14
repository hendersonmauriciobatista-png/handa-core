# ============================================================
# core/market_quality/models.py
# MQII — Market Quality Internal Indicator
# Modelos oficiais v1.0
# ============================================================

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict


# ============================================================
# HELPERS
# ============================================================


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# AGGREGATE
# ============================================================


@dataclass
class MarketQualityAggregate:
    total_assets: int = 0
    uptrend_count: int = 0
    bullish_momentum_count: int = 0
    bearish_count: int = 0
    high_volume_count: int = 0
    neutral_momentum_count: int = 0
    refined_count: int = 0
    approved_count: int = 0
    structural_block_count: int = 0

    avg_volume_ratio: float = 0.0
    avg_market_score: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


# ============================================================
# SNAPSHOT
# ============================================================


@dataclass
class MarketQualitySnapshot:
    state: str = "UNKNOWN"
    label: str = "SEM DADOS"
    score: float = 0.0
    message: str = "Sem dados suficientes."

    total_assets: int = 0
    uptrend_count: int = 0
    bullish_momentum_count: int = 0
    bearish_count: int = 0
    high_volume_count: int = 0
    neutral_momentum_count: int = 0
    refined_count: int = 0
    approved_count: int = 0
    structural_block_count: int = 0

    avg_volume_ratio: float = 0.0
    avg_market_score: float = 0.0

    components: Dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> Dict:
        return asdict(self)
