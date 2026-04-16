# ============================================================
# core/alo/dynamic_core_models.py
# H&A — ALO Dynamic Core Models
# ============================================================

from dataclasses import dataclass, field
from typing import List


@dataclass
class AloDynamicMarketContext:
    market_state: str = ""
    liquidity_score: float = 0.0
    liquidity_label: str = ""
    opportunity_density: str = ""
    trend_strength: str = ""
    mqii_state: str = ""
    mqii_score: float = 0.0


@dataclass
class AloDynamicSetupContext:
    symbol: str = ""
    price: float = 0.0
    rsi: float = 0.0
    volume_ratio: float = 0.0
    trend: str = ""
    momentum: str = ""
    volume_state: str = ""
    setup_quality_label: str = ""
    setup_quality_score: float = 0.0
    market_score: float = 0.0


@dataclass
class AloDynamicProfileContext:
    status: str = ""
    confidence_score: float = 0.0
    total_events: int = 0
    execution_count: int = 0
    non_execution_count: int = 0
    structural_block_count: int = 0
    quality_filter_count: int = 0
    low_score_count: int = 0
    loss_count: int = 0
    win_count: int = 0
    block_bias: float = 0.0


@dataclass
class AloDynamicSystemContext:
    active_slots: int = 0
    max_slots: int = 4
    balance: float = 0.0
    loss_streak: int = 0
    win_rate_recent: float = 0.0
    drawdown_pct: float = 0.0


@dataclass
class AloDynamicCoreInput:
    symbol: str = ""
    market: AloDynamicMarketContext = field(default_factory=AloDynamicMarketContext)
    setup: AloDynamicSetupContext = field(default_factory=AloDynamicSetupContext)
    profile: AloDynamicProfileContext = field(default_factory=AloDynamicProfileContext)
    system: AloDynamicSystemContext = field(default_factory=AloDynamicSystemContext)


@dataclass
class AloDynamicCoreOutput:
    symbol: str = ""
    dynamic_mode: str = "BLOCK"
    confidence_score: float = 0.0
    confidence_label: str = "MUITO_BAIXA"
    risk_weight: float = 1.0
    override_permission: bool = False
    block_reason: str = ""
    reasons: List[str] = field(default_factory=list)