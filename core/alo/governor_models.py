from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Tuple


READ_ONLY_MODE = "READ_ONLY"


@dataclass(frozen=True)
class ALOGovernorGuidance:
    guidance_id: str
    cycle_id: str
    symbol: str
    timestamp: str
    global_context_state: str = "UNKNOWN"
    context_stability: str = "UNKNOWN"
    specialized_alignment: str = "UNKNOWN"
    conflict_level: str = "NONE"
    premium_context: str = "NOT_OBSERVED"
    aggressiveness_guidance: str = "OBSERVE_ONLY"
    caution_level: str = "UNKNOWN"
    interpretation_label: str = "INSUFFICIENT_CONTEXT"
    reason_codes: Tuple[str, ...] = field(default_factory=tuple)
    explainability: str = ""
    missing_sources: Tuple[str, ...] = field(default_factory=tuple)
    source_summary: Dict[str, Any] = field(default_factory=dict)
    mode: str = READ_ONLY_MODE
    no_effect: bool = True
    operational_effect_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ALOGovernorConflictReport:
    conflict_id: str
    symbol: str
    sources: Tuple[str, ...]
    conflict_type: str
    observed_values: Dict[str, Any] = field(default_factory=dict)
    authority_owner: str = "UNKNOWN"
    interpretation: str = ""
    severity: str = "INFO"
    mode: str = READ_ONLY_MODE
    no_effect: bool = True
    operational_effect_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ALOGovernorContextSnapshot:
    cycle_id: str
    timestamp: str
    global_context: Dict[str, Any] = field(default_factory=dict)
    local_contexts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    source_freshness: Dict[str, Any] = field(default_factory=dict)
    guidance: ALOGovernorGuidance | None = None
    conflicts: Tuple[ALOGovernorConflictReport, ...] = field(default_factory=tuple)
    missing_sources: Tuple[str, ...] = field(default_factory=tuple)
    provenance: Dict[str, Any] = field(default_factory=dict)
    mode: str = READ_ONLY_MODE
    no_effect: bool = True
    operational_effect_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
