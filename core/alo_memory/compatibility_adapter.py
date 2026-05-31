from typing import Any, Dict, Optional

from core.alo_memory.models import ALOMemoryEventProjection, ALOMemoryProfile
from core.alo_memory.service import ALOMemoryReadOnlyService


class ALOMemoryCompatibilityAdapter:
    """
    Compatibility facade for future migration from AdaptiveLearningObserver.

    In Phase 1 this adapter is not connected to operational consumers. Its
    methods are read-only/projection-only and keep operational effects at zero.
    """

    def __init__(self, service: Optional[ALOMemoryReadOnlyService] = None) -> None:
        self.service = service or ALOMemoryReadOnlyService()

    def get_symbol_profile(self, symbol: str) -> ALOMemoryProfile:
        safe_symbol = str(symbol or "").strip().upper()
        snapshot = self.service.get_last_snapshot()
        if snapshot is None:
            snapshot = self.service.build_snapshot(emit_logs=False)
        return snapshot.get_profile(safe_symbol)

    def get_symbol_summary(self, symbol: str) -> Dict[str, Any]:
        profile = self.get_symbol_profile(symbol)
        return {
            "symbol": profile.symbol,
            "total_events": profile.total_events,
            "attempts": profile.attempt_count,
            "approvals": profile.approval_count,
            "rejections": profile.rejection_count,
            "dominant_rejection_reason": profile.dominant_rejection_reason,
            "confidence_score": profile.confidence_score,
            "status": profile.status,
            "no_effect": True,
            "operational_effect_count": 0,
        }

    def get_learning_summary(self) -> Dict[str, Any]:
        snapshot = self.service.get_last_snapshot()
        if snapshot is None:
            snapshot = self.service.build_snapshot(emit_logs=False)

        top_symbols = sorted(
            (
                {
                    "symbol": profile.symbol,
                    "confidence_score": profile.confidence_score,
                    "total_events": profile.total_events,
                    "status": profile.status,
                }
                for profile in snapshot.profiles.values()
            ),
            key=lambda item: (
                float(item.get("confidence_score", 0.0)),
                int(item.get("total_events", 0)),
            ),
            reverse=True,
        )

        return {
            "total_symbols": snapshot.profiles_count,
            "divergences": len(snapshot.divergences),
            "top_symbols": top_symbols[:10],
            "mode": snapshot.mode,
            "no_effect": True,
            "operational_effect_count": 0,
        }

    def ingest_event(self, event: Dict[str, Any]) -> ALOMemoryEventProjection:
        if not isinstance(event, dict):
            return ALOMemoryEventProjection(
                event_source="COMPAT_INGEST",
                event_type="INVALID",
                symbol="",
                applied_to_projection=False,
                reason_codes=("INVALID_EVENT", "READ_ONLY_NO_EFFECT"),
            )

        symbol = str(event.get("symbol") or event.get("pair") or "").strip().upper()
        event_type = str(event.get("event_type", "") or "UNKNOWN").strip().upper()

        return ALOMemoryEventProjection(
            event_source="COMPAT_INGEST",
            event_type=event_type,
            symbol=symbol,
            applied_to_projection=False,
            changed_fields=tuple(),
            reason_codes=("READ_ONLY_NO_EFFECT",),
            no_effect=True,
            operational_effect_count=0,
        )
