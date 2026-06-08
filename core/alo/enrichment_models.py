from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Tuple


READ_ONLY_MODE = "READ_ONLY"

ALLOWED_ENRICHMENT_STAGES = (
    "NEAR_PASS_SELECTION",
    "NEAR_PASS_MCE",
    "NEAR_PASS_DECISION",
)


@dataclass(frozen=True)
class ALOEnrichmentEvent:
    event_id: str
    symbol: str
    timestamp: str
    stage: str
    classification: str
    reason: str
    context: Dict[str, Any] = field(default_factory=dict)
    delta: Dict[str, float] = field(default_factory=dict)
    required_change: Tuple[str, ...] = field(default_factory=tuple)
    source: str = "ALO_ENRICHMENT_A"
    mode: str = READ_ONLY_MODE
    no_effect: bool = True
    operational_effect_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
