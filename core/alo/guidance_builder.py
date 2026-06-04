from datetime import datetime, timezone
from typing import Any, Dict, List

from core.alo.guidance_models import ALOGuidanceSnapshot


class ALOGuidanceBuilder:
    """
    Read-only interpreter for ALOMemory + ALOContext.

    This builder answers only what the current memory/context means. It does
    not recommend BUY, recommend SELL, block assets, release assets, alter
    score, alter ranking, alter capital, or connect to operational runtime.
    """

    def build(
        self,
        symbol: str = "",
        cycle_id: str = "",
        memory_snapshot: Any = None,
        context_snapshot: Any = None,
        global_guidance_snapshot: Any = None,
    ) -> ALOGuidanceSnapshot:
        safe_symbol = self._safe_symbol(symbol)
        memory_available = self._is_available(memory_snapshot)
        context_available = self._is_available(context_snapshot)
        macro_context = self._extract_macro_context(global_guidance_snapshot)

        profile = self._get_memory_profile(memory_snapshot, safe_symbol)
        local_context = self._get_local_context(context_snapshot, safe_symbol)

        historical_alignment = self._interpret_historical_alignment(profile)
        context_stability = self._interpret_context_stability(context_snapshot)
        similarity_level = self._interpret_similarity(profile, local_context)
        divergence_level = self._interpret_divergence_level(
            memory_snapshot, context_snapshot
        )

        missing_sources = self._collect_missing_sources(
            memory_available=memory_available,
            context_available=context_available,
            context_snapshot=context_snapshot,
        )
        reason_codes = self._build_reason_codes(
            historical_alignment=historical_alignment,
            context_stability=context_stability,
            similarity_level=similarity_level,
            divergence_level=divergence_level,
            missing_sources=missing_sources,
            macro_context=macro_context,
        )
        interpretation_label = self._interpret_label(
            memory_available=memory_available,
            context_available=context_available,
            historical_alignment=historical_alignment,
            context_stability=context_stability,
            divergence_level=divergence_level,
        )
        notes = self._build_notes(
            historical_alignment=historical_alignment,
            context_stability=context_stability,
            similarity_level=similarity_level,
            divergence_level=divergence_level,
            missing_sources=missing_sources,
            macro_context=macro_context,
        )

        snapshot = ALOGuidanceSnapshot(
            symbol=safe_symbol,
            cycle_id=str(cycle_id or ""),
            generated_at=self._now_iso(),
            memory_available=memory_available,
            context_available=context_available,
            macro_context_available=bool(macro_context["available"]),
            historical_alignment=historical_alignment,
            context_stability=context_stability,
            similarity_level=similarity_level,
            divergence_level=divergence_level,
            macro_alignment=float(macro_context["macro_alignment"]),
            macro_state=str(macro_context["macro_state"]),
            macro_reason_codes=tuple(macro_context["macro_reason_codes"]),
            macro_explainability=str(macro_context["macro_explainability"]),
            macro_no_effect=bool(macro_context["no_effect"]),
            macro_operational_effect_count=int(
                macro_context["operational_effect_count"]
            ),
            interpretation_label=interpretation_label,
            interpretation_notes=tuple(notes),
            reason_codes=tuple(reason_codes),
            missing_sources=tuple(missing_sources),
            source_summary=self._build_source_summary(
                memory_snapshot,
                context_snapshot,
                profile,
                local_context,
                macro_context,
            ),
            no_effect=True,
            operational_effect_count=0,
        )

        if macro_context["available"]:
            print(
                "[ALO GUIDANCE MACRO READONLY] "
                f"macro_state={macro_context['macro_state']} | "
                f"macro_alignment={float(macro_context['macro_alignment']):.4f} | "
                f"no_effect={str(macro_context['no_effect']).lower()} | "
                f"operational_effect_count="
                f"{int(macro_context['operational_effect_count'])}"
            )

        return snapshot

    def _is_available(self, snapshot: Any) -> bool:
        if snapshot is None:
            return False
        if getattr(snapshot, "no_effect", True) is not True:
            return False
        return True

    def _get_memory_profile(self, memory_snapshot: Any, symbol: str) -> Any:
        if memory_snapshot is None or not symbol:
            return None

        profiles = getattr(memory_snapshot, "profiles", {}) or {}
        if isinstance(profiles, dict):
            return profiles.get(symbol)

        getter = getattr(memory_snapshot, "get_profile", None)
        if callable(getter):
            profile = getter(symbol)
            total_events = int(getattr(profile, "total_events", 0) or 0)
            return profile if total_events > 0 else None

        return None

    def _get_local_context(self, context_snapshot: Any, symbol: str) -> Dict[str, Any]:
        if context_snapshot is None or not symbol:
            return {}
        getter = getattr(context_snapshot, "get_local_context", None)
        if callable(getter):
            return getter(symbol)
        local_contexts = getattr(context_snapshot, "local_contexts", {}) or {}
        return dict(local_contexts.get(symbol, {}) or {})

    def _interpret_historical_alignment(self, profile: Any) -> str:
        if profile is None:
            return "NO_MEMORY"
        total_events = int(getattr(profile, "total_events", 0) or 0)
        if total_events <= 0:
            return "NO_HISTORY"
        confidence = float(getattr(profile, "confidence_score", 0.0) or 0.0)
        if confidence >= 0.60:
            return "POSITIVE_HISTORY"
        if confidence <= 0.30:
            return "WEAK_HISTORY"
        return "MIXED_HISTORY"

    def _interpret_context_stability(self, context_snapshot: Any) -> str:
        if context_snapshot is None:
            return "NO_CONTEXT"
        divergences = len(getattr(context_snapshot, "divergences", ()) or ())
        missing = len(getattr(context_snapshot, "missing_sources", ()) or ())
        if divergences <= 0 and missing <= 0:
            return "STABLE_CONTEXT"
        if divergences <= 2 and missing <= 1:
            return "PARTIAL_CONTEXT"
        return "DIVERGENT_CONTEXT"

    def _interpret_similarity(self, profile: Any, local_context: Dict[str, Any]) -> str:
        if profile is None or not local_context:
            return "UNKNOWN"
        last_market_state = str(getattr(profile, "last_market_state", "") or "").upper()
        current_market_state = str(local_context.get("market_state", "") or "").upper()
        if not last_market_state or not current_market_state:
            return "INSUFFICIENT_CONTEXT"
        if last_market_state == current_market_state:
            return "SIMILAR"
        return "DIFFERENT"

    def _interpret_divergence_level(
        self, memory_snapshot: Any, context_snapshot: Any
    ) -> str:
        memory_divergences = len(getattr(memory_snapshot, "divergences", ()) or ())
        context_divergences = len(getattr(context_snapshot, "divergences", ()) or ())
        total = memory_divergences + context_divergences
        if total <= 0:
            return "NONE"
        if total <= 3:
            return "LOW"
        if total <= 10:
            return "MEDIUM"
        return "HIGH"

    def _collect_missing_sources(
        self,
        memory_available: bool,
        context_available: bool,
        context_snapshot: Any,
    ) -> List[str]:
        missing: List[str] = []
        if not memory_available:
            missing.append("ALO_MEMORY")
        if not context_available:
            missing.append("ALO_CONTEXT")
        missing.extend(
            str(item) for item in getattr(context_snapshot, "missing_sources", ()) or ()
        )
        return sorted(set(missing))

    def _build_reason_codes(
        self,
        historical_alignment: str,
        context_stability: str,
        similarity_level: str,
        divergence_level: str,
        missing_sources: List[str],
        macro_context: Dict[str, Any],
    ) -> List[str]:
        codes = [
            f"HISTORICAL_ALIGNMENT={historical_alignment}",
            f"CONTEXT_STABILITY={context_stability}",
            f"SIMILARITY_LEVEL={similarity_level}",
            f"DIVERGENCE_LEVEL={divergence_level}",
        ]
        codes.extend(f"MISSING_SOURCE={source}" for source in missing_sources)
        if macro_context["available"]:
            codes.append("MACRO_CONTEXT_AVAILABLE=True")
            codes.append(f"MACRO_STATE={macro_context['macro_state']}")
            codes.append(
                f"MACRO_ALIGNMENT={float(macro_context['macro_alignment']):.4f}"
            )
            codes.extend(str(code) for code in macro_context["macro_reason_codes"])
        codes.append("READ_ONLY_NO_EFFECT")
        return codes

    def _interpret_label(
        self,
        memory_available: bool,
        context_available: bool,
        historical_alignment: str,
        context_stability: str,
        divergence_level: str,
    ) -> str:
        if not memory_available or not context_available:
            return "INSUFFICIENT_DATA"
        if divergence_level == "HIGH" or context_stability == "DIVERGENT_CONTEXT":
            return "CONTEXT_CONFLICT"
        if (
            historical_alignment == "POSITIVE_HISTORY"
            and context_stability == "STABLE_CONTEXT"
        ):
            return "ALIGNED_CONTEXT"
        if historical_alignment == "WEAK_HISTORY":
            return "WEAK_HISTORICAL_CONTEXT"
        return "NEUTRAL_CONTEXT"

    def _build_notes(
        self,
        historical_alignment: str,
        context_stability: str,
        similarity_level: str,
        divergence_level: str,
        missing_sources: List[str],
        macro_context: Dict[str, Any],
    ) -> List[str]:
        notes = [
            f"Historical alignment is {historical_alignment}.",
            f"Context stability is {context_stability}.",
            f"Similarity level is {similarity_level}.",
            f"Divergence level is {divergence_level}.",
        ]
        if macro_context["available"]:
            notes.append(
                "Macro leaders context is "
                f"{macro_context['macro_state']} "
                f"with alignment {float(macro_context['macro_alignment']):.4f}."
            )
            notes.append(str(macro_context["macro_explainability"]))
        if missing_sources:
            notes.append(f"Missing sources: {', '.join(missing_sources)}.")
        notes.append("Read-only interpretation only; no operational effect.")
        return notes

    def _build_source_summary(
        self,
        memory_snapshot: Any,
        context_snapshot: Any,
        profile: Any,
        local_context: Dict[str, Any],
        macro_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "memory_mode": getattr(memory_snapshot, "mode", ""),
            "context_mode": getattr(context_snapshot, "mode", ""),
            "memory_divergences": len(
                getattr(memory_snapshot, "divergences", ()) or ()
            ),
            "context_divergences": len(
                getattr(context_snapshot, "divergences", ()) or ()
            ),
            "memory_profile_available": profile is not None,
            "local_context_fields": len(local_context),
            "macro_context_available": bool(macro_context["available"]),
            "macro_state": macro_context["macro_state"],
            "macro_alignment": macro_context["macro_alignment"],
            "macro_no_effect": macro_context["no_effect"],
            "macro_operational_effect_count": macro_context[
                "operational_effect_count"
            ],
            "no_effect": True,
            "operational_effect_count": 0,
        }

    def _extract_macro_context(self, global_guidance_snapshot: Any) -> Dict[str, Any]:
        default = {
            "available": False,
            "macro_alignment": 0.0,
            "macro_state": "UNKNOWN",
            "macro_reason_codes": tuple(),
            "macro_explainability": "",
            "no_effect": True,
            "operational_effect_count": 0,
        }

        if global_guidance_snapshot is None:
            return default

        mode = str(
            getattr(global_guidance_snapshot, "mode", "") or ""
        ).strip().upper()
        no_effect = getattr(global_guidance_snapshot, "no_effect", True)
        operational_effect_count = int(
            getattr(global_guidance_snapshot, "operational_effect_count", 0) or 0
        )

        if mode != "READ_ONLY" or no_effect is not True or operational_effect_count != 0:
            return default

        return {
            "available": True,
            "macro_alignment": float(
                getattr(global_guidance_snapshot, "macro_alignment", 0.0) or 0.0
            ),
            "macro_state": str(
                getattr(global_guidance_snapshot, "macro_state", "UNKNOWN")
                or "UNKNOWN"
            ).strip().upper(),
            "macro_reason_codes": tuple(
                getattr(global_guidance_snapshot, "macro_reason_codes", ()) or ()
            ),
            "macro_explainability": str(
                getattr(global_guidance_snapshot, "macro_explainability", "") or ""
            ),
            "no_effect": True,
            "operational_effect_count": 0,
        }

    def _safe_symbol(self, value: Any) -> str:
        return str(value or "").strip().upper()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
