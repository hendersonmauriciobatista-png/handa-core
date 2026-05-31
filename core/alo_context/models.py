from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Tuple


READ_ONLY_MODE = "READ_ONLY"


@dataclass(frozen=True)
class ALOContextSource:
    name: str
    source_type: str = "UNKNOWN"
    scope: str = "GLOBAL"
    timestamp: str = ""
    available: bool = False
    freshness_seconds: float | None = None
    fields: Tuple[str, ...] = field(default_factory=tuple)
    payload: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    no_effect: bool = True
    operational_effect_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ALOContextSnapshot:
    cycle_id: str
    timestamp: str
    global_context: Dict[str, Any] = field(default_factory=dict)
    local_contexts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    position_context: Dict[str, Any] = field(default_factory=dict)
    system_context: Dict[str, Any] = field(default_factory=dict)
    sources: Tuple[ALOContextSource, ...] = field(default_factory=tuple)
    divergences: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    freshness: Dict[str, Any] = field(default_factory=dict)
    missing_sources: Tuple[str, ...] = field(default_factory=tuple)
    summary: Dict[str, Any] = field(default_factory=dict)
    mode: str = READ_ONLY_MODE
    no_effect: bool = True
    operational_effect_count: int = 0

    def get_local_context(self, symbol: str) -> Dict[str, Any]:
        safe_symbol = str(symbol or "").strip().upper()
        return dict(self.local_contexts.get(safe_symbol, {}))

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["sources"] = [source.to_dict() for source in self.sources]
        data["divergences"] = [dict(item) for item in self.divergences]
        return data
