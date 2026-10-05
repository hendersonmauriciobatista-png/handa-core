"""C4C expected-RED falsifiers for read-only APPLIED reconstruction.

The suite creates durable ledger and position-effect evidence before crossing
the intentionally absent C4C boundary. C4C-012 and C4C-017 are deliberately
not represented as executable tests because the current public architecture
has no legitimate duplicate-candidate or external-submission reader boundary.
"""

from importlib import import_module
from pathlib import Path
import os
import re
from urllib.parse import urlparse

import psycopg2
import pytest

from core.execution.operational_effect_adapter import (
    EffectType,
    LogicalEffectBinding,
    LogicalEffectIdentity,
)
from core.persistence.effect_application_ledger import EffectApplicationLedger
from core.position.position_effect_authority import (
    PositionEffectAuthority,
    PositionEffectResult,
)
from tests.integration import test_effect_application_ledger_postgres as _ledger_test


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = tuple(
    ROOT / "core" / "persistence" / "migrations" / name
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
REPLAY_MODULE = "core.persistence.applied_effect_replay"
EXPECTED_DB_URL = "postgresql://handa_test:handa_test_only@127.0.0.1:55432/handa_test"


def _database_url():
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.fail("TEST_DATABASE_URL is required for durable C4C falsifiers")
    parsed = urlparse(value)
    if value != EXPECTED_DB_URL or parsed.port != 55432:
        pytest.fail("TEST_DATABASE_URL is not the governed disposable database")
    return value


@pytest.fixture()
def connection():
    connection = psycopg2.connect(_database_url())
    try:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            for migration in MIGRATIONS:
                cursor.execute(migration.read_text(encoding="utf-8"))
        connection.commit()
        _ledger_test._base(connection)
        yield connection
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
        connection.commit()
        connection.close()


def _fresh_connection():
    return psycopg2.connect(_database_url())


def _binding(
    *,
    logical_id,
    request_id,
    effect_type,
    authority_decision_id="decision-a",
    reconciliation_context_id="context-a",
    decision_sequence=1,
    authority_contract_version="v1",
):
    return LogicalEffectBinding(
        logical_identity=LogicalEffectIdentity("intent-a", logical_id),
        effect_request_id=request_id,
        effect_type=EffectType(effect_type),
        authority_decision_id=authority_decision_id,
        reconciliation_context_id=reconciliation_context_id,
        decision_sequence=decision_sequence,
        authority_contract_version=authority_contract_version,
    )


def _binding_values(binding, *, semantic_decision_id=None):
    return {
        "reconciliation_context_id": binding.reconciliation_context_id,
        "semantic_decision_id": semantic_decision_id or binding.authority_decision_id,
        "decision_sequence": binding.decision_sequence,
        "authority_contract_version": binding.authority_contract_version,
    }


def _position_receipt(receipt_id, order_id, quantity):
    return {
        "receipt_id": receipt_id,
        "exchange": "TEST",
        "order_id": order_id,
        "executed_base_qty": quantity,
        "executed_quote_qty": 100,
        "weighted_price": 100,
        "status": "FILLED",
        "fills": [{"trade_id": f"trade-{order_id}", "quantity": quantity}],
        "normalization_version": "v1",
    }


def _ledger_receipt(receipt_id):
    return {
        "receipt_id": receipt_id,
        "schema_version": "v1",
        "producer_id": "c4c-test",
        "payload": {"receipt_id": receipt_id},
    }


def _create_request_and_claim(connection, binding, attempt_id):
    ledger = EffectApplicationLedger(
        connection, trusted_issuers=_ledger_test.TEST_TRUSTED_ISSUERS
    )
    with ledger.transaction_scope() as cursor:
        ledger.bind_logical_effect(
            logical_identity=binding.logical_identity,
            effect_request_id=binding.effect_request_id,
            effect_type=binding.effect_type,
            authority_decision_id=binding.authority_decision_id,
            reconciliation_context_id=binding.reconciliation_context_id,
            decision_sequence=binding.decision_sequence,
            authority_contract_version=binding.authority_contract_version,
            cursor=cursor,
        )
        ledger.claim_application(
            binding.effect_request_id,
            application_attempt_id=attempt_id,
            cursor=cursor,
        )
    return ledger


def _create_open(
    connection,
    *,
    logical_id="logical-open",
    request_id="request-open",
    attempt_id="attempt-open",
    position_id="position-1",
    quantity=10,
    semantic_decision_id=None,
    before_apply=None,
):
    binding = _binding(
        logical_id=logical_id,
        request_id=request_id,
        effect_type=EffectType.OPEN,
    )
    ledger = _create_request_and_claim(connection, binding, attempt_id)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    if before_apply is not None:
        before_apply(connection)
    position_receipt = _position_receipt(
        f"position-{request_id}", f"order-{request_id}", quantity
    )
    with ledger.transaction_scope() as cursor:
        position_result = authority.apply_open(
            position_id=position_id,
            intended_quantity=quantity,
            receipt=position_receipt,
            intent_id="intent-a",
            symbol="BTCUSDC",
            effect_request_id=request_id,
            cursor=cursor,
            **_binding_values(binding, semantic_decision_id=semantic_decision_id),
        )
        ledger.mark_applied(
            request_id,
            application_attempt_id=attempt_id,
            receipt=_ledger_receipt(f"ledger-{request_id}"),
            cursor=cursor,
        )
    return binding, position_result


def _persist_historical_position_effect(
    connection,
    *,
    ledger,
    binding,
    attempt_id,
    position_id,
    effect_type,
    receipt,
    previous_quantity,
    applied_quantity,
    resulting_quantity,
):
    """Seed one valid immutable history row without changing production code.

    The current PositionEffectAuthority persistent REDUCE/CLOSE path updates
    the mutable projection before migration-007's insert trigger validates the
    historical transition.  This test-only seed writes the event first, in the
    order required by the published database contract, then advances the
    projection and closes the ledger attempt in the same transaction.
    """

    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    with ledger.transaction_scope() as cursor:
        cursor.execute(
            "SELECT current_quantity, position_lifecycle_version "
            "FROM handa_live.position WHERE position_id=%s FOR UPDATE",
            (position_id,),
        )
        current_quantity, current_version = cursor.fetchone()
        assert current_quantity == previous_quantity
        metadata = authority._persistent_metadata(
            cursor, binding.effect_request_id, _binding_values(binding)
        )
        extent = authority._extent_identity(receipt)
        receipt_id = authority._persist_receipt(
            cursor, receipt, binding.effect_request_id, extent
        )
        cursor.execute(
            "SELECT COALESCE(MAX(event_sequence), 0) + 1 "
            "FROM handa_live.position_effect_event WHERE position_id=%s",
            (position_id,),
        )
        event_sequence = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO handa_live.position_effect_event
            (position_id, intent_id, effect_type, effect_request_id,
             application_attempt_id, external_order_identity,
             execution_extent_identity, receipt_id, previous_quantity,
             applied_quantity, resulting_quantity, event_sequence,
             reconciliation_context_id, semantic_decision_id, decision_sequence,
             authority_contract_version)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                position_id,
                "intent-a",
                effect_type.value,
                binding.effect_request_id,
                metadata["application_attempt_id"],
                str(receipt["order_id"]),
                extent,
                receipt_id,
                previous_quantity,
                applied_quantity,
                resulting_quantity,
                event_sequence,
                metadata["reconciliation_context_id"],
                metadata["semantic_decision_id"],
                metadata["decision_sequence"],
                metadata["authority_contract_version"],
            ),
        )
        lifecycle_state = "CLOSED" if resulting_quantity == 0 else "ACTIVE"
        cursor.execute(
            "UPDATE handa_live.position SET lifecycle_state=%s, "
            "current_quantity=%s, position_lifecycle_version=%s, "
            "updated_at=CURRENT_TIMESTAMP WHERE position_id=%s",
            (lifecycle_state, resulting_quantity, current_version + 1, position_id),
        )
        ledger.mark_applied(
            binding.effect_request_id,
            application_attempt_id=attempt_id,
            receipt=_ledger_receipt(f"ledger-{binding.effect_request_id}"),
            cursor=cursor,
        )
    return PositionEffectResult(
        position_id=position_id,
        effect_type=effect_type.value,
        previous_quantity=previous_quantity,
        applied_quantity=applied_quantity,
        resulting_quantity=resulting_quantity,
        state=lifecycle_state,
        effect_request_id=binding.effect_request_id,
        execution_extent_identity=extent,
    )


