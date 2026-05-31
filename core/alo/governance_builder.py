from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from core.alo.governance_models import ALOGovernanceSnapshot, FORBIDDEN_ACTIONS


class ALOGovernanceBuilder:
    """
    Read-only institutional recommendation layer for ALOGuidance.

    This builder consumes only a guidance snapshot. It does not execute trades,
    create gates, alter runtime state, alter score, alter ranking, alter
    capital, alter positions, or alter slots.
    """

    ALLOWED_RECOMMENDATIONS = (
        "OBSERVE_ONLY",
        "MAINTAIN_CAUTION",
        "REQUEST_MORE_DATA",
        "ESCALATE_FOR_REVIEW",
        "NO_RECOMMENDATION",
    )

    def build(
        self,
        symbol: str = "",
        cycle_id: str = "",
        guidance_snapshot: Any = None,
    ) -> ALOGovernanceSnapshot:
        safe_symbol = self._resolve_symbol(symbol, guidance_snapshot)
        safe_cycle_id = self._resolve_cycle_id(cycle_id, guidance_snapshot)
        guidance_available = self._is_valid_guidance(guidance_snapshot)

        if not guidance_available:
            recommendation_type = "REQUEST_MORE_DATA"
            recommendation_label = "REQUEST_MORE_DATA"
            missing_sources = ("ALO_GUIDANCE",)
            reason_codes = (
                "GUIDANCE_AVAILABLE=False",
                "MISSING_SOURCE=ALO_GUIDANCE",
                "READ_ONLY_NO_EFFECT",
            )
            notes = (
                "Valid ALOGuidance snapshot is required for institutional recommendation.",
                "Read-only recommendation only; no operational effect.",
            )
        else:
            interpretation_label = str(
                getattr(guidance_snapshot, "interpretation_label", "") or ""
            ).strip().upper()
            missing_sources = tuple(
                str(item)
                for item in (getattr(guidance_snapshot, "missing_sources", ()) or ())
            )
            recommendation_type = self._map_recommendation(interpretation_label)
            recommendation_label = recommendation_type
            reason_codes = self._build_reason_codes(
                guidance_snapshot=guidance_snapshot,
                recommendation_type=recommendation_type,
            )
            notes = self._build_notes(
                interpretation_label=interpretation_label,
                recommendation_type=recommendation_type,
                missing_sources=missing_sources,
            )

        return ALOGovernanceSnapshot(
            symbol=safe_symbol,
            cycle_id=safe_cycle_id,
            generated_at=self._now_iso(),
            guidance_available=guidance_available,
            recommendation_type=recommendation_type,
            recommendation_label=recommendation_label,
            recommendation_strength=self._recommendation_strength(recommendation_type),
            recommendation_reason_codes=tuple(reason_codes),
            recommendation_notes=tuple(notes),
            constraints=self._build_constraints(),
            forbidden_actions=FORBIDDEN_ACTIONS,
            missing_sources=tuple(sorted(set(missing_sources))),
            source_summary=self._build_source_summary(
                guidance_snapshot, guidance_available
            ),
            no_effect=True,
            operational_effect_count=0,
        )

    def _is_valid_guidance(self, guidance_snapshot: Any) -> bool:
        if guidance_snapshot is None:
            return False
        mode = str(getattr(guidance_snapshot, "mode", "") or "").strip().upper()
        if mode != "READ_ONLY":
            return False
        if getattr(guidance_snapshot, "no_effect", None) is not True:
            return False
        if int(getattr(guidance_snapshot, "operational_effect_count", -1) or 0) != 0:
            return False
        return True

    def _map_recommendation(self, interpretation_label: str) -> str:
        mapping = {
            "INSUFFICIENT_DATA": "REQUEST_MORE_DATA",
            "CONTEXT_CONFLICT": "ESCALATE_FOR_REVIEW",
            "WEAK_HISTORICAL_CONTEXT": "MAINTAIN_CAUTION",
            "ALIGNED_CONTEXT": "OBSERVE_ONLY",
            "NEUTRAL_CONTEXT": "OBSERVE_ONLY",
        }
        recommendation = mapping.get(interpretation_label, "NO_RECOMMENDATION")
        return (
            recommendation
            if recommendation in self.ALLOWED_RECOMMENDATIONS
            else "NO_RECOMMENDATION"
        )

    def _recommendation_strength(self, recommendation_type: str) -> str:
        if recommendation_type == "ESCALATE_FOR_REVIEW":
            return "HIGH"
        if recommendation_type in ("REQUEST_MORE_DATA", "MAINTAIN_CAUTION"):
            return "MEDIUM"
        if recommendation_type == "OBSERVE_ONLY":
            return "LOW"
        return "NONE"

    def _build_reason_codes(
        self, guidance_snapshot: Any, recommendation_type: str
    ) -> Tuple[str, ...]:
        interpretation_label = str(
            getattr(guidance_snapshot, "interpretation_label", "") or ""
        ).strip().upper()
        divergence_level = str(
            getattr(guidance_snapshot, "divergence_level", "") or ""
        ).strip().upper()
        codes: List[str] = [
            "GUIDANCE_AVAILABLE=True",
            f"INTERPRETATION_LABEL={interpretation_label}",
            f"DIVERGENCE_LEVEL={divergence_level}",
            f"RECOMMENDATION_TYPE={recommendation_type}",
            "READ_ONLY_NO_EFFECT",
        ]
        for source in getattr(guidance_snapshot, "missing_sources", ()) or ():
            codes.append(f"MISSING_SOURCE={source}")
        return tuple(codes)

    def _build_notes(
        self,
        interpretation_label: str,
        recommendation_type: str,
        missing_sources: Tuple[str, ...],
    ) -> Tuple[str, ...]:
        notes = [
            f"Guidance interpretation label is {interpretation_label or 'UNKNOWN'}.",
            f"Institutional recommendation is {recommendation_type}.",
            "Recommendation is consultative and read-only.",
            "DecisionEngine remains the operational decision authority.",
        ]
        if missing_sources:
            notes.append(f"Missing sources: {', '.join(missing_sources)}.")
        notes.append("No operational action is authorized by this snapshot.")
        return tuple(notes)

    def _build_constraints(self) -> Tuple[str, ...]:
        return (
            "READ_ONLY",
            "NO_RUNTIME_CONNECTION",
            "NO_OPERATIONAL_GATE",
            "NO_SCORE_CHANGE",
            "NO_RANKING_CHANGE",
            "NO_CAPITAL_CHANGE",
            "NO_POSITION_CHANGE",
            "NO_SLOT_CHANGE",
        )

    def _build_source_summary(
        self, guidance_snapshot: Any, guidance_available: bool
    ) -> Dict[str, Any]:
        return {
            "guidance_available": guidance_available,
            "guidance_mode": getattr(guidance_snapshot, "mode", ""),
            "guidance_no_effect": getattr(guidance_snapshot, "no_effect", None),
            "guidance_operational_effect_count": getattr(
                guidance_snapshot, "operational_effect_count", None
            ),
            "guidance_interpretation_label": getattr(
                guidance_snapshot, "interpretation_label", ""
            ),
            "guidance_divergence_level": getattr(
                guidance_snapshot, "divergence_level", ""
            ),
            "no_effect": True,
            "operational_effect_count": 0,
        }

    def _resolve_symbol(self, symbol: str, guidance_snapshot: Any) -> str:
        value = symbol or getattr(guidance_snapshot, "symbol", "")
        return str(value or "").strip().upper()

    def _resolve_cycle_id(self, cycle_id: str, guidance_snapshot: Any) -> str:
        value = cycle_id or getattr(guidance_snapshot, "cycle_id", "")
        return str(value or "")

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
