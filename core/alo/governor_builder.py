import copy
import uuid
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass, replace
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Tuple

from core.alo.governor_models import (
    ALOGovernorConflictReport,
    ALOGovernorContextSnapshot,
    ALOGovernorGuidance,
    READ_ONLY_MODE,
)


class ALOGovernorBuilder:
    """
    Builds a passive institutional interpretation from supplied snapshots.

    The builder does not query operational components, persist data, register
    consumers, create gates, or alter scores, thresholds, cooldowns, capital,
    positions, slots, decisions, or execution.
    """

    EXPECTED_SOURCES = (
        "MQII",
        "RANKING",
        "RADAR",
        "SELECTION",
        "MCE",
        "DECISION",
        "DRC",
        "ALO_ENRICHMENT",
        "ALO_MEMORY",
        "SYSTEM",
        "POSITION",
    )

    def build(
        self,
        snapshots: Mapping[str, Any] | None = None,
        symbol: str = "",
        cycle_id: str = "",
    ) -> ALOGovernorContextSnapshot:
        collected = self._collect(snapshots)
        valid_sources, invalid_sources = self._validate_boundaries(collected)
        normalized = self._normalize(valid_sources)
        interpretation = self._interpret_context(normalized)
        conflicts = self._resolve_conflicts(normalized, interpretation)

        missing_sources = tuple(
            source
            for source in self.EXPECTED_SOURCES
            if source not in normalized
        )
        safe_symbol = self._safe_upper(symbol) or self._resolve_symbol(normalized)
        safe_cycle_id = str(cycle_id or "").strip()
        timestamp = self._now_iso()

        guidance = self._build_guidance(
            symbol=safe_symbol,
            cycle_id=safe_cycle_id,
            timestamp=timestamp,
            normalized=normalized,
            interpretation=interpretation,
            conflicts=conflicts,
            missing_sources=missing_sources,
            invalid_sources=invalid_sources,
        )
        guidance = self._constitutional_guard(guidance)

        snapshot = ALOGovernorContextSnapshot(
            cycle_id=safe_cycle_id,
            timestamp=timestamp,
            global_context=self._build_global_context(normalized, interpretation),
            local_contexts=self._build_local_contexts(normalized, safe_symbol),
            source_freshness=self._build_source_freshness(normalized),
            guidance=guidance,
            conflicts=tuple(conflicts),
            missing_sources=missing_sources,
            provenance={
                "available_sources": tuple(sorted(normalized)),
                "invalid_sources": tuple(sorted(invalid_sources)),
                "expected_sources": self.EXPECTED_SOURCES,
                "mode": READ_ONLY_MODE,
                "no_effect": True,
                "operational_effect_count": 0,
            },
            no_effect=True,
            operational_effect_count=0,
        )
        return self._guard_snapshot(snapshot)

    # Collector
    def _collect(self, snapshots: Mapping[str, Any] | None) -> Dict[str, Dict[str, Any]]:
        if not isinstance(snapshots, Mapping):
            return {}

        collected: Dict[str, Dict[str, Any]] = {}
        for source, snapshot in snapshots.items():
            safe_source = self._safe_upper(source)
            payload = self._snapshot_to_dict(snapshot)
            if safe_source and payload is not None:
                collected[safe_source] = payload
        return collected

    # Boundary Validator
    def _validate_boundaries(
        self, collected: Mapping[str, Dict[str, Any]]
    ) -> Tuple[Dict[str, Dict[str, Any]], Tuple[str, ...]]:
        valid: Dict[str, Dict[str, Any]] = {}
        invalid = []

        for source, payload in collected.items():
            mode = self._safe_upper(payload.get("mode"))
            no_effect = payload.get("no_effect")
            try:
                effect_count = int(payload.get("operational_effect_count", -1))
            except (TypeError, ValueError):
                effect_count = -1

            if (
                mode == READ_ONLY_MODE
                and no_effect is True
                and effect_count == 0
            ):
                valid[source] = copy.deepcopy(payload)
            else:
                invalid.append(source)

        return valid, tuple(sorted(invalid))

    # Normalizer
    def _normalize(
        self, sources: Mapping[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        normalized: Dict[str, Dict[str, Any]] = {}
        for source, payload in sources.items():
            safe_payload = copy.deepcopy(payload)
            if "symbol" in safe_payload:
                safe_payload["symbol"] = self._safe_upper(safe_payload.get("symbol"))
            safe_payload["source"] = self._safe_upper(
                safe_payload.get("source") or source
            )
            normalized[self._safe_upper(source)] = safe_payload
        return normalized

    # Context Interpreter
    def _interpret_context(
        self, sources: Mapping[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        mqii = sources.get("MQII", {})
        global_state = self._safe_upper(
            mqii.get("state")
            or mqii.get("mqii_state")
            or mqii.get("global_context_state")
            or "UNKNOWN"
        )
        observed_states = self._collect_mqii_states(sources)
        specialized_alignment = (
            "UNKNOWN"
            if not observed_states
            else "ALIGNED"
            if len(set(observed_states.values())) == 1
            else "DIVERGENT"
        )

        reversal = mqii.get("reversal", {})
        reversal_signal = (
            reversal.get("reversal_signal", False)
            if isinstance(reversal, Mapping)
            else False
        )
        context_stability = "UNKNOWN"
        if global_state != "UNKNOWN":
            context_stability = "TRANSITION" if reversal_signal else "STABLE"

        premium_context = (
            "OBSERVED"
            if any(self._contains_token(payload, "PREMIUM") for payload in sources.values())
            else "NOT_OBSERVED"
        )

        return {
            "global_context_state": global_state,
            "context_stability": context_stability,
            "specialized_alignment": specialized_alignment,
            "premium_context": premium_context,
            "observed_mqii_states": observed_states,
        }

    # Conflict Resolver
    def _resolve_conflicts(
        self,
        sources: Mapping[str, Dict[str, Any]],
        interpretation: Mapping[str, Any],
    ) -> Tuple[ALOGovernorConflictReport, ...]:
        observed_states = dict(interpretation.get("observed_mqii_states", {}) or {})
        if len(set(observed_states.values())) <= 1:
            return ()

        return (
            ALOGovernorConflictReport(
                conflict_id=uuid.uuid4().hex,
                symbol=self._resolve_symbol(sources),
                sources=tuple(sorted(observed_states)),
                conflict_type="MQII_STATE_DIVERGENCE",
                observed_values=copy.deepcopy(observed_states),
                authority_owner="MQII",
                interpretation=(
                    "Specialized snapshots expose divergent MQII state values; "
                    "MQII remains the authority owner."
                ),
                severity="INFO",
                no_effect=True,
                operational_effect_count=0,
            ),
        )

    # Guidance Builder
    def _build_guidance(
        self,
        symbol: str,
        cycle_id: str,
        timestamp: str,
        normalized: Mapping[str, Dict[str, Any]],
        interpretation: Mapping[str, Any],
        conflicts: Iterable[ALOGovernorConflictReport],
        missing_sources: Tuple[str, ...],
        invalid_sources: Tuple[str, ...],
    ) -> ALOGovernorGuidance:
        conflict_items = tuple(conflicts)
        global_state = str(interpretation.get("global_context_state", "UNKNOWN"))
        premium_context = str(interpretation.get("premium_context", "NOT_OBSERVED"))

        if not normalized:
            interpretation_label = "INSUFFICIENT_CONTEXT"
        elif conflict_items:
            interpretation_label = "CONTEXT_DIVERGENT"
        elif premium_context == "OBSERVED":
            interpretation_label = "PREMIUM_CONTEXT_OBSERVED"
        else:
            interpretation_label = "CONTEXT_ALIGNED"

        reason_codes = [
            f"AVAILABLE_SOURCES={len(normalized)}",
            f"GLOBAL_CONTEXT_STATE={global_state}",
            f"SPECIALIZED_ALIGNMENT={interpretation.get('specialized_alignment', 'UNKNOWN')}",
            f"CONFLICTS={len(conflict_items)}",
            "READ_ONLY_NO_EFFECT",
        ]
        reason_codes.extend(f"MISSING_SOURCE={source}" for source in missing_sources)
        reason_codes.extend(f"INVALID_SOURCE={source}" for source in invalid_sources)

        caution_level = self._describe_caution(global_state)
        return ALOGovernorGuidance(
            guidance_id=uuid.uuid4().hex,
            cycle_id=cycle_id,
            symbol=symbol,
            timestamp=timestamp,
            global_context_state=global_state,
            context_stability=str(
                interpretation.get("context_stability", "UNKNOWN")
            ),
            specialized_alignment=str(
                interpretation.get("specialized_alignment", "UNKNOWN")
            ),
            conflict_level="OBSERVED" if conflict_items else "NONE",
            premium_context=premium_context,
            aggressiveness_guidance="OBSERVE_ONLY",
            caution_level=caution_level,
            interpretation_label=interpretation_label,
            reason_codes=tuple(reason_codes),
            explainability=(
                "Passive interpretation of supplied read-only specialized snapshots. "
                "No operational action is authorized."
            ),
            missing_sources=missing_sources,
            source_summary=self._build_source_summary(normalized),
            no_effect=True,
            operational_effect_count=0,
        )

    # Constitutional Guard
    def _constitutional_guard(
        self, guidance: ALOGovernorGuidance
    ) -> ALOGovernorGuidance:
        return replace(
            guidance,
            aggressiveness_guidance="OBSERVE_ONLY",
            mode=READ_ONLY_MODE,
            no_effect=True,
            operational_effect_count=0,
        )

    def _guard_snapshot(
        self, snapshot: ALOGovernorContextSnapshot
    ) -> ALOGovernorContextSnapshot:
        return replace(
            snapshot,
            mode=READ_ONLY_MODE,
            no_effect=True,
            operational_effect_count=0,
        )

    def _build_global_context(
        self,
        sources: Mapping[str, Dict[str, Any]],
        interpretation: Mapping[str, Any],
    ) -> Dict[str, Any]:
        return {
            "state": interpretation.get("global_context_state", "UNKNOWN"),
            "stability": interpretation.get("context_stability", "UNKNOWN"),
            "alignment": interpretation.get("specialized_alignment", "UNKNOWN"),
            "premium_context": interpretation.get("premium_context", "NOT_OBSERVED"),
            "mqii": copy.deepcopy(sources.get("MQII", {})),
            "system": copy.deepcopy(sources.get("SYSTEM", {})),
            "no_effect": True,
            "operational_effect_count": 0,
        }

    def _build_local_contexts(
        self, sources: Mapping[str, Dict[str, Any]], symbol: str
    ) -> Dict[str, Dict[str, Any]]:
        if not symbol:
            return {}

        local = {}
        for source, payload in sources.items():
            payload_symbol = self._safe_upper(payload.get("symbol"))
            if payload_symbol == symbol:
                local[source] = copy.deepcopy(payload)
        return {symbol: local} if local else {}

    def _build_source_freshness(
        self, sources: Mapping[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        freshness = {}
        for source, payload in sources.items():
            freshness[source] = (
                payload.get("timestamp")
                or payload.get("generated_at")
                or payload.get("updated_at")
                or "UNKNOWN"
            )
        return freshness

    def _build_source_summary(
        self, sources: Mapping[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        return {
            source: {
                "source": payload.get("source", source),
                "timestamp": (
                    payload.get("timestamp")
                    or payload.get("generated_at")
                    or payload.get("updated_at")
                    or ""
                ),
                "mode": READ_ONLY_MODE,
                "no_effect": True,
                "operational_effect_count": 0,
            }
            for source, payload in sorted(sources.items())
        }

    def _collect_mqii_states(
        self, sources: Mapping[str, Dict[str, Any]]
    ) -> Dict[str, str]:
        states = {}
        for source, payload in sources.items():
            value = payload.get("mqii_state")
            if source == "MQII":
                value = payload.get("state") or value
            safe_value = self._safe_upper(value)
            if safe_value:
                states[source] = safe_value
        return states

    def _resolve_symbol(self, sources: Mapping[str, Dict[str, Any]]) -> str:
        for payload in sources.values():
            symbol = self._safe_upper(payload.get("symbol"))
            if symbol:
                return symbol
        return ""

    def _snapshot_to_dict(self, snapshot: Any) -> Dict[str, Any] | None:
        try:
            if isinstance(snapshot, Mapping):
                return copy.deepcopy(dict(snapshot))
            if is_dataclass(snapshot):
                return copy.deepcopy(asdict(snapshot))
            if hasattr(snapshot, "__dict__"):
                return copy.deepcopy(vars(snapshot))
        except Exception:
            return None
        return None

    def _contains_token(self, value: Any, token: str) -> bool:
        safe_token = self._safe_upper(token)
        if isinstance(value, Mapping):
            return any(self._contains_token(item, safe_token) for item in value.values())
        if isinstance(value, (list, tuple, set, frozenset)):
            return any(self._contains_token(item, safe_token) for item in value)
        return safe_token in self._safe_upper(value)

    def _describe_caution(self, global_state: str) -> str:
        state = self._safe_upper(global_state)
        if state == "NO_TRADE":
            return "HIGH"
        if state == "CAUTIOUS":
            return "MEDIUM"
        if state in ("TRADE_OK", "AGGRESSIVE_OK"):
            return "LOW"
        return "UNKNOWN"

    def _safe_upper(self, value: Any) -> str:
        return str(value or "").strip().upper()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
