# ============================================================
# core/learning/models.py
# LC-3 — Shadow Learning Analyzer
# Modelos oficiais v1.0
# ============================================================

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List


# ============================================================
# HELPERS
# ============================================================


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# TRADE SAMPLE
# ============================================================


@dataclass
class TradeLearningSample:
    symbol: str = ""

    entry_price: float = 0.0
    exit_price: float = 0.0

    pnl_usdc: float = 0.0
    pnl_pct: float = 0.0
    duration_seconds: int = 0

    close_reason: str = ""
    opened_at: str = ""
    closed_at: str = ""

    is_win: bool = False
    is_loss: bool = False

    context: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


# ============================================================
# PATTERN STATS
# ============================================================


@dataclass
class PatternStats:
    pattern_key: str = ""

    total_trades: int = 0
    wins: int = 0
    losses: int = 0

    win_rate: float = 0.0
    avg_pnl_usdc: float = 0.0
    avg_pnl_pct: float = 0.0
    avg_duration_seconds: float = 0.0

    samples: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


# ============================================================
# SHADOW ANALYSIS REPORT
# ============================================================


@dataclass
class ShadowAnalysisReport:
    generated_at: str = field(default_factory=_utc_now_iso)

    total_samples: int = 0
    total_patterns: int = 0

    wins: int = 0
    losses: int = 0
    overall_win_rate: float = 0.0
    overall_avg_pnl_usdc: float = 0.0
    overall_avg_pnl_pct: float = 0.0

    best_patterns: List[Dict] = field(default_factory=list)
    worst_patterns: List[Dict] = field(default_factory=list)

    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)
