from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Tuple


READ_ONLY_MODE = "READ_ONLY"


@dataclass(frozen=True)
class ALOMemoryProfile:
    symbol: str

    total_events: int = 0
    execution_count: int = 0
    non_execution_count: int = 0
    win_count: int = 0
    loss_count: int = 0

    attempt_count: int = 0
    approval_count: int = 0
    rejection_count: int = 0

    structural_block_count: int = 0
    technical_rejection_count: int = 0
    macro_block_count: int = 0
    quality_filter_count: int = 0
    low_score_count: int = 0

    confidence_score: float = 0.0
    status: str = "NO_HISTORY"
    block_bias: float = 0.0
    confidence_bias: float = 0.0
    capital_bias: float = 1.0

    recent_results: Tuple[float, ...] = field(default_factory=tuple)
    recent_reasons: Tuple[str, ...] = field(default_factory=tuple)
    dominant_rejection_reason: str = "NONE"
    last_market_state: str = ""

    source_counts: Dict[str, int] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    mode: str = READ_ONLY_MODE
    no_effect: bool = True
    operational_effect_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ALOMemoryDivergence:
    symbol: str
    field: str
    projected: Any
    reference: Any
    reference_source: str
    severity: str = "INFO"
    reason: str = ""
    no_effect: bool = True
    operational_effect_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ALOMemoryEventProjection:
    event_source: str
    event_type: str
    symbol: str
    applied_to_projection: bool = False
    changed_fields: Tuple[str, ...] = field(default_factory=tuple)
    reason_codes: Tuple[str, ...] = field(default_factory=tuple)
    no_effect: bool = True
    operational_effect_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ALOMemorySnapshot:
    generated_at: str
    profiles_count: int
    profiles: Dict[str, ALOMemoryProfile] = field(default_factory=dict)
    divergences: Tuple[ALOMemoryDivergence, ...] = field(default_factory=tuple)
    source_files: Dict[str, str] = field(default_factory=dict)
    source_event_counts: Dict[str, int] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    mode: str = READ_ONLY_MODE
    no_effect: bool = True
    operational_effect_count: int = 0

    def get_profile(self, symbol: str) -> ALOMemoryProfile:
        safe_symbol = str(symbol or "").strip().upper()
        return self.profiles.get(safe_symbol, ALOMemoryProfile(symbol=safe_symbol))

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["profiles"] = {
            symbol: profile.to_dict() for symbol, profile in self.profiles.items()
        }
        data["divergences"] = [item.to_dict() for item in self.divergences]
        return data
