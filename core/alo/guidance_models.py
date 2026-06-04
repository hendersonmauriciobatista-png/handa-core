from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Tuple


READ_ONLY_MODE = "READ_ONLY"


@dataclass(frozen=True)
class ALOGuidanceSnapshot:
    symbol: str
    cycle_id: str
    generated_at: str

    mode: str = READ_ONLY_MODE
    no_effect: bool = True
    operational_effect_count: int = 0

    memory_available: bool = False
    context_available: bool = False
    macro_context_available: bool = False

    historical_alignment: str = "UNKNOWN"
    context_stability: str = "UNKNOWN"
    similarity_level: str = "UNKNOWN"
    divergence_level: str = "UNKNOWN"
    macro_alignment: float = 0.0
    macro_state: str = "UNKNOWN"
    macro_reason_codes: Tuple[str, ...] = field(default_factory=tuple)
    macro_explainability: str = ""
    macro_no_effect: bool = True
    macro_operational_effect_count: int = 0

    interpretation_label: str = "INSUFFICIENT_DATA"
    interpretation_notes: Tuple[str, ...] = field(default_factory=tuple)
    reason_codes: Tuple[str, ...] = field(default_factory=tuple)
    missing_sources: Tuple[str, ...] = field(default_factory=tuple)
    source_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
