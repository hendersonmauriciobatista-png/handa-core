from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from core.alo_context.models import ALOContextSource


class ALOContextProvider:
    """
    Read-only provider contract for ALOContext sources.

    Providers must only collect and normalize source data. They must not create
    gates, mutate runtime state, alter scores, or emit operational decisions.
    """

    name = "unknown"
    source_type = "UNKNOWN"
    scope = "GLOBAL"
    required = False

    def collect(self) -> ALOContextSource:
        return ALOContextSource(
            name=self.name,
            source_type=self.source_type,
            scope=self.scope,
            timestamp=self._now_iso(),
            available=False,
            fields=tuple(),
            payload={},
            no_effect=True,
            operational_effect_count=0,
        )

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()


class StaticALOContextProvider(ALOContextProvider):
    """
    Passive provider for tests, audits, and future controlled wiring.
    """

    def __init__(
        self,
        name: str,
        payload: Dict[str, Any] | None = None,
        source_type: str = "STATIC",
        scope: str = "GLOBAL",
        required: bool = False,
        timestamp: str = "",
    ) -> None:
        self.name = str(name or "static")
        self.source_type = str(source_type or "STATIC").upper()
        self.scope = str(scope or "GLOBAL").upper()
        self.required = bool(required)
        self.payload = dict(payload or {})
        self.timestamp = str(timestamp or "")

    def collect(self) -> ALOContextSource:
        payload = dict(self.payload)
        fields: Tuple[str, ...] = tuple(sorted(str(key) for key in payload.keys()))
        return ALOContextSource(
            name=self.name,
            source_type=self.source_type,
            scope=self.scope,
            timestamp=self.timestamp or self._now_iso(),
            available=True,
            fields=fields,
            payload=payload,
            no_effect=True,
            operational_effect_count=0,
        )
