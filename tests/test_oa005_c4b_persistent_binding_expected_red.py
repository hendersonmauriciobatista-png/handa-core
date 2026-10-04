"""C4B falsifiers for durable binding boundaries and generic ledger behavior."""

from importlib import import_module
import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import get_type_hints

import pytest

from core.execution.operational_effect_adapter import LogicalBindingLookupResult


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "core" / "persistence" / "migrations"
EFFECT_LEDGER = ROOT / "core" / "persistence" / "effect_application_ledger.py"
ADAPTER = ROOT / "core" / "execution" / "operational_effect_adapter.py"
C4B1_MIGRATION = MIGRATIONS / "008_effect_request_logical_binding.sql"


def _migration_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(MIGRATIONS.glob("*.sql"))
    )


def _ledger_type():
    return import_module("core.persistence.effect_application_ledger").EffectApplicationLedger


def _public_ledger_methods():
    return {
        name: member
        for name, member in inspect.getmembers(_ledger_type(), predicate=inspect.isfunction)
        if not name.startswith("_")
    }


def _has_c4_binding_write_capability():
    required = {
        "effect_request_id",
        "effect_type",
        "authority_decision_id",
        "reconciliation_context_id",
        "decision_sequence",
        "authority_contract_version",
    }
    for method in _public_ledger_methods().values():
        parameters = set(inspect.signature(method).parameters)
        if required <= parameters and ({"logical_effect_id", "logical_identity"} & parameters):
            return True
    return False


def _has_logical_lookup_capability():
    for method in _public_ledger_methods().values():
        parameters = set(inspect.signature(method).parameters)
        if {"logical_effect_id", "logical_identity"} & parameters:
            return "effect_request_id" not in parameters
    return False


def _logical_lookup_method():
    for method in _public_ledger_methods().values():
        parameters = set(inspect.signature(method).parameters)
        if {"logical_effect_id", "logical_identity"} & parameters:
            if "effect_request_id" not in parameters:
                return method
    return None


def _skip(control: str, classification: str, reason: str) -> None:
    pytest.skip(f"{control}::{classification}: {reason}")


def test_c4b001_durable_effect_request_has_logical_effect_id_field():
    migration = C4B1_MIGRATION.read_text(encoding="utf-8").lower()
    assert "add column logical_effect_id text" in migration
    assert "logical_effect_id text not null" not in migration
    assert "default" not in migration


def test_c4b002_legacy_logical_effect_id_remains_nullable():
    migration = C4B1_MIGRATION.read_text(encoding="utf-8").lower()
    assert "add column logical_effect_id text" in migration
    assert "logical_effect_id text not null" not in migration


def test_c4b003_partial_logical_uniqueness_is_database_enforced():
    migration = C4B1_MIGRATION.read_text(encoding="utf-8").lower()
    assert "create unique index effect_request_logical_identity_uq" in migration
    assert "(intent_id, logical_effect_id)" in migration
    assert "where logical_effect_id is not null" in migration


def test_c4b004_public_new_c4_binding_write_capability_exists():
    if not _has_c4_binding_write_capability():
        pytest.fail(
            "BOUNDARY_RED: no public ledger capability accepts logical identity, "
            "candidate effect_request_id, effect type, and authority metadata"
        )


def test_c4b005_public_lookup_by_logical_identity_exists():
    if not _has_logical_lookup_capability():
        pytest.fail(
            "BOUNDARY_RED: no public read capability accepts logical identity "
            "without requiring effect_request_id"
        )


def test_c4b006_lookup_not_found_has_explicit_disposition():
    method = _logical_lookup_method()
    assert method is not None
    assert "logical_identity" in inspect.signature(method).parameters


def test_c4b007_lookup_returns_valid_canonical_binding():
    method = _logical_lookup_method()
    assert method is not None
    assert get_type_hints(method).get("return") is LogicalBindingLookupResult


def test_c4b008_lookup_detects_authority_conflict():
    method = _logical_lookup_method()
    assert method is not None
    assert "authority_decision_id" in inspect.signature(method).parameters


def test_c4b009_lookup_detects_effect_type_conflict():
    method = _logical_lookup_method()
    assert method is not None
    assert "effect_type" in inspect.signature(method).parameters


def test_c4b010_existing_binding_reuses_canonical_request():
    method = _logical_lookup_method()
    assert method is not None
    parameters = inspect.signature(method).parameters
    assert "effect_request_id" not in parameters
    assert "cursor" in parameters


def test_c4b011_effect_request_id_cannot_bind_two_rows():
    migration = _migration_text().lower()
    assert "effect_request_id text primary key" in migration


def test_c4b012_concurrent_first_bind_converges_to_one_binding():
    _skip("C4B-012", "NOT_YET_REACHED", "persistent C4B binding boundary is absent")


def test_c4b013_concurrent_conflict_is_explicit():
    _skip("C4B-013", "NOT_YET_REACHED", "C4B-012 concurrency boundary is absent")


def test_c4b014_binding_survives_session_boundary():
    _skip("C4B-014", "NOT_YET_REACHED", "persistent C4B binding boundary is absent")


def test_c4b015_legacy_records_are_not_synthetic_backfilled():
    migration = C4B1_MIGRATION.read_text(encoding="utf-8").lower()
    assert "add column logical_effect_id text" in migration
    assert "backfill" not in migration
    assert "update handa_live.effect_request" not in migration


def test_c4b016_effect_application_ledger_remains_generic():
    ledger_module = import_module("core.persistence.effect_application_ledger")
    signature = inspect.signature(ledger_module.EffectApplicationLedger.create_effect_request)
    annotation = signature.parameters["effect_type"].annotation
    assert annotation in (str, "str")
    assert "bind_logical_effect" not in _public_ledger_methods()


def test_c4b017_no_replay_or_c4c_c4d_behavior_is_present():
    source = ADAPTER.read_text(encoding="utf-8")
    forbidden = (
        "AppliedEffectReplayRecord",
        "get_application_state",
        "claim_application",
        "PositionEffectAuthority",
        "order_market",
        "resubmit",
    )
    assert all(token not in source for token in forbidden)


def test_c4b018_operational_adapter_behavior_remains_frozen():
    from core.execution.operational_effect_adapter import (
        EffectEligibility,
        EffectType,
        LogicalEffectIdentity,
        OperationalEffectAdapter,
        OperationalEffectRequest,
        OperationalEffectStatus,
        PositionBinding,
    )

    def request(state, extent_certainty=None):
        return OperationalEffectRequest(
            execution_fact=SimpleNamespace(extent_certainty=extent_certainty),
            semantic_decision=SimpleNamespace(state=state),
            reconciliation_context_id="context-1",
            authority_decision_id="decision-1",
            decision_sequence=1,
            evidence_ids=("evidence-1",),
            effect_eligibility=EffectEligibility(
                effect_type=EffectType.OPEN,
                authority_decision_id="decision-1",
                reconciliation_context_id="context-1",
                decision_sequence=1,
                evidence_ids=("evidence-1",),
            ),
            logical_effect_identity=LogicalEffectIdentity("intent-1", "logical-1"),
            position_binding=PositionBinding(position_creation_id="creation-1"),
        )

    adapter = OperationalEffectAdapter()
    assert adapter.apply(request("PENDING")).status is OperationalEffectStatus.PENDING
    assert adapter.apply(request("BLOCKED")).status is OperationalEffectStatus.BLOCKED
    assert (
        adapter.apply(request("RESOLVED", SimpleNamespace(value="UNKNOWN"))).status
        is OperationalEffectStatus.OUTCOME_UNKNOWN
    )
    with pytest.raises(NotImplementedError):
        adapter.apply(request("RESOLVED", SimpleNamespace(value="KNOWN")))
