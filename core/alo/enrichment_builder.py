import copy
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from core.alo.enrichment_models import (
    ALLOWED_ENRICHMENT_STAGES,
    ALOEnrichmentEvent,
)


class ALOEnrichmentBuilder:
    """
    Normalizes passive near-pass observations into read-only ALO events.

    This builder does not query operational components, persist events, create
    consumers, infer approvals, recalculate thresholds, or alter runtime state.
    """

    ALLOWED_STAGES = ALLOWED_ENRICHMENT_STAGES

    def build(self, payload: Mapping[str, Any]) -> Optional[ALOEnrichmentEvent]:
        if not isinstance(payload, Mapping):
            return None

        symbol = self._safe_upper(payload.get("symbol"))
        stage = self._safe_upper(payload.get("stage"))
        if not symbol or stage not in self.ALLOWED_STAGES:
            return None

        classification = self._safe_upper(payload.get("classification"))
        if classification not in self.ALLOWED_STAGES:
            classification = stage

        context = self._normalize_context(payload.get("context"))
        delta = self._normalize_delta(payload.get("delta"))
        required_change = self._normalize_required_change(
            payload.get("required_change")
        )

        return ALOEnrichmentEvent(
            event_id=uuid.uuid4().hex,
            symbol=symbol,
            timestamp=self._safe_timestamp(payload.get("timestamp")),
            stage=stage,
            classification=classification,
            reason=self._safe_upper(payload.get("reason")),
            context=context,
            delta=delta,
            required_change=required_change,
            no_effect=True,
            operational_effect_count=0,
        )

    def _normalize_context(self, value: Any) -> Dict[str, Any]:
        if not isinstance(value, Mapping):
            return {}
        return copy.deepcopy(dict(value))

    def _normalize_delta(self, value: Any) -> Dict[str, float]:
        if not isinstance(value, Mapping):
            return {}

        normalized: Dict[str, float] = {}
        for key, raw_value in value.items():
            safe_key = str(key or "").strip()
            if not safe_key:
                continue
            try:
                normalized[safe_key] = float(raw_value)
            except (TypeError, ValueError):
                continue
        return copy.deepcopy(normalized)

    def _normalize_required_change(self, value: Any) -> Tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            values = (value,)
        elif isinstance(value, (list, tuple, set, frozenset)):
            values = value
        else:
            return ()

        return tuple(
            text
            for text in (str(item or "").strip() for item in values)
            if text
        )

    def _safe_timestamp(self, value: Any) -> str:
        supplied = str(value or "").strip()
        return supplied or datetime.now(timezone.utc).isoformat()

    def _safe_upper(self, value: Any) -> str:
        return str(value or "").strip().upper()