def _create_reduce(
    connection,
    *,
    logical_id="logical-reduce",
    request_id="request-reduce",
    attempt_id="attempt-reduce",
    position_id="position-1",
    quantity=4,
):
    binding = _binding(
        logical_id=logical_id,
        request_id=request_id,
        effect_type=EffectType.REDUCE,
    )
    ledger = _create_request_and_claim(connection, binding, attempt_id)
    position_receipt = _position_receipt(
        f"position-{request_id}", f"order-{request_id}", quantity
    )
    position_result = _persist_historical_position_effect(
        connection,
        ledger=ledger,
        binding=binding,
        attempt_id=attempt_id,
        position_id=position_id,
        effect_type=EffectType.REDUCE,
        receipt=position_receipt,
        previous_quantity=10,
        applied_quantity=quantity,
        resulting_quantity=10 - quantity,
    )
    return binding, position_result


def _create_close(
    connection,
    *,
    logical_id="logical-close",
    request_id="request-close",
    attempt_id="attempt-close",
    position_id="position-1",
    quantity=10,
):
    binding = _binding(
        logical_id=logical_id,
        request_id=request_id,
        effect_type=EffectType.CLOSE,
    )
    ledger = _create_request_and_claim(connection, binding, attempt_id)
    position_receipt = _position_receipt(
        f"position-{request_id}", f"order-{request_id}", quantity
    )
    position_result = _persist_historical_position_effect(
        connection,
        ledger=ledger,
        binding=binding,
        attempt_id=attempt_id,
        position_id=position_id,
        effect_type=EffectType.CLOSE,
        receipt=position_receipt,
        previous_quantity=quantity,
        applied_quantity=quantity,
        resulting_quantity=0,
    )
    return binding, position_result


