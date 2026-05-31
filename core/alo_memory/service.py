from typing import Optional, Set, Tuple

from core.alo_memory.builder import ALOMemoryBuilder
from core.alo_memory.models import ALOMemorySnapshot


class ALOMemoryReadOnlyService:
    """
    Read-only facade for ALOMemory snapshots and observability.

    The service keeps all effects at zero and is intentionally not registered in
    the main runtime by this phase.
    """

    def __init__(
        self,
        builder: Optional[ALOMemoryBuilder] = None,
        max_divergence_logs: int = 10,
        emit_unchanged_snapshot_logs: bool = False,
    ) -> None:
        self.builder = builder or ALOMemoryBuilder()
        self.max_divergence_logs = int(max_divergence_logs)
        self.emit_unchanged_snapshot_logs = bool(emit_unchanged_snapshot_logs)
        self.last_snapshot: Optional[ALOMemorySnapshot] = None
        self._logged_divergence_keys: Set[Tuple[str, str, str]] = set()
        self._last_snapshot_signature: Optional[Tuple[int, int]] = None

    def build_snapshot(self, emit_logs: bool = True) -> ALOMemorySnapshot:
        snapshot = self.builder.build_snapshot()
        self.last_snapshot = snapshot
        if emit_logs:
            self._emit_snapshot_logs(snapshot)
        return snapshot

    def get_last_snapshot(self) -> Optional[ALOMemorySnapshot]:
        return self.last_snapshot

    def _emit_snapshot_logs(self, snapshot: ALOMemorySnapshot) -> None:
        signature = (snapshot.profiles_count, len(snapshot.divergences))
        should_log_snapshot = (
            self.emit_unchanged_snapshot_logs
            or self._last_snapshot_signature != signature
        )

        if should_log_snapshot:
            print(
                "[ALO MEMORY] "
                f"mode={snapshot.mode} | "
                f"no_effect={str(snapshot.no_effect).lower()} | "
                f"operational_effect_count={snapshot.operational_effect_count} | "
                f"sources={snapshot.source_event_counts}"
            )
            print(
                "[ALO MEMORY SNAPSHOT] "
                f"profiles={snapshot.profiles_count} | "
                f"divergences={len(snapshot.divergences)} | "
                "no_effect=true | operational_effect_count=0"
            )
            self._last_snapshot_signature = signature

        emitted = 0
        for divergence in snapshot.divergences:
            key = (
                divergence.symbol,
                divergence.field,
                divergence.reference_source,
            )
            if key in self._logged_divergence_keys:
                continue

            print(
                "[ALO MEMORY DIVERGENCE] "
                f"symbol={divergence.symbol} | "
                f"field={divergence.field} | "
                f"projected={divergence.projected} | "
                f"reference={divergence.reference} | "
                f"source={divergence.reference_source} | "
                f"severity={divergence.severity} | "
                f"reason={divergence.reason} | "
                "no_effect=true | operational_effect_count=0"
            )
            self._logged_divergence_keys.add(key)
            emitted += 1
            if emitted >= self.max_divergence_logs:
                break
