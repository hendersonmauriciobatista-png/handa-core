"""Database-free falsifiers for the frozen decision-ledger physical contract."""

import inspect
from pathlib import Path

from core.persistence.live_order_store import LiveOrderStore, live_order_resource_scope


ROOT = Path(__file__).parents[1]
MIGRATION_003 = ROOT / "core" / "persistence" / "migrations" / "003_reconciliation_evidence.sql"
MIGRATION_004 = ROOT / "core" / "persistence" / "migrations" / "004_external_order_observation_contract.sql"
MIGRATION_005 = ROOT / "core" / "persistence" / "migrations" / "005_decision_ledger.sql"


def resources():
    return {
        resource.table: resource
        for resource in live_order_resource_scope().resources
    }


def columns(resource):
    return resource.readable_columns | resource.writable_columns


def reconciliation_columns():
    return columns(resources()["reconciliation"])


def decision_columns():
    return columns(resources()["semantic_decision"])


def test_pr001_distinct_reconciliation_context_capability_is_missing():
    assert any("context_id" in columns(resource) for resource in resources().values())


def test_pr002_context_sequence_capability_is_missing():
    assert any(
        {"intent_id", "context_sequence"} <= columns(resource)
        for resource in resources().values()
    )


def test_pr003_active_context_capability_is_missing():
    assert any(
        {"intent_id", "context_state"} <= columns(resource)
        for resource in resources().values()
    )


def test_pr004_distinct_semantic_decision_capability_is_missing():
    assert any("decision_id" in columns(resource) for resource in resources().values())


def test_pr005_decision_sequence_with_context_capability_is_missing():
    assert any(
        {"context_id", "decision_sequence"} <= columns(resource)
        for resource in resources().values()
    )


def test_pr006_governed_append_only_semantic_decision_capability_is_missing():
    assert any("decision_id" in columns(resource) for resource in resources().values())
    assert "update_if_version" not in inspect.getsource(
        LiveOrderStore.append_reconciliation_decision
    )


def test_pr007_exact_semantic_proposition_set_is_missing():
    assert {
        "decision_scope",
        "execution_occurred",
        "order_outcome_terminal",
        "execution_extent",
        "final_partial_outcome",
        "unknown_reason",
        "contradiction_result",
    } <= decision_columns()


def test_pr008_three_semantic_version_bindings_are_missing():
    assert {
        "authority_contract_version",
        "decision_schema_version",
        "evidence_normalization_version",
    } <= decision_columns()


def test_pr009_lineage_status_representation_is_missing():
    assert "lineage_completeness_status" in decision_columns()


def test_pr010_typed_decision_evidence_parent_is_missing():
    assert any(
        {"decision_id", "evidence_kind", "semantic_role"} <= columns(resource)
        for resource in resources().values()
    )


def test_pr011_exchange_observation_decision_reference_is_missing():
    migration = MIGRATION_005.read_text(encoding="utf-8")
    assert "EXCHANGE_OBSERVATION" in migration
    assert "evidence_id" in migration


def test_pr012_normalized_revision_decision_reference_is_missing():
    migration = MIGRATION_005.read_text(encoding="utf-8")
    assert "decision_id" in migration and "normalized_revision_id" in migration


def test_pr013_trade_fill_decision_reference_is_missing():
    migration = MIGRATION_005.read_text(encoding="utf-8")
    assert "TRADE_FILL" in migration and "exchange_trade_id" in migration


def test_pr014_contradiction_basis_reference_is_missing():
    migration = MIGRATION_005.read_text(encoding="utf-8")
    assert "CONTRADICTION_BASIS" in migration and "semantic_role" in migration


def test_pr015_minimum_evaluated_snapshot_is_missing():
    assert "evaluated_input_snapshot" in decision_columns()


def test_pr016_attempt_context_association_is_missing():
    assert "context_id" in columns(resources()["submission_attempt"])


def test_pr017_projection_is_not_backed_by_distinct_immutable_ledger():
    assert any("decision_id" in columns(resource) for resource in resources().values())


def test_pr018_store_exposes_all_migration_004_structured_fields():
    fields = {
        "client_order_id_observed",
        "order_type",
        "time_in_force",
        "orig_qty",
        "orig_quote_order_qty",
        "executed_qty",
        "cumulative_quote_qty",
        "observation_class",
        "observation_source",
    }
    assert fields <= columns(resources()["exchange_evidence"])


def test_pr019_reconciliation_is_not_semantic_decision_and_lineage_is_not_complete():
    assert "decision_id" not in reconciliation_columns()
    migration = MIGRATION_003.read_text(encoding="utf-8")
    assert "evidence_kind" not in migration
    assert "exchange_trade_id" not in migration


def test_pr020_no_synthetic_decision_or_lineage_backfill_capability_exists():
    assert "decision_id" in decision_columns()
    assert "backfill" not in MIGRATION_005.read_text(encoding="utf-8").lower()
