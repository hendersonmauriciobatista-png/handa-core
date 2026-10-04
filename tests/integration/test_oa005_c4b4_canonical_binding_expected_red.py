"""C4B-4 falsifiers for canonical binding creation."""

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
from tests.integration import test_effect_application_ledger_postgres as _postgres


ROOT = Path(__file__).parents[2]
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


def _bind_capability():
    method = _public_ledger_methods().get("bind_logical_effect")
    if method is None:
        return None
    required = {
        "logical_identity",
        "effect_request_id",
        "effect_type",
        "authority_decision_id",
        "reconciliation_context_id",
        "decision_sequence",
        "authority_contract_version",
    }
    return method if required <= set(inspect.signature(method).parameters) else None


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


@pytest.fixture()
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
            cursor.execute("SELECT current_database(), current_user")
            assert cursor.fetchone() == (EXPECTED_DATABASE, EXPECTED_USER)
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            for migration in migrations:
                cursor.execute(migration.read_text(encoding="utf-8"))
        connection.commit()
        _postgres._base(connection)
        yield connection
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
        connection.commit()
        connection.close()


def _ledger(connection):
    return EffectApplicationLedger(connection)


def _bind_kwargs(
    *,
    logical_id="logical-a",
    request_id="request-a",
    effect_type=EffectType.OPEN,
    authority_decision_id="decision-a",
    reconciliation_context_id="context-a",
    decision_sequence=1,
    authority_contract_version="v1",
):
    return {
        "logical_identity": LogicalEffectIdentity("intent-a", logical_id),
        "effect_request_id": request_id,
        "effect_type": effect_type,
        "authority_decision_id": authority_decision_id,
        "reconciliation_context_id": reconciliation_context_id,
        "decision_sequence": decision_sequence,
        "authority_contract_version": authority_contract_version,
    }


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
        return cursor.fetchone()


def test_c4b4001_public_canonical_bind_capability_exists():
    assert _bind_capability() is not None


def test_c4b4002_bind_returns_published_write_result():
    method = _bind_capability()
    assert get_type_hints(method).get("return") is _adapter_module().LogicalBindingWriteResult


def test_c4b4003_candidate_request_id_is_explicit_input():
    method = _bind_capability()
    assert "effect_request_id" in inspect.signature(method).parameters


def test_c4b4004_first_canonical_binding_creation(connection):
    result = _ledger(connection).bind_logical_effect(**_bind_kwargs())
    assert result.disposition is _adapter_module().LogicalBindingWriteDisposition.CREATED_CANONICAL_BINDING
    assert result.binding.effect_request_id == "request-a"
    assert result.binding.logical_identity == LogicalEffectIdentity("intent-a", "logical-a")


def test_c4b4005_effect_request_durability(connection):
    _ledger(connection).bind_logical_effect(**_bind_kwargs())
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT effect_request_id, effect_type, intent_id,
                   reconciliation_context_id, logical_effect_id, current_state
            FROM handa_live.effect_request
            WHERE effect_request_id='request-a'
            """
        )
        assert cursor.fetchone() == (
            "request-a", "OPEN", "intent-a", "context-a", "logical-a", "AUTHORIZED"
        )


def test_c4b4006_authority_binding_durability(connection):
    _ledger(connection).bind_logical_effect(**_bind_kwargs())
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT effect_request_id, authority_decision_id, intent_id,
                   reconciliation_context_id, decision_sequence,
                   authority_contract_version
            FROM handa_live.authority_binding
            WHERE effect_request_id='request-a'
            """
        )
        assert cursor.fetchone() == (
            "request-a", "decision-a", "intent-a", "context-a", 1, "v1"
        )


