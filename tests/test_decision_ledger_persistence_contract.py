"""Contract falsifiers for the immutable semantic decision ledger.

These tests are intentionally database-free.  They inspect the currently
published persistence boundary without creating schema, Store methods, or
compatibility shims.
"""

from pathlib import Path

from core.persistence.live_order_store import LiveOrderStore, live_order_resource_scope
from core.persistence.transaction_context import ImmutableRow


MIGRATION_005 = (
    Path(__file__).parents[1]
    / "core"
    / "persistence"
    / "migrations"
    / "005_decision_ledger.sql"
)


def resource_tables():
    return {
        spec.table: spec
        for spec in live_order_resource_scope().resources
    }


def decision_columns():
    decision = resource_tables()["semantic_decision"]
    return decision.readable_columns | decision.writable_columns


def test_existing_reconciliation_capabilities_are_recorded():
    columns = resource_tables()["reconciliation"].readable_columns

    assert {"reconciliation_id", "intent_id", "decision_sequence"} <= columns
    assert {"reconciliation_state", "execution_certainty"} <= columns
    assert "decision_reason" in columns


def test_distinct_immutable_decision_entity_is_available():
    tables = resource_tables()

    assert "semantic_decision" in tables
    assert {"decision_id", "reconciliation_id"} <= (
        tables["semantic_decision"].readable_columns
        | tables["semantic_decision"].writable_columns
    )


def test_reconciliation_persists_scope_and_exact_proposition_results():
    columns = decision_columns()

    assert "decision_scope" in columns
    assert {
        "execution_occurred",
        "order_outcome_terminal",
        "execution_extent",
        "final_partial_outcome",
        "unknown_reason",
        "contradiction_result",
    } <= columns


def test_typed_lineage_supports_all_evidence_categories():
    tables = resource_tables()
    migration = MIGRATION_005.read_text(encoding="utf-8")

    assert "decision_evidence_reference" in tables
    lineage_columns = (
        tables["decision_evidence_reference"].readable_columns
        | tables["decision_evidence_reference"].writable_columns
    )
    assert "evidence_kind" in lineage_columns
    assert "semantic_role" in lineage_columns
    assert "decision_exchange_observation_ref" in migration
    assert "decision_normalized_revision_ref" in migration
    assert "decision_trade_fill_ref" in migration
    assert "decision_contradiction_basis_ref" in migration
    assert "evidence_id" in migration
    assert "normalized_revision_id" in migration
    assert "exchange_trade_id" in migration
    assert "TRADE_FILL" in migration
    assert "CONTRADICTION_BASIS" in migration


def test_decision_binds_all_required_semantic_versions():
    columns = decision_columns()

    assert {
        "authority_contract_version",
        "decision_schema_version",
        "evidence_normalization_version",
    } <= columns


def test_decision_has_minimum_evaluated_input_snapshot_contract():
    columns = decision_columns()

    assert "evaluated_input_snapshot" in columns
    assert "lineage_completeness_status" in columns


def test_history_api_creates_immutable_semantic_decisions():
    assert hasattr(LiveOrderStore, "append_semantic_decision")
    assert not hasattr(LiveOrderStore, "update_semantic_decision")
    assert not hasattr(LiveOrderStore, "delete_semantic_decision")


class _LedgerContextDouble:
    def __init__(self):
        self.inserted = []
        self.updated = []
        self.allocate_calls = []
        self._next = 0

    def allocate_next_sequence(self, *args):
        self.allocate_calls.append(args)
        self._next += 1
        return self._next

    def insert_returning(self, table, values, columns):
        self.inserted.append((table, dict(values)))
        return ImmutableRow(values)

    def insert(self, table, values):
        self.inserted.append((table, dict(values)))

    def update_if_version(self, table, keys, version, changes, columns):
        self.updated.append((table, dict(keys), version, dict(changes)))
        return ImmutableRow(changes)

    def read_by_key(self, *args):
        return None


def _decision(decision_id):
    return {
        "decision_id": decision_id,
        "context_id": "ctx-1",
        "intent_id": "intent-1",
        "evaluation_time": "2026-01-01T00:00:00Z",
        "decision_scope": "ORDER_OUTCOME",
        "authority_state": "PENDING",
        "execution_occurred": "UNKNOWN",
        "order_outcome_terminal": "UNKNOWN",
        "execution_extent": "UNKNOWN",
        "final_partial_outcome": "UNKNOWN",
        "evaluated_input_snapshot": {"source": "test"},
        "authority_contract_version": "v1",
        "decision_schema_version": "v1",
        "evidence_normalization_version": "v1",
        "lineage_completeness_status": "LINEAGE_INCOMPLETE",
    }


def test_semantic_decision_append_does_not_mutate_prior_decisions():
    store = LiveOrderStore.__new__(LiveOrderStore)
    context = _LedgerContextDouble()
    store._run = lambda operation: operation(context)

    store.append_semantic_decision(decision=_decision("d-1"))
    store.append_semantic_decision(decision=_decision("d-2"))

    decision_rows = [row for row in context.inserted if row[0] == "semantic_decision"]
    assert [row[1]["decision_id"] for row in decision_rows] == ["d-1", "d-2"]
    assert [row[1]["decision_sequence"] for row in decision_rows] == [1, 2]
    assert context.updated == []


def test_context_sequence_is_allocated_by_the_transaction_context():
    store = LiveOrderStore.__new__(LiveOrderStore)
    context = _LedgerContextDouble()
    store._run = lambda operation: operation(context)

    store.create_reconciliation_context(
        context_id="ctx-1", intent_id="intent-1"
    )

    assert context.allocate_calls == [
        (
            "reconciliation_context",
            "intent_id",
            "intent-1",
            "context_sequence",
            "order_intent",
        )
    ]
    assert context.inserted[0][1]["context_sequence"] == 1


def test_current_projection_mutation_is_separate_from_decision_append():
    store = LiveOrderStore.__new__(LiveOrderStore)
    context = _LedgerContextDouble()
    store._run = lambda operation: operation(context)

    store.append_semantic_decision(decision=_decision("d-1"), expected_version=4)

    assert context.updated == [
        (
            "order_intent",
            {"intent_id": "intent-1"},
            4,
            {"current_context_id": "ctx-1", "current_decision_id": "d-1"},
        )
    ]


def test_lineage_completeness_is_explicitly_evaluable():
    assert hasattr(LiveOrderStore, "evaluate_lineage_completeness")


def test_migration_004_structured_fields_are_exposed_by_store_scope():
    evidence = resource_tables()["exchange_evidence"]
    columns = evidence.readable_columns | evidence.writable_columns
    required = {
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

    assert required <= columns


def test_migration_004_defines_the_structured_observation_facts():
    migration = (Path(__file__).parents[1] / "core" / "persistence" / "migrations" / "004_external_order_observation_contract.sql").read_text(encoding="utf-8")

    for field in (
        "client_order_id_observed",
        "order_type",
        "time_in_force",
        "orig_qty",
        "orig_quote_order_qty",
        "executed_qty",
        "cumulative_quote_qty",
        "observation_class",
        "observation_source",
    ):
        assert f"ADD COLUMN {field}" in migration
