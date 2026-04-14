# ============================================================
# core/alo/vision_models.py
# H&A — ALO Vision Models
# Modelos estruturais da camada de visão do ALO
# ============================================================

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional


# ============================================================
# MARKET CONTEXT
# ============================================================


@dataclass
class MarketContext:
    liquidity_score: float = 0.0
    liquidity_label: str = ""
    liquidity_message: str = ""

    avg_volume_ratio: float = 0.0
    uptrend_count: int = 0
    refined_count: int = 0
    approved_count: int = 0

    market_state: str = "UNKNOWN"
    opportunity_density: str = "UNKNOWN"
    trend_strength: str = "UNKNOWN"

    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# SETUP CONTEXT
# ============================================================


@dataclass
class SetupContext:
    symbol: str = ""

    trend: str = "UNKNOWN"
    momentum: str = "UNKNOWN"
    market_state: str = "UNKNOWN"
    volume_state: str = "UNKNOWN"

    rsi: float = 0.0
    volume_ratio: float = 0.0
    price: float = 0.0

    ema_fast: float = 0.0
    ema_slow: float = 0.0

    quality_label: str = "UNKNOWN"
    quality_score: float = 0.0

    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# VISION INFERENCE
# ============================================================


@dataclass
class VisionInference:
    confidence_label: str = "UNKNOWN"
    confidence_score: float = 0.0

    expected_outcome: str = "UNKNOWN"
    guidance: str = "NEUTRAL"

    summary: str = ""
    reasons: list[str] = field(default_factory=list)

    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# ALO VISION SNAPSHOT
# ============================================================


@dataclass
class AloVisionSnapshot:
    symbol: str = ""
    timestamp: str = ""

    market_context: MarketContext = field(default_factory=MarketContext)
    setup_context: SetupContext = field(default_factory=SetupContext)
    inference: VisionInference = field(default_factory=VisionInference)

    source: str = "alo_vision_engine"
    version: str = "1.0"

    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "source": self.source,
            "version": self.version,
            "market_context": self.market_context.to_dict(),
            "setup_context": self.setup_context.to_dict(),
            "inference": self.inference.to_dict(),
            "extra": self.extra,
        }


# ============================================================
# HELPER FACTORY
# ============================================================


def build_vision_snapshot(
    symbol: str = "",
    timestamp: str = "",
    market_context: Optional[MarketContext] = None,
    setup_context: Optional[SetupContext] = None,
    inference: Optional[VisionInference] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> AloVisionSnapshot:
    return AloVisionSnapshot(
        symbol=symbol,
        timestamp=timestamp,
        market_context=market_context or MarketContext(),
        setup_context=setup_context or SetupContext(),
        inference=inference or VisionInference(),
        extra=extra or {},
    )
