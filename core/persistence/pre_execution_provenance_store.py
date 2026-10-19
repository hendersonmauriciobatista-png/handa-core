"""Least-authority persistence for immutable pre-execution provenance."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, Optional

from psycopg2.extras import Json

from core.execution.authority_digest import canonical_decimal, canonical_timestamp
from core.execution.pre_execution_provenance_artifact import PreExecutionProvenanceArtifact
from core.persistence.persistence_coordinator import PersistenceCoordinator
from core.persistence.transaction_context import ImmutablePage, ImmutableRow, Predicate, PredicateOperator, ResourceScope, ResourceSpec, UniqueConflict


LIVE_SCHEMA = "handa_live"
PROVENANCE_COLUMNS = (
    "provenance_artifact_id", "candidate_evidence_identity", "symbol", "side",
    "source_group_timestamps", "source_group_digests", "source_group_intervals",
    "source_group_closure_statuses", "source_group_server_times",
    "source_group_constituent_digests", "source_group_identities",
    "source_group_constituents", "source_group_missing_evidence", "source_group_trust",
    "ticker_value", "ticker_application_receipt_at", "decision_produced_at",
    "requested_quote_amount", "dynamic_policy_evidence", "dynamic_risk_evidence",
    "decision_dynamic_evidence", "static_manifest_identity",
    "strategy_manifest_id", "policy_manifest_id", "risk_manifest_id",
    "configuration_manifest_id", "freshness_manifest_id", "binding_status",
    "canonical_semantic_digest", "recorded_at",
)


def pre_execution_provenance_resource_scope() -> ResourceScope:
    resource = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="pre_execution_provenance_artifact",
        readable_columns=frozenset(PROVENANCE_COLUMNS),
        writable_columns=frozenset(column for column in PROVENANCE_COLUMNS if column != "recorded_at"),
        key_columns=frozenset({"provenance_artifact_id"}),
        ordering_columns=("recorded_at", "provenance_artifact_id"),
    )
    return ResourceScope((resource,))


class PreExecutionProvenanceStore:
    def __init__(self, coordinator: PersistenceCoordinator):
        self._coordinator = coordinator

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, datetime):
            return canonical_timestamp(value)
        if isinstance(value, Decimal):
            return canonical_decimal(value)
        if isinstance(value, Mapping):
            return {str(key): PreExecutionProvenanceStore._json_safe(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [PreExecutionProvenanceStore._json_safe(item) for item in value]
        if isinstance(value, (set, frozenset)):
            return [PreExecutionProvenanceStore._json_safe(item) for item in sorted(value, key=repr)]
        return str(value) if type(value) is not str and isinstance(value, str) else value

    @staticmethod
    def _values(artifact: PreExecutionProvenanceArtifact) -> dict:
        values = artifact.as_record()
        values.pop("recorded_at", None)
        for field in (
            "source_group_timestamps", "source_group_digests", "source_group_intervals",
            "source_group_closure_statuses", "source_group_server_times",
            "source_group_constituent_digests", "source_group_identities",
            "source_group_constituents", "source_group_missing_evidence", "source_group_trust",
            "dynamic_policy_evidence", "dynamic_risk_evidence",
            "decision_dynamic_evidence", "static_manifest_identity",
        ):
            values[field] = Json(PreExecutionProvenanceStore._json_safe(values[field]))
        return values

    def persist(self, artifact: PreExecutionProvenanceArtifact) -> ImmutableRow:
        values = self._values(artifact)
        try:
            with self._coordinator.transaction() as context:
                return context.insert_returning(
                    "pre_execution_provenance_artifact", values, PROVENANCE_COLUMNS
                )
        except UniqueConflict:
            return self.get(artifact.candidate_id)

    def get(self, provenance_artifact_id: str) -> ImmutableRow:
        with self._coordinator.transaction() as context:
            row = context.read_by_key(
                "pre_execution_provenance_artifact",
                {"provenance_artifact_id": provenance_artifact_id},
                PROVENANCE_COLUMNS,
            )
        if row is None:
            raise ValueError("provenance artifact replay row is missing")
        return row

    def get_artifact(self, provenance_artifact_id: str) -> PreExecutionProvenanceArtifact:
        return PreExecutionProvenanceArtifact.from_record(
            self.get(provenance_artifact_id)
        )

    def list_for_symbol(self, symbol: str, *, limit: int = 100, cursor: Optional[str] = None) -> ImmutablePage:
        with self._coordinator.transaction() as context:
            return context.enumerate(
                "pre_execution_provenance_artifact",
                (Predicate("symbol", PredicateOperator.EQ, symbol),),
                PROVENANCE_COLUMNS,
                limit,
                cursor,
            )
