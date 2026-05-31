from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Tuple


READ_ONLY_MODE = "READ_ONLY"

FORBIDDEN_ACTIONS = (
    "APPROVE",
    "ALLOW",
    "BLOCK",
    "REJECT",
    "BUY",
    "SELL",
    "BUY_READY",
    "RISK_OK",
    "RELEASE",
    "EXECUTE",
    "ALTER_SCORE",
    "ALTER_RANKING",
    "ALTER_CAPITAL",
    "ALTER_POSITION",
    "ALTER_SLOT",
)


@dataclass(frozen=True)
class ALOGovernanceSnapshot:
    symbol: str
    cycle_id: str
    generated_at: str

    mode: str = READ_ONLY_MODE
    no_effect: bool = True
    operational_effect_count: int = 0

    guidance_available: bool = False

    recommendation_type: str = "NO_RECOMMENDATION"
    recommendation_label: str = "NO_RECOMMENDATION"
    recommendation_strength: str = "NONE"

    recommendation_reason_codes: Tuple[str, ...] = field(default_factory=tuple)
    recommendation_notes: Tuple[str, ...] = field(default_factory=tuple)
    constraints: Tuple[str, ...] = field(default_factory=tuple)
    forbidden_actions: Tuple[str, ...] = field(default_factory=lambda: FORBIDDEN_ACTIONS)
    missing_sources: Tuple[str, ...] = field(default_factory=tuple)
    source_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
