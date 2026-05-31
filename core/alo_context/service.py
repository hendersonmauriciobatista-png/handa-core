from typing import Optional, Set, Tuple

from core.alo_context.builder import ALOContextBuilder
from core.alo_context.models import ALOContextSnapshot


class ALOContextReadOnlyService:
    """
    Read-only facade for ALOContext snapshots and observability.

    The service is intentionally not registered in the main runtime in Phase 2.
    """

    def __init__(
        self,
        builder: Optional[ALOContextBuilder] = None,
        max_divergence_logs: int = 10,
        emit_unchanged_snapshot_logs: bool = False,
    ) -> None:
        self.builder = builder or ALOContextBuilder()
        self.max_divergence_logs = int(max_divergence_logs)
        self.emit_unchanged_snapshot_logs = bool(emit_unchanged_snapshot_logs)
        self.last_snapshot: Optional[ALOContextSnapshot] = None
        self._logged_divergence_keys: Set[Tuple[str, str, str, str]] = set()
        self._last_snapshot_signature: Optional[Tuple[int, int, int, int]] = None

    def build_snapshot(self, emit_logs: bool = True, **kwargs) -> ALOContextSnapshot:
        snapshot = self.builder.build_snapshot(**kwargs)
        self.last_snapshot = snapshot
        if emit_logs:
            self._emit_snapshot_logs(snapshot)
        return snapshot

    def get_last_snapshot(self) -> Optional[ALOContextSnapshot]:
        return self.last_snapshot

    def _emit_snapshot_logs(self, snapshot: ALOContextSnapshot) -> None:
        signature = (
            len(snapshot.global_context),
            len(snapshot.local_contexts),
            len(snapshot.missing_sources),
            len(snapshot.divergences),
        )
        should_log_snapshot = (
            self.emit_unchanged_snapshot_logs
            or self._last_snapshot_signature != signature
        )

        if should_log_snapshot:
            print(
                "[ALO CONTEXT] "
                f"mode={snapshot.mode} | "
                f"no_effect={str(snapshot.no_effect).lower()} | "
                f"operational_effect_count={snapshot.operational_effect_count} | "
                f"sources={len(snapshot.sources)} | "
                f"cycle_id={snapshot.cycle_id}"
            )
            print(
                "[ALO CONTEXT SNAPSHOT] "
                f"global_fields={len(snapshot.global_context)} | "
                f"local_contexts={len(snapshot.local_contexts)} | "
                f"missing_sources={len(snapshot.missing_sources)} | "
                f"divergences={len(snapshot.divergences)} | "
                "no_effect=true | operational_effect_count=0"
            )
            self._last_snapshot_signature = signature

        emitted = 0
        for divergence in snapshot.divergences:
            key = (
                str(divergence.get("scope", "")),
                str(divergence.get("field", "")),
                str(divergence.get("source_a", "")),
                str(divergence.get("source_b", "")),
            )
            if key in self._logged_divergence_keys:
                continue

            print(
                "[ALO CONTEXT DIVERGENCE] "
                f"scope={divergence.get('scope', '')} | "
                f"field={divergence.get('field', '')} | "
                f"source_a={divergence.get('source_a', '')} | "
                f"value_a={divergence.get('value_a', '')} | "
                f"source_b={divergence.get('source_b', '')} | "
                f"value_b={divergence.get('value_b', '')} | "
                f"reason={divergence.get('reason', '')} | "
                "no_effect=true | operational_effect_count=0"
            )
            self._logged_divergence_keys.add(key)
            emitted += 1
            if emitted >= self.max_divergence_logs:
                break