def test_c4b4007_authorized_lifecycle_foundation(connection):
    _ledger(connection).bind_logical_effect(**_bind_kwargs())
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT er.current_state, le.previous_state, le.next_state,
                   le.event_kind, COUNT(aa.application_attempt_id)
            FROM handa_live.effect_request er
            JOIN handa_live.lifecycle_event le
              ON le.effect_request_id=er.effect_request_id
            LEFT JOIN handa_live.application_attempt aa
              ON aa.effect_request_id=er.effect_request_id
            WHERE er.effect_request_id='request-a'
            GROUP BY er.current_state, le.previous_state, le.next_state,
                     le.event_kind
            """
        )
        assert cursor.fetchone() == (
            "AUTHORIZED", None, "AUTHORIZED", "AUTHORITY_ACCEPTED", 0
        )


def test_c4b4008_created_result_semantics(connection):
    result = _ledger(connection).bind_logical_effect(**_bind_kwargs())
    assert result.disposition is _adapter_module().LogicalBindingWriteDisposition.CREATED_CANONICAL_BINDING
    assert result.binding.effect_type is EffectType.OPEN
    assert result.binding.authority_decision_id == "decision-a"
    assert result.binding.reconciliation_context_id == "context-a"
    assert result.binding.decision_sequence == 1
    assert result.binding.authority_contract_version == "v1"


def test_c4b4009_existing_valid_binding_reuses_canonical_request(connection):
    ledger = _ledger(connection)
    ledger.bind_logical_effect(**_bind_kwargs())
    result = ledger.bind_logical_effect(**_bind_kwargs(request_id="request-b"))
    assert result.disposition is _adapter_module().LogicalBindingWriteDisposition.EXISTING_VALID_BINDING
    assert result.binding.effect_request_id == "request-a"
    assert _counts(connection) == (1, 1, 1, 0)


def test_c4b4010_existing_conflicting_binding_is_preserved(connection):
    ledger = _ledger(connection)
    ledger.bind_logical_effect(**_bind_kwargs())
    result = ledger.bind_logical_effect(
        **_bind_kwargs(request_id="request-b", authority_decision_id="decision-other")
    )
    assert result.disposition is _adapter_module().LogicalBindingWriteDisposition.CONFLICTING_BINDING
    assert result.binding.effect_request_id == "request-a"
    assert _counts(connection) == (1, 1, 1, 0)


def test_c4b4011_effect_type_conflict_is_explicit(connection):
    ledger = _ledger(connection)
    ledger.bind_logical_effect(**_bind_kwargs())
    result = ledger.bind_logical_effect(
        **_bind_kwargs(request_id="request-b", effect_type=EffectType.CLOSE)
    )
    assert result.disposition is _adapter_module().LogicalBindingWriteDisposition.CONFLICTING_BINDING
    assert result.binding.effect_request_id == "request-a"


def test_c4b4012_authority_metadata_conflicts_are_explicit(connection):
    ledger = _ledger(connection)
    ledger.bind_logical_effect(**_bind_kwargs())
    for field, value in (
        ("authority_decision_id", "decision-other"),
        ("reconciliation_context_id", "context-other"),
        ("decision_sequence", 2),
        ("authority_contract_version", "v2"),
    ):
        values = _bind_kwargs(request_id=f"candidate-{field}")
        values[field] = value
        result = ledger.bind_logical_effect(**values)
        assert result.disposition is _adapter_module().LogicalBindingWriteDisposition.CONFLICTING_BINDING
        assert result.binding.effect_request_id == "request-a"
    assert _counts(connection) == (1, 1, 1, 0)


def test_c4b4013_first_bind_is_atomic(connection, monkeypatch):
    ledger = _ledger(connection)

    def fail_event(*args, **kwargs):
        raise RuntimeError("synthetic lifecycle failure")

    monkeypatch.setattr(ledger, "_event", fail_event)
    with pytest.raises(RuntimeError, match="synthetic lifecycle failure"):
        ledger.bind_logical_effect(**_bind_kwargs(request_id="request-atomic"))
    assert _counts(connection) == (0, 0, 0, 0)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.effect_request
                (effect_request_id, effect_type, intent_id,
                 reconciliation_context_id, logical_effect_id, current_state)
            VALUES ('occupied', 'OPEN', 'intent-a', 'context-a',
                    'logical-occupied', 'AUTHORIZED'),
                   ('legacy', 'OPEN', 'intent-a', 'context-a',
                    NULL, 'AUTHORIZED')
            """
        )
    connection.commit()
    for candidate, logical_id in (("occupied", "logical-b"), ("legacy", "logical-c")):
        with pytest.raises(
            EffectApplicationLedgerError,
            match="candidate effect_request_id is already occupied",
        ):
            ledger.bind_logical_effect(
                **_bind_kwargs(request_id=candidate, logical_id=logical_id)
            )
    assert _counts(connection) == (2, 0, 0, 0)


def test_c4b4014_bind_preserves_caller_transaction_ownership(connection):
    ledger = _ledger(connection)
    with connection.cursor() as cursor:
        cursor.execute("BEGIN")
        status_before = connection.status
        result = ledger.bind_logical_effect(
            cursor=cursor, **_bind_kwargs(request_id="request-cursor")
        )
        assert result.disposition is _adapter_module().LogicalBindingWriteDisposition.CREATED_CANONICAL_BINDING
        assert connection.status == status_before
        cursor.execute(
            "SELECT COUNT(*) FROM handa_live.effect_request WHERE effect_request_id='request-cursor'"
        )
        assert cursor.fetchone() == (1,)
        connection.rollback()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM handa_live.effect_request WHERE effect_request_id='request-cursor'"
        )
        assert cursor.fetchone() == (0,)


def test_c4b4015_published_lookup_remains_read_only(connection):
    ledger_type = _ledger_module().EffectApplicationLedger
    assert "lookup_logical_binding" in _public_ledger_methods()
    assert "bind_logical_effect" in _public_ledger_methods()
    assert "effect_request_id" not in inspect.signature(
        ledger_type.lookup_logical_binding
    ).parameters
    ledger = _ledger(connection)
    before = _counts(connection)
    ledger.lookup_logical_binding(
        logical_identity=LogicalEffectIdentity("intent-a", "absent"),
        effect_type=EffectType.OPEN,
        authority_decision_id="decision-a",
        reconciliation_context_id="context-a",
        decision_sequence=1,
        authority_contract_version="v1",
    )
    assert _counts(connection) == before


def test_c4b4016_c4b5_concurrency_protocol_is_absent():
    method_names = set(_public_ledger_methods())
    assert "bind_logical_effect" in method_names
    assert not method_names & {"resolve_binding_collision", "converge_first_bind"}


def test_c4b4017_no_c4c_or_c4d_behavior_is_present():
    source = inspect.getsource(_adapter_module())
    forbidden = (
        "AppliedEffectReplayRecord",
        "PositionEffectResult",
        "mark_applied",
        "claim_application",
        "order_market",
        "resubmit",
    )
    assert all(token not in source for token in forbidden)


def test_c4b4018_operational_adapter_behavior_remains_unchanged():
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
