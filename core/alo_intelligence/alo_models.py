# =============================================================================
# core/alo_intelligence/alo_models.py
# H&A — ALO Intelligent Core Models
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# =============================================================================
# ENUMS
# =============================================================================

class ConfidenceLevel(str, Enum):
    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"


class GuidanceType(str, Enum):
    ALLOW = "ALLOW"
    ALLOW_WITH_CAUTION = "ALLOW_WITH_CAUTION"
    REQUIRE_STRONGER_CONFIRMATION = "REQUIRE_STRONGER_CONFIRMATION"
    TEMPORARY_BLOCK = "TEMPORARY_BLOCK"
    HARD_BLOCK = "HARD_BLOCK"


class ReentryState(str, Enum):
    CLEAN = "CLEAN"
    CAUTION = "CAUTION"
    RESTRICTED = "RESTRICTED"
    TEMP_BLOCK = "TEMP_BLOCK"
    HARD_BLOCK = "HARD_BLOCK"


class RiskBias(str, Enum):
    NORMAL = "NORMAL"
    CONSERVATIVE = "CONSERVATIVE"
    VERY_CONSERVATIVE = "VERY_CONSERVATIVE"
    OPPORTUNITY_FAVORABLE = "OPPORTUNITY_FAVORABLE"


class RankingBias(str, Enum):
    BOOST = "BOOST"
    KEEP = "KEEP"
    REDUCE = "REDUCE"
    DEPRIORITIZE = "DEPRIORITIZE"


class BehaviorLabel(str, Enum):
    PREMIUM_CONTINUATION = "PREMIUM_CONTINUATION"
    HEALTHY = "HEALTHY"
    NEUTRAL = "NEUTRAL"
    WARM_BUT_WEAK = "WARM_BUT_WEAK"
    STAGNATION_RISK = "STAGNATION_RISK"
    RECENT_FAILURE = "RECENT_FAILURE"
    EXHAUSTED = "EXHAUSTED"
    UNSTABLE = "UNSTABLE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class ALOMode(str, Enum):
    PASSIVE = "PASSIVE"
    ADVISORY = "ADVISORY"
    ACTIVE = "ACTIVE"


# =============================================================================
# INPUT MODELS
# =============================================================================

@dataclass
class TechnicalContext:
    price: float
    rsi: float
    ema_fast: float
    ema_slow: float
    ema_trend: float
    volume_ratio: float
    trend: str
    momentum: str
    market_state: str
    selection_score: float
    market_score: float = 0.0
    base_score: float = 0.0
    penalty: float = 0.0


@dataclass
class MacroMarketContext:
    liquidity_score: float
    liquidity_label: str
    liquidity_message: str
    avg_volume_ratio: float
    uptrend_count: int
    refined_count: int
    approved_count: int
    total_assets: int
    market_regime_internal: str = ""


@dataclass
class MemoryContext:
    last_trade_result: Optional[str] = None
    last_exit_reason: Optional[str] = None
    win_rate: float = 0.5
    loss_streak: int = 0
    stagnation_count_recent: int = 0
    fast_stop_flag: bool = False
    recent_failures: int = 0
    recent_wins: int = 0
    confidence_history_score: float = 0.5


@dataclass
class TemporalContext:
    minutes_since_last_trade: Optional[int] = None
    minutes_since_last_failure: Optional[int] = None
    minutes_since_last_win: Optional[int] = None
    recent_activity_score: float = 0.0


@dataclass
class StructuralContext:
    structural_block: bool = False
    hard_block: bool = False
    soft_block: bool = False
    asset_class: str = "UNKNOWN"
    pair_maturity: str = "UNKNOWN"
    historical_reliability: float = 0.5


@dataclass
class WebContext:
    macro_regime: str = "NEUTRAL"
    news_risk: str = "LOW"
    asset_event_risk: str = "NONE"
    continuation_context: str = "MEDIUM"
    market_sentiment: str = "MIXED"


@dataclass
class ALOInput:
    symbol: str
    technical: TechnicalContext
    macro: MacroMarketContext
    memory: MemoryContext
    temporal: TemporalContext
    structural: StructuralContext
    web: WebContext


# =============================================================================
# INTERNAL MODELS
# =============================================================================

@dataclass
class ReasonBundle:
    codes: List[str] = field(default_factory=list)

    def add(self, code: str) -> None:
        if code and code not in self.codes:
            self.codes.append(code)


@dataclass
class BehaviorProfile:
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    behavior_label: BehaviorLabel = BehaviorLabel.NEUTRAL
    reentry_state: ReentryState = ReentryState.CLEAN
    dynamic_penalty: float = 0.0
    dynamic_bonus: float = 0.0
    risk_bias: RiskBias = RiskBias.NORMAL
    ranking_bias: RankingBias = RankingBias.KEEP
    guidance: GuidanceType = GuidanceType.ALLOW_WITH_CAUTION
    reason_codes: List[str] = field(default_factory=list)


# =============================================================================
# OUTPUT MODEL
# =============================================================================

@dataclass
class ALOGuidance:
    symbol: str
    confidence_level: ConfidenceLevel
    behavior_label: BehaviorLabel
    reentry_state: ReentryState
    dynamic_penalty: float
    dynamic_bonus: float
    risk_bias: RiskBias
    ranking_bias: RankingBias
    guidance: GuidanceType
    reason_codes: List[str]
    explainability_text: str