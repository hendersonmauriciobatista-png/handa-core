from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple

from core.alo_context.models import ALOContextSnapshot, ALOContextSource
from core.alo_context.providers import ALOContextProvider


class ALOContextBuilder:
    """
    Builds a read-only context snapshot from passive providers.

    This builder does not register consumers, create gates, mutate runtime state,
    alter score, alter capital, alter ranking, or alter selection.
    """

    def __init__(
        self,
        providers: Iterable[ALOContextProvider] | None = None,
        expected_sources: Iterable[str] | None = None,
    ) -> None:
        self.providers = list(providers or [])
        self.expected_sources = tuple(str(item) for item in (expected_sources or ()))

    def build_snapshot(
        self,
        cycle_id: str = "",
        global_context: Dict[str, Any] | None = None,
        local_contexts: Dict[str, Dict[str, Any]] | None = None,
        position_context: Dict[str, Any] | None = None,
        system_context: Dict[str, Any] | None = None,
    ) -> ALOContextSnapshot:
        sources = self._collect_sources()

        global_payload = self._normalize_payload(global_context)
        local_payloads = self._normalize_local_contexts(local_contexts)
        position_payload = self._normalize_payload(position_context)
        system_payload = self._normalize_payload(system_context)

        self._merge_sources(
            sources=sources,
            global_context=global_payload,
            local_contexts=local_payloads,
            position_context=position_payload,
            system_context=system_payload,
        )

        divergences = self._build_divergences(sources)
        self._mark_global_divergent_fields(global_payload, divergences)
        missing_sources = self._build_missing_sources(sources)
        freshness = {
            source.name: source.freshness_seconds
            for source in sources
            if source.freshness_seconds is not None
        }
        summary = {
            "global_fields": len(global_payload),
            "local_contexts": len(local_payloads),
            "position_fields": len(position_payload),
            "system_fields": len(system_payload),
            "sources": len(sources),
            "missing_sources": len(missing_sources),
            "divergences": len(divergences),
            "mode": "READ_ONLY",
            "no_effect": True,
            "operational_effect_count": 0,
        }

        return ALOContextSnapshot(
            cycle_id=str(cycle_id or ""),
            timestamp=self._now_iso(),
            global_context=global_payload,
            local_contexts=local_payloads,
            position_context=position_payload,
            system_context=system_payload,
            sources=tuple(sources),
            divergences=tuple(divergences),
            freshness=freshness,
            missing_sources=tuple(missing_sources),
            summary=summary,
            no_effect=True,
            operational_effect_count=0,
        )

    def _collect_sources(self) -> List[ALOContextSource]:
        sources: List[ALOContextSource] = []
        for provider in self.providers:
            try:
                source = provider.collect()
                if not isinstance(source, ALOContextSource):
                    raise TypeError(
                        f"provider.collect() returned {type(source).__name__}"
                    )
            except Exception as exc:
                source = ALOContextSource(
                    name=str(getattr(provider, "name", "unknown")),
                    source_type=str(getattr(provider, "source_type", "UNKNOWN")),
                    scope=str(getattr(provider, "scope", "GLOBAL")),
                    timestamp=self._now_iso(),
                    available=False,
                    error=str(exc),
                    no_effect=True,
                    operational_effect_count=0,
                )
            sources.append(source)
        return sources

    def _merge_sources(
        self,
        sources: Iterable[ALOContextSource],
        global_context: Dict[str, Any],
        local_contexts: Dict[str, Dict[str, Any]],
        position_context: Dict[str, Any],
        system_context: Dict[str, Any],
    ) -> None:
        for source in sources:
            if not source.available:
                continue
            payload = self._normalize_payload(source.payload)
            scope = str(source.scope or "GLOBAL").upper()

            if scope == "LOCAL":
                symbol = self._safe_symbol(payload.get("symbol") or payload.get("pair"))
                if symbol:
                    local_contexts.setdefault(symbol, {}).update(payload)
                continue

            if scope == "POSITION":
                position_context.update(payload)
                continue

            if scope == "SYSTEM":
                system_context.update(payload)
                continue

            if scope == "MIXED":
                self._merge_mixed_payload(payload, global_context, local_contexts)
                continue

            global_context.update(payload)

    def _merge_mixed_payload(
        self,
        payload: Dict[str, Any],
        global_context: Dict[str, Any],
        local_contexts: Dict[str, Dict[str, Any]],
    ) -> None:
        local_items = payload.get("local_contexts")
        if isinstance(local_items, dict):
            for symbol, local_payload in local_items.items():
                safe_symbol = self._safe_symbol(symbol)
                if safe_symbol and isinstance(local_payload, dict):
                    local_contexts.setdefault(safe_symbol, {}).update(
                        self._normalize_payload(local_payload)
                    )

        for key, value in payload.items():
            if key == "local_contexts":
                continue
            global_context[str(key)] = value

    def _build_missing_sources(
        self, sources: Iterable[ALOContextSource]
    ) -> List[str]:
        available = {source.name for source in sources if source.available}
        missing = [name for name in self.expected_sources if name not in available]
        for source in sources:
            if not source.available:
                missing.append(source.name)
        return sorted(set(missing))

    def _build_divergences(
        self, sources: Iterable[ALOContextSource]
    ) -> List[Dict[str, Any]]:
        observed: Dict[Tuple[str, str, str], Tuple[str, Any]] = {}
        divergences: List[Dict[str, Any]] = []

        for source in sources:
            if not source.available:
                continue
            scope = str(source.scope or "GLOBAL").upper()
            if scope not in ("GLOBAL", "POSITION", "SYSTEM", "LOCAL", "MIXED"):
                continue

            for scope_key, symbol, field, value in self._iter_scalar_context_values(
                source
            ):
                key = (scope_key, symbol, field)
                if key not in observed:
                    observed[key] = (source.name, value)
                    continue

                previous_source, previous_value = observed[key]
                if self._normalize_scalar(previous_value) == self._normalize_scalar(
                    value
                ):
                    continue

                divergence = {
                    "scope": scope_key,
                    "field": field,
                    "source_a": previous_source,
                    "value_a": previous_value,
                    "source_b": source.name,
                    "value_b": value,
                    "severity": "INFO",
                    "reason": "CONTEXT_SOURCE_DIVERGENCE",
                    "no_effect": True,
                    "operational_effect_count": 0,
                }
                if symbol:
                    divergence["symbol"] = symbol
                    divergence["reason"] = "LOCAL_CONTEXT_SOURCE_DIVERGENCE"
                divergences.append(divergence)

        return divergences

    def _iter_scalar_context_values(
        self, source: ALOContextSource
    ) -> Iterable[Tuple[str, str, str, Any]]:
        scope = str(source.scope or "GLOBAL").upper()
        payload = source.payload if isinstance(source.payload, dict) else {}

        if scope == "LOCAL":
            symbol = self._safe_symbol(payload.get("symbol") or payload.get("pair"))
            if not symbol:
                return
            for field, value in payload.items():
                if str(field) in ("symbol", "pair"):
                    continue
                if isinstance(value, (dict, list, tuple, set)):
                    continue
                yield ("LOCAL", symbol, str(field), value)
            return

        if scope == "MIXED":
            local_contexts = payload.get("local_contexts")
            if isinstance(local_contexts, dict):
                for raw_symbol, local_payload in local_contexts.items():
                    symbol = self._safe_symbol(raw_symbol)
                    if not symbol or not isinstance(local_payload, dict):
                        continue
                    for field, value in local_payload.items():
                        if isinstance(value, (dict, list, tuple, set)):
                            continue
                        yield ("LOCAL", symbol, str(field), value)

            for field, value in payload.items():
                if field == "local_contexts":
                    continue
                if isinstance(value, (dict, list, tuple, set)):
                    continue
                yield ("GLOBAL", "", str(field), value)
            return

        for field, value in payload.items():
            if isinstance(value, (dict, list, tuple, set)):
                continue
            yield (scope, "", str(field), value)

    def _mark_global_divergent_fields(
        self, global_context: Dict[str, Any], divergences: Iterable[Dict[str, Any]]
    ) -> None:
        values_by_field: Dict[str, Dict[str, Any]] = {}
        for divergence in divergences:
            if str(divergence.get("scope", "")).upper() != "GLOBAL":
                continue
            field = str(divergence.get("field", ""))
            if not field:
                continue
            values_by_source = values_by_field.setdefault(field, {})
            values_by_source[str(divergence.get("source_a", ""))] = divergence.get(
                "value_a"
            )
            values_by_source[str(divergence.get("source_b", ""))] = divergence.get(
                "value_b"
            )

        for field, values_by_source in values_by_field.items():
            global_context[field] = {
                "divergent": True,
                "values_by_source": dict(values_by_source),
                "selected_value": None,
                "reason": "CONTEXT_SOURCE_DIVERGENCE",
                "no_effect": True,
                "operational_effect_count": 0,
            }

    def _normalize_payload(self, payload: Dict[str, Any] | None) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        return {str(key): value for key, value in payload.items()}

    def _normalize_local_contexts(
        self, local_contexts: Dict[str, Dict[str, Any]] | None
    ) -> Dict[str, Dict[str, Any]]:
        if not isinstance(local_contexts, dict):
            return {}

        normalized: Dict[str, Dict[str, Any]] = {}
        for symbol, payload in local_contexts.items():
            safe_symbol = self._safe_symbol(symbol)
            if safe_symbol and isinstance(payload, dict):
                normalized[safe_symbol] = self._normalize_payload(payload)
        return normalized

    def _safe_symbol(self, value: Any) -> str:
        return str(value or "").strip().upper()

    def _normalize_scalar(self, value: Any) -> str:
        return str(value or "").strip().upper()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