def _create_ledger_only_applied(connection, *, request_id, logical_id, recovery):
    binding = _binding(
        logical_id=logical_id,
        request_id=request_id,
        effect_type=EffectType.OPEN,
    )
    ledger = _create_request_and_claim(connection, binding, f"attempt-{request_id}")
    attempt_id = f"attempt-{request_id}"
    if not recovery:
        ledger.mark_applied(
            request_id,
            application_attempt_id=attempt_id,
            receipt=_ledger_receipt(f"ledger-{request_id}"),
        )
        return binding

    evidence = ({"evidence_id": f"recovery-{request_id}", "proof_type": "EXCHANGE_QUERY"},)
    ledger.mark_outcome_unknown(
        request_id,
        application_attempt_id=attempt_id,
        reason="C4C recovery fixture",
        evidence=evidence,
    )
    ledger.recover_application(
        request_id,
        recovery_authority_id="recovery-c4c",
        recovery_policy_version="v1",
        classification="APPLIED",
        evidence=evidence,
        receipt=_ledger_receipt(f"recovered-{request_id}"),
        recovery_capability=_ledger_test._recovery_capability(
            effect_request_id=request_id,
            application_attempt_id=attempt_id,
            allowed_classification="APPLIED",
            evidence=evidence,
            nonce=f"nonce-{request_id}",
        ),
        recovery_subject_id="recovery-worker",
    )
    return binding


class _ReadOnlyCursor:
    """Test-only cursor that makes any replay write observable and fatal."""

    def __init__(self, cursor):
        self._cursor = cursor
        self.statements = []

    def execute(self, statement, params=None):
        text = str(statement)
        self.statements.append(text)
        if re.search(r"\b(INSERT|UPDATE|DELETE|TRUNCATE|ALTER|DROP|CREATE)\b", text, re.I):
            raise AssertionError(f"C4C replay attempted a database write: {text}")
        if params is None:
            return self._cursor.execute(statement)
        return self._cursor.execute(statement, params)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


def _reconstruct(binding, connection, *, cursor=None):
    module = import_module(REPLAY_MODULE)
    reconstruct = getattr(module, "reconstruct_applied_effect")
    if cursor is not None:
        result = reconstruct(logical_binding=binding, cursor=cursor)
        connection.rollback()
        return result
    with connection.cursor() as cursor:
        result = reconstruct(logical_binding=binding, cursor=cursor)
    connection.rollback()
    return result


def _expect_reconstruction_error(binding, connection, classification):
    try:
        _reconstruct(binding, connection)
    except ModuleNotFoundError:
        raise
    except Exception as error:
        assert classification in str(error)
    else:
        raise AssertionError(f"expected reconstruction failure: {classification}")


