"""C4B-3 falsifiers for the public logical binding lookup contract."""

from importlib import import_module
import inspect
import os
from pathlib import Path
from types import SimpleNamespace
from typing import get_type_hints
from urllib.parse import urlparse

import psycopg2
import pytest

from core.execution.operational_effect_adapter import EffectType, LogicalEffectIdentity
from core.persistence.effect_application_ledger import (
    EffectApplicationLedger,
    EffectApplicationLedgerError,
)


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "core" / "persistence" / "migrations"
EXPECTED_DATABASE = "handa_test"
EXPECTED_USER = "handa_test"
EXPECTED_HOSTS = {"127.0.0.1", "localhost"}
EXPECTED_PORT = 55432


def _ledger_module():
    return import_module("core.persistence.effect_application_ledger")


def _adapter_module():
    return import_module("core.execution.operational_effect_adapter")


def _public_ledger_methods():
    ledger_type = _ledger_module().EffectApplicationLedger
    return {
        name: member
        for name, member in inspect.getmembers(ledger_type, inspect.isfunction)
        if not name.startswith("_")
    }


def _lookup_capability():
    required = {
        "effect_type",
        "authority_decision_id",
        "reconciliation_context_id",
        "decision_sequence",
        "authority_contract_version",
    }
    for method in _public_ledger_methods().values():
        parameters = set(inspect.signature(method).parameters)
        has_identity = "logical_identity" in parameters or {
            "intent_id",
            "logical_effect_id",
        } <= parameters
        if has_identity and required <= parameters:
            return method
    return None


def _binding_write_capability():
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
        if required <= parameters and (
            "logical_identity" in parameters
            or {"intent_id", "logical_effect_id"} <= parameters
        ):
            return method
    return None


def _skip_not_reached(control):
    pytest.skip(f"{control}::NOT_YET_REACHED")


def _database_url():
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("ENVIRONMENT_BLOCKED: TEST_DATABASE_URL is not configured")
    parsed = urlparse(value)
    if (
        parsed.hostname not in EXPECTED_HOSTS
        or parsed.port != EXPECTED_PORT
        or parsed.path.lstrip("/") != EXPECTED_DATABASE
        or parsed.username != EXPECTED_USER
    ):
        pytest.skip("ENVIRONMENT_BLOCKED: TEST_DATABASE_URL is not disposable handa_test")
    return value