def _snapshot(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM handa_live.effect_request),
              (SELECT COUNT(*) FROM handa_live.application_attempt),
              (SELECT COUNT(*) FROM handa_live.applied_effect),
              (SELECT COUNT(*) FROM handa_live.lifecycle_event),
              (SELECT COUNT(*) FROM handa_live.position),
              (SELECT COUNT(*) FROM handa_live.position_receipt),
              (SELECT COUNT(*) FROM handa_live.position_effect_event)
            """
        )
        counts = cursor.fetchone()
        cursor.execute(
            "SELECT effect_request_id, current_state, current_attempt_id "
            "FROM handa_live.effect_request ORDER BY effect_request_id"
        )
        requests = tuple(cursor.fetchall())
        cursor.execute(
            "SELECT position_id, lifecycle_state, current_quantity, "
            "position_lifecycle_version FROM handa_live.position "
            "ORDER BY position_id"
        )
        positions = tuple(cursor.fetchall())
    return counts, requests, positions


def _lifecycle_snapshot(connection, request_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_state, current_attempt_id FROM handa_live.effect_request "
            "WHERE effect_request_id=%s",
            (request_id,),
        )
        request = cursor.fetchone()
        cursor.execute(
            "SELECT event_sequence, previous_state, next_state, event_kind "
            "FROM handa_live.lifecycle_event WHERE effect_request_id=%s "
            "ORDER BY event_sequence",
            (request_id,),
        )
        events = tuple(cursor.fetchall())
    return request, events


def _position_snapshot(connection, position_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT position_id, lifecycle_state, current_quantity, "
            "position_lifecycle_version FROM handa_live.position "
            "WHERE position_id=%s",
            (position_id,),
        )
        position = cursor.fetchone()
        cursor.execute(
            "SELECT effect_request_id, effect_type, previous_quantity, "
            "applied_quantity, resulting_quantity, event_sequence, "
            "execution_extent_identity FROM handa_live.position_effect_event "
            "WHERE position_id=%s ORDER BY event_sequence",
            (position_id,),
        )
        events = tuple(cursor.fetchall())
    return position, events


def test_c4c001_public_reconstruction_api_exists():
    module = import_module(REPLAY_MODULE)
    assert callable(getattr(module, "reconstruct_applied_effect"))


def test_c4c002_reconstructs_canonical_applied_result(connection):
    binding, expected = _create_open(connection)
    result = _reconstruct(binding, connection)
    assert result.effect_request_id == binding.effect_request_id
    assert result.applied_effect_id
    assert result.position_effect_result == expected


def test_c4c003_reconstructs_open_historical_result(connection):
    binding, expected = _create_open(connection)
    result = _reconstruct(binding, connection)
    assert result.position_effect_result == expected
    assert result.position_effect_result.state == "ACTIVE"


def test_c4c004_reconstructs_reduce_historical_result(connection):
    _create_open(connection)
    binding, expected = _create_reduce(connection)
    result = _reconstruct(binding, connection)
    assert result.position_effect_result == expected
    assert result.position_effect_result.residual_quantity == 6


def test_c4c005_reconstructs_close_historical_result(connection):
    _create_open(connection)
    binding, expected = _create_close(connection)
    result = _reconstruct(binding, connection)
    assert result.position_effect_result == expected
    assert result.position_effect_result.state == "CLOSED"
    assert result.position_effect_result.residual_quantity == 0


def test_c4c006_reconstructs_from_a_fresh_session(connection):
    binding, expected = _create_open(connection)
    connection.commit()
    fresh = _fresh_connection()
    try:
        result = _reconstruct(binding, fresh)
    finally:
        fresh.close()
    assert result.position_effect_result == expected


def test_c4c007_replay_has_no_durable_write(connection):
    binding, _ = _create_open(connection)
    before = _snapshot(connection)
    with connection.cursor() as raw_cursor:
        audited_cursor = _ReadOnlyCursor(raw_cursor)
        _reconstruct(binding, connection, cursor=audited_cursor)
    after = _snapshot(connection)
    assert after == before
    assert all(
        not re.search(r"\b(INSERT|UPDATE|DELETE|TRUNCATE|ALTER|DROP|CREATE)\b", statement, re.I)
        for statement in audited_cursor.statements
    )


def test_c4c008_replay_does_not_mutate_position_or_history(connection):
    binding, _ = _create_open(connection)
    before = _position_snapshot(connection, "position-1")
    with connection.cursor() as raw_cursor:
        _reconstruct(binding, connection, cursor=_ReadOnlyCursor(raw_cursor))
    after = _position_snapshot(connection, "position-1")
    assert after == before


def test_c4c009_replay_does_not_transition_lifecycle(connection):
    binding, _ = _create_open(connection)
    before = _lifecycle_snapshot(connection, binding.effect_request_id)
    with connection.cursor() as raw_cursor:
        _reconstruct(binding, connection, cursor=_ReadOnlyCursor(raw_cursor))
    after = _lifecycle_snapshot(connection, binding.effect_request_id)
    assert after == before


def test_c4c010_missing_required_position_history_fails_closed(connection):
    binding = _create_ledger_only_applied(
        connection,
        request_id="request-missing-history",
        logical_id="logical-missing-history",
        recovery=False,
    )
    before = _snapshot(connection)
    _expect_reconstruction_error(
        binding, connection, "DURABLE_APPLIED_RESULT_MISSING"
    )
    assert _snapshot(connection) == before


def test_c4c011_cross_source_lineage_contradiction_fails_closed(connection):
    def insert_contradicting_decision(connection):
        _ledger_test._decision(
            connection,
            decision_id="decision-not-authorized",
            context_id="context-a",
            intent_id="intent-a",
            sequence=2,
        )
        connection.commit()

    binding, _ = _create_open(
        connection,
        request_id="request-contradiction",
        logical_id="logical-contradiction",
        attempt_id="attempt-contradiction",
        semantic_decision_id="decision-not-authorized",
        before_apply=insert_contradicting_decision,
    )
    _expect_reconstruction_error(
        binding, connection, "DURABLE_DATA_CONTRADICTION"
    )


def test_c4c013_validates_and_returns_matching_authority_lineage(connection):
    binding, _ = _create_open(connection)
    result = _reconstruct(binding, connection)
    assert result.authority_decision_id == binding.authority_decision_id
    assert result.reconciliation_context_id == binding.reconciliation_context_id
    assert result.decision_sequence == binding.decision_sequence
    assert result.authority_contract_version == binding.authority_contract_version


def test_c4c014_preserves_exact_execution_extent_identity(connection):
    binding, expected = _create_open(connection)
    result = _reconstruct(binding, connection)
    assert (
        result.position_effect_result.execution_extent_identity
        == expected.execution_extent_identity
    )


def test_c4c015_historical_e1_wins_over_current_position_drift(connection):
    open_binding, open_result = _create_open(connection)
    _create_reduce(connection)
    result = _reconstruct(open_binding, connection)
    position, _ = _position_snapshot(connection, "position-1")
    assert position[2] == 6
    assert result.position_effect_result == open_result
    assert result.position_effect_result.resulting_quantity == 10


def test_c4c016_replay_does_not_call_c4d_mutation_boundaries(connection, monkeypatch):
    binding, _ = _create_open(connection)

    def forbidden(*args, **kwargs):
        raise AssertionError("C4C invoked a C4D mutation boundary")

    monkeypatch.setattr(EffectApplicationLedger, "claim_application", forbidden)
    monkeypatch.setattr(EffectApplicationLedger, "mark_applied", forbidden)
    monkeypatch.setattr(PositionEffectAuthority, "apply_open", forbidden)
    monkeypatch.setattr(PositionEffectAuthority, "apply_reduction", forbidden)
    monkeypatch.setattr(PositionEffectAuthority, "apply_close", forbidden)

    result = _reconstruct(binding, connection)
    assert result.effect_request_id == binding.effect_request_id


def test_c4c018_oa005_behavior_remains_protected():
    from core.execution.operational_effect_adapter import (
        OperationalEffectAdapter,
        OperationalEffectStatus,
    )
    from tests.test_operational_effect_adapter_expected_red import (
        _request,
        _unknown_execution_fact,
    )

    pending = OperationalEffectAdapter().apply(
        _request(semantic_state="PENDING", execution_fact=_unknown_execution_fact())
    )
    unknown = OperationalEffectAdapter().apply(
        _request(execution_fact=_unknown_execution_fact())
    )
    assert pending.status is OperationalEffectStatus.PENDING
    assert unknown.status is OperationalEffectStatus.OUTCOME_UNKNOWN


def test_c4c019_recovery_applied_without_position_event_is_not_reconstructable(
    connection,
):
    binding = _create_ledger_only_applied(
        connection,
        request_id="request-recovered-applied",
        logical_id="logical-recovered-applied",
        recovery=True,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_state FROM handa_live.effect_request "
            "WHERE effect_request_id=%s",
            (binding.effect_request_id,),
        )
        assert cursor.fetchone()[0] == "APPLIED"
        cursor.execute(
            "SELECT COUNT(*) FROM handa_live.applied_effect "
            "WHERE effect_request_id=%s",
            (binding.effect_request_id,),
        )
        assert cursor.fetchone()[0] == 1
        cursor.execute(
            "SELECT COUNT(*) FROM handa_live.position_effect_event "
            "WHERE effect_request_id=%s",
            (binding.effect_request_id,),
        )
        assert cursor.fetchone()[0] == 0
    before = _snapshot(connection)
    _expect_reconstruction_error(
        binding,
        connection,
        "APPLIED_POSITION_RESULT_NOT_RECONSTRUCTABLE",
    )
    assert _snapshot(connection) == before