@pytest.fixture(scope="module")
def connection():
    try:
        connection = psycopg2.connect(_database_url())
    except (OSError, psycopg2.Error) as exc:
        pytest.skip(f"ENVIRONMENT_BLOCKED: disposable PostgreSQL unavailable: {exc}")
    migrations = tuple(
        MIGRATIONS_DIR / name
        for name in (
            "001_create_handa_live.sql",
            "002_relax_may_have_been_submitted_certainty.sql",
            "003_reconciliation_evidence.sql",
            "004_external_order_observation_contract.sql",
            "005_decision_ledger.sql",
            "006_effect_application_ledger.sql",
            "007_position_effect_authority.sql",
            "008_effect_request_logical_binding.sql",
        )
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            for migration in migrations:
                cursor.execute(migration.read_text(encoding="utf-8"))
            cursor.execute(
                """
                INSERT INTO handa_live.order_intent
                    (intent_id, venue, account_scope, client_order_id, slot_id,
                     symbol, side, requested_quote_amount, policy_context,
                     submission_lifecycle_state)
                VALUES ('intent-a', 'TEST', 'TEST', 'client-a', 'slot-a',
                        'BTCUSDT', 'BUY', 10, '', 'READY_TO_SUBMIT')
                """
            )
            cursor.execute(
                """
                INSERT INTO handa_live.reconciliation_context
                    (context_id, intent_id, context_sequence, context_state,
                     closed_at)
                VALUES ('context-a', 'intent-a', 1, 'ACTIVE', NULL),
                       ('context-b', 'intent-a', 2, 'CLOSED', CURRENT_TIMESTAMP)
                """
            )
            cursor.execute(
                """
                INSERT INTO handa_live.semantic_decision
                    (decision_id, context_id, intent_id, decision_sequence,
                     evaluation_time, decision_scope, authority_state,
                     execution_occurred, order_outcome_terminal,
                     execution_extent, final_partial_outcome,
                     evaluated_input_snapshot, authority_contract_version,
                     decision_schema_version, evidence_normalization_version,
                     lineage_completeness_status)
                VALUES ('decision-a', 'context-a', 'intent-a', 1,
                        CURRENT_TIMESTAMP, 'ORDER_OUTCOME', 'RESOLVED',
                        '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb,
                        '{}'::jsonb, 'v1', 'v1', 'v1', 'LINEAGE_COMPLETE')
                """
            )
            for request_id, logical_id in (
                ("request-a", "logical-a"),
                ("request-b", "logical-b"),
                ("request-c", "logical-c"),
            ):
                cursor.execute(
                    """
                    INSERT INTO handa_live.effect_request
                        (effect_request_id, effect_type, intent_id,
                         reconciliation_context_id, logical_effect_id,
                         current_state)
                    VALUES (%s, 'OPEN', 'intent-a', 'context-a', %s, 'AUTHORIZED')
                    """,
                    (request_id, logical_id),
                )
            cursor.execute(
                """
                INSERT INTO handa_live.authority_binding
                    (effect_request_id, authority_decision_id, intent_id,
                     reconciliation_context_id, decision_sequence,
                     authority_contract_version)
                VALUES ('request-a', 'decision-a', 'intent-a', 'context-a', 1, 'v1'),
                       ('request-c', 'decision-a', 'intent-a', 'context-b', 1, 'v1')
                """
            )
        connection.commit()
        yield connection
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
        connection.commit()
        connection.close()


def _lookup_kwargs(logical_id="logical-a", **overrides):
    values = {
        "logical_identity": LogicalEffectIdentity("intent-a", logical_id),
        "effect_type": EffectType.OPEN,
        "authority_decision_id": "decision-a",
        "reconciliation_context_id": "context-a",
        "decision_sequence": 1,
        "authority_contract_version": "v1",
    }
    values.update(overrides)
    return values


def _ledger(connection):
    return EffectApplicationLedger(connection)


def _counts(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM handa_live.effect_request),
                (SELECT COUNT(*) FROM handa_live.authority_binding),
                (SELECT COUNT(*) FROM handa_live.lifecycle_event),
                (SELECT COUNT(*) FROM handa_live.application_attempt)
            """
        )
        result = cursor.fetchone()
    connection.rollback()
    return result


def test_c4b3001_public_logical_lookup_capability_exists():
    if _lookup_capability() is None:
        pytest.fail(
            "BOUNDARY_RED: EffectApplicationLedger has no public logical binding "
            "lookup accepting LogicalEffectIdentity and frozen authority metadata"
        )


def test_c4b3002_lookup_returns_published_result_type():
    method = _lookup_capability()
    if method is None:
        _skip_not_reached("C4B3-002")
    assert (
        get_type_hints(method).get("return")
        is _adapter_module().LogicalBindingLookupResult
    )


def test_c4b3003_lookup_not_found_returns_empty_published_result(connection):
    result = _ledger(connection).lookup_logical_binding(
        **_lookup_kwargs(logical_id="absent")
    )
    assert result.disposition is _adapter_module().LogicalBindingLookupDisposition.NOT_FOUND
    assert result.binding is None


def test_c4b3004_lookup_returns_valid_canonical_binding(connection):
    result = _ledger(connection).lookup_logical_binding(**_lookup_kwargs())
    assert (
        result.disposition
        is _adapter_module().LogicalBindingLookupDisposition.FOUND_VALID_BINDING
    )
    assert result.binding.logical_identity == LogicalEffectIdentity(
        "intent-a", "logical-a"
    )
    assert result.binding.effect_request_id == "request-a"
    assert result.binding.effect_type is EffectType.OPEN


def test_c4b3005_lookup_reports_effect_type_conflict(connection):
    result = _ledger(connection).lookup_logical_binding(
        **_lookup_kwargs(effect_type=EffectType.REDUCE)
    )
    assert (
        result.disposition
        is _adapter_module().LogicalBindingLookupDisposition.FOUND_CONFLICTING_BINDING
    )
    assert result.binding.effect_request_id == "request-a"


def test_c4b3006_lookup_reports_authority_decision_conflict(connection):
    result = _ledger(connection).lookup_logical_binding(
        **_lookup_kwargs(authority_decision_id="decision-other")
    )
    assert (
        result.disposition
        is _adapter_module().LogicalBindingLookupDisposition.FOUND_CONFLICTING_BINDING
    )


def test_c4b3007_lookup_reports_reconciliation_context_conflict(connection):
    result = _ledger(connection).lookup_logical_binding(
        **_lookup_kwargs(reconciliation_context_id="context-b")
    )
    assert (
        result.disposition
        is _adapter_module().LogicalBindingLookupDisposition.FOUND_CONFLICTING_BINDING
    )


def test_c4b3008_lookup_reports_decision_sequence_conflict(connection):
    result = _ledger(connection).lookup_logical_binding(
        **_lookup_kwargs(decision_sequence=2)
    )
    assert (
        result.disposition
        is _adapter_module().LogicalBindingLookupDisposition.FOUND_CONFLICTING_BINDING
    )


def test_c4b3009_lookup_reports_authority_contract_version_conflict(connection):
    result = _ledger(connection).lookup_logical_binding(
        **_lookup_kwargs(authority_contract_version="v2")
    )
    assert (
        result.disposition
        is _adapter_module().LogicalBindingLookupDisposition.FOUND_CONFLICTING_BINDING
    )


def test_c4b3010_lookup_recovers_canonical_effect_request_id(connection):
    result = _ledger(connection).lookup_logical_binding(
        **_lookup_kwargs(effect_type=EffectType.CLOSE)
    )
    assert result.binding.effect_request_id == "request-a"


def test_c4b3011_lookup_is_read_only(connection):
    before = _counts(connection)
    ledger = _ledger(connection)
    ledger.lookup_logical_binding(**_lookup_kwargs(logical_id="absent"))
    ledger.lookup_logical_binding(**_lookup_kwargs())
    ledger.lookup_logical_binding(**_lookup_kwargs(effect_type=EffectType.REDUCE))
    with pytest.raises(
        EffectApplicationLedgerError,
        match="authority binding is missing for logical effect",
    ):
        ledger.lookup_logical_binding(**_lookup_kwargs(logical_id="logical-b"))
    with pytest.raises(
        EffectApplicationLedgerError,
        match="DURABLE_DATA_CONTRADICTION",
    ):
        ledger.lookup_logical_binding(**_lookup_kwargs(logical_id="logical-c"))
    assert _counts(connection) == before


def test_c4b3012_lookup_causes_no_lifecycle_transition(connection):
    before = _counts(connection)
    _ledger(connection).lookup_logical_binding(**_lookup_kwargs())
    after = _counts(connection)
    assert after[2:] == before[2:]


def test_c4b3013_lookup_preserves_read_cursor_convention(connection):
    ledger = _ledger(connection)
    owned = ledger.lookup_logical_binding(**_lookup_kwargs())
    assert owned.binding.effect_request_id == "request-a"
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        status_before = connection.status
        caller_owned = ledger.lookup_logical_binding(
            **_lookup_kwargs(), cursor=cursor
        )
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
        assert caller_owned.binding.effect_request_id == "request-a"
        assert connection.status == status_before
    connection.rollback()


def test_c4b3014_generic_ledger_semantics_remain_preserved():
    ledger_module = _ledger_module()
    signature = inspect.signature(ledger_module.EffectApplicationLedger.create_effect_request)
    annotation = signature.parameters["effect_type"].annotation
    assert annotation in (str, "str")
    assert "bind_logical_effect" not in _public_ledger_methods()


def test_c4b3015_c4b3_does_not_add_binding_write_behavior():
    assert _binding_write_capability() is None
    assert "bind_logical_effect" not in _public_ledger_methods()


def test_c4b3016_c4b3_does_not_add_concurrency_protocol():
    method_names = set(_public_ledger_methods())
    assert not method_names & {
        "bind_logical_effect",
        "resolve_binding_collision",
    }
    assert "savepoint" not in inspect.getsource(_ledger_module()).lower()


def test_c4b3017_c4b3_does_not_add_c4c_c4d_or_oa005_behavior():
    source = inspect.getsource(_adapter_module())
    forbidden = (
        "AppliedEffectReplayRecord",
        "PositionEffectResult",
        "claim_application",
        "mark_applied",
        "outer transaction",
        "retry",
        "resubmit",
        "order_market",
    )
    assert all(token not in source for token in forbidden)


def test_c4b3018_operational_adapter_behavior_remains_unchanged():
    module = _adapter_module()

    def request(state, extent_certainty=None):
        return module.OperationalEffectRequest(
            execution_fact=SimpleNamespace(extent_certainty=extent_certainty),
            semantic_decision=SimpleNamespace(state=state),
            reconciliation_context_id="context-1",
            authority_decision_id="decision-1",
            decision_sequence=1,
            evidence_ids=("evidence-1",),
            effect_eligibility=module.EffectEligibility(
                effect_type=module.EffectType.OPEN,
                authority_decision_id="decision-1",
                reconciliation_context_id="context-1",
                decision_sequence=1,
                evidence_ids=("evidence-1",),
            ),
            logical_effect_identity=module.LogicalEffectIdentity(
                "intent-1", "logical-1"
            ),
            position_binding=module.PositionBinding(
                position_creation_id="creation-1"
            ),
        )

    adapter = module.OperationalEffectAdapter()
    assert adapter.apply(request("PENDING")).status is module.OperationalEffectStatus.PENDING
    assert adapter.apply(request("BLOCKED")).status is module.OperationalEffectStatus.BLOCKED
    assert (
        adapter.apply(request("RESOLVED", SimpleNamespace(value="UNKNOWN"))).status
        is module.OperationalEffectStatus.OUTCOME_UNKNOWN
    )
    with pytest.raises(NotImplementedError):
        adapter.apply(request("RESOLVED", SimpleNamespace(value="KNOWN")))
