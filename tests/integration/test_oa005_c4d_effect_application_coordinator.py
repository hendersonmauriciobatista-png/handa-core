"""C4D expected-RED falsifiers for atomic effect coordination.

The coordinator is intentionally absent in this chain. C4D-001 is the single
boundary RED. C4D-002..C4D-017 still build durable PostgreSQL fixtures and
encode the governed assertions; they are reported as NOT_YET_REACHED until
the public coordinator module exists.

The suite defines orchestration expectations only. It does not add a
production implementation, a migration, recovery authority, or an external
submission path.
"""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest

from core.execution.operational_effect_adapter import (
    EffectType,
    LogicalEffectBinding,
    LogicalEffectIdentity,
)
from core.persistence.effect_application_ledger import EffectApplicationLedger
from core.position.position_effect_authority import PositionEffectAuthority
from tests.integration import test_effect_application_ledger_postgres as _ledger_test


MODULE = "core.execution.effect_application_coordinator"
MIGRATIONS = tuple(
    Path(__file__).parents[2] / "core" / "persistence" / "migrations" / name
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


def _database_url():
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.fail("TEST_DATABASE_URL is required for C4D durable falsifiers")
    parsed = urlparse(value)
    if (
        parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.port != 55432
        or parsed.username != "handa_test"
        or parsed.path.lstrip("/") != "handa_test"
    ):
        pytest.fail("refusing non-governed disposable PostgreSQL target")
    return value


@pytest.fixture()
def connection():
    conn = psycopg2.connect(_database_url())
    try:
        with conn.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            for migration in MIGRATIONS:
                cursor.execute(migration.read_text(encoding="utf-8"))
        conn.commit()
        _ledger_test._base(conn)
        yield conn
    finally:
        conn.rollback()
        with conn.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
        conn.commit()
        conn.close()


def _binding(
    *,
    logical_id="logical-reduce",
    request_id="request-reduce",
    effect_type=EffectType.REDUCE,
    authority_decision_id="decision-a",
    reconciliation_context_id="context-a",
    decision_sequence=1,
):
    return LogicalEffectBinding(
        logical_identity=LogicalEffectIdentity("intent-a", logical_id),
        effect_request_id=request_id,
        effect_type=effect_type,
        authority_decision_id=authority_decision_id,
        reconciliation_context_id=reconciliation_context_id,
        decision_sequence=decision_sequence,
        authority_contract_version="v1",
    )


def _receipt(receipt_id="receipt-reduce", quantity="4"):
    return {
        "receipt_id": receipt_id,
        "order_id": f"order-{receipt_id}",
        "fills": [{"fill_id": f"fill-{receipt_id}", "qty": quantity}],
        "executed_base_qty": quantity,
        "status": "FILLED",
        "normalization_version": "1",
    }


def _bind(ledger, binding):
    return ledger.bind_logical_effect(
        logical_identity=binding.logical_identity,
        effect_request_id=binding.effect_request_id,
        effect_type=binding.effect_type,
        authority_decision_id=binding.authority_decision_id,
        reconciliation_context_id=binding.reconciliation_context_id,
        decision_sequence=binding.decision_sequence,
        authority_contract_version=binding.authority_contract_version,
    )


def _seed_position(connection):
    ledger = EffectApplicationLedger(connection)
    open_binding = _binding(
        logical_id="logical-open",
        request_id="request-open",
        effect_type=EffectType.OPEN,
    )
    _bind(ledger, open_binding)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.position
            (position_id, intent_id, symbol, lifecycle_state, current_quantity,
             open_effect_request_id, position_lifecycle_version)
            VALUES ('position-1', 'intent-a', 'BTCUSDC', 'ACTIVE', 10,
                    'request-open', 1)
            """
        )
    connection.commit()
    return ledger


def _seed_authorized(connection, binding=None):
    ledger = _seed_position(connection)
    binding = binding or _binding()
    _bind(ledger, binding)
    return ledger, binding, _receipt()


def _seed_applied(connection, binding=None):
    ledger, binding, receipt = _seed_authorized(connection, binding)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    with ledger.transaction_scope() as cursor:
        ledger.claim_application(
            binding.effect_request_id,
            application_attempt_id="attempt-reduce",
            claimant_id="fixture",
            cursor=cursor,
        )
        authority.apply_reduction(
            position_id="position-1",
            applied_quantity=Decimal("4"),
            receipt=receipt,
            effect_request_id=binding.effect_request_id,
            cursor=cursor,
            reconciliation_context_id=binding.reconciliation_context_id,
            semantic_decision_id=binding.authority_decision_id,
            decision_sequence=binding.decision_sequence,
            authority_contract_version=binding.authority_contract_version,
        )
        ledger.mark_applied(
            binding.effect_request_id,
            application_attempt_id="attempt-reduce",
            receipt=_ledger_test._receipt("ledger-reduce"),
            cursor=cursor,
        )
    return ledger, authority, binding, receipt


def _seed_unknown(connection, binding=None):
    ledger, binding, receipt = _seed_authorized(connection, binding)
    ledger.claim_application(
        binding.effect_request_id,
        application_attempt_id="attempt-unknown",
        claimant_id="fixture",
    )
    ledger.mark_outcome_unknown(
        binding.effect_request_id,
        application_attempt_id="attempt-unknown",
        reason="C4D fixture",
    )
    return ledger, binding, receipt


def _seed_failed_without_effect(connection, binding=None):
    ledger, binding, receipt = _seed_authorized(connection, binding)
    ledger.claim_application(
        binding.effect_request_id,
        application_attempt_id="attempt-failed",
        claimant_id="fixture",
    )
    ledger.mark_failed_without_effect(
        binding.effect_request_id,
        application_attempt_id="attempt-failed",
        evidence=(
            {
                "evidence_id": "no-effect-proof",
                "proof_type": "AUTHORITATIVE_NO_EFFECT",
            },
        ),
    )
    return ledger, binding, receipt


def _seed_recovery_applied_without_position_event(connection):
    ledger = EffectApplicationLedger(
        connection, trusted_issuers=_ledger_test.TEST_TRUSTED_ISSUERS
    )
    binding = _binding(
        logical_id="logical-recovery",
        request_id="request-recovery",
    )
    _bind(ledger, binding)
    ledger.claim_application(
        binding.effect_request_id,
        application_attempt_id="attempt-recovery",
        claimant_id="fixture",
    )
    evidence = ({"evidence_id": "recovery-proof", "proof_type": "EXCHANGE_QUERY"},)
    ledger.mark_outcome_unknown(
        binding.effect_request_id,
        application_attempt_id="attempt-recovery",
        reason="C4D recovery fixture",
        evidence=evidence,
    )
    ledger.recover_application(
        binding.effect_request_id,
        recovery_authority_id="recovery-issuer",
        recovery_policy_version="v1",
        classification="APPLIED",
        evidence=evidence,
        receipt=_ledger_test._receipt("recovered-ledger"),
        recovery_capability=_ledger_test._recovery_capability(
            effect_request_id=binding.effect_request_id,
            application_attempt_id="attempt-recovery",
            allowed_classification="APPLIED",
            evidence=evidence,
            nonce="nonce-recovery",
        ),
        recovery_subject_id="recovery-worker",
    )
    return ledger, binding, _receipt("position-recovery")


def _extent(receipt):
    payload = json.dumps(
        {"order_id": str(receipt["order_id"]), "fills": receipt["fills"]},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _seed_contradictory_applied(connection):
    ledger, binding, receipt = _seed_authorized(
        connection,
        _binding(logical_id="logical-contradiction", request_id="request-contradiction"),
    )
    ledger.claim_application(
        binding.effect_request_id,
        application_attempt_id="attempt-contradiction",
        claimant_id="fixture",
    )
    extent = _extent(receipt)
    payload = json.dumps(receipt, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    with ledger.transaction_scope() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.position_receipt
            (receipt_id, external_order_identity, execution_extent_identity,
             executed_base_quantity, external_status, receipt_payload,
             receipt_digest, normalization_version)
            VALUES (%s,%s,%s,4,'FILLED',%s::jsonb,%s,'1')
            """,
            (receipt["receipt_id"], receipt["order_id"], extent, payload, digest),
        )
        cursor.execute(
            """
            INSERT INTO handa_live.position_effect_event
            (position_id, intent_id, effect_type, effect_request_id,
             application_attempt_id, external_order_identity,
             execution_extent_identity, receipt_id, previous_quantity,
             applied_quantity, resulting_quantity, event_sequence,
             reconciliation_context_id, semantic_decision_id, decision_sequence,
             authority_contract_version)
            VALUES ('position-1','intent-a','REDUCE',%s,'attempt-contradiction',
                    %s,%s,%s,10,4,6,1,'context-a','decision-other',1,'v1')
            """,
            (
                binding.effect_request_id,
                receipt["order_id"],
                extent,
                receipt["receipt_id"],
            ),
        )
        cursor.execute(
            """
            UPDATE handa_live.position
            SET current_quantity=6, position_lifecycle_version=2
            WHERE position_id='position-1'
            """
        )
        ledger.mark_applied(
            binding.effect_request_id,
            application_attempt_id="attempt-contradiction",
            receipt=_ledger_test._receipt("ledger-contradiction"),
            cursor=cursor,
        )
    return ledger, binding, receipt


def _coordinator_or_not_yet_reached():
    try:
        module = importlib.import_module(MODULE)
    except ModuleNotFoundError as error:
        if error.name == MODULE:
            pytest.skip("NOT_YET_REACHED: public C4D coordinator is absent")
        raise
    coordinator_type = getattr(module, "EffectApplicationCoordinator")
    return module, coordinator_type


def _coordinator(ledger, authority):
    _, coordinator_type = _coordinator_or_not_yet_reached()
    return coordinator_type(ledger=ledger, position_authority=authority)


def _apply(coordinator, binding, receipt, *, attempt_id="attempt-new"):
    return coordinator.apply(
        logical_binding=binding,
        application_attempt_id=attempt_id,
        claimant_id="c4d-test-worker",
        position_id="position-1",
        receipt=receipt,
        applied_quantity=Decimal("4"),
        intended_quantity=Decimal("4"),
        external_order_id=receipt["order_id"],
        symbol="BTCUSDC",
    )


def _counts(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM handa_live.effect_request),
              (SELECT COUNT(*) FROM handa_live.application_attempt),
              (SELECT COUNT(*) FROM handa_live.applied_effect),
              (SELECT COUNT(*) FROM handa_live.position_effect_event),
              (SELECT COUNT(*) FROM handa_live.position_receipt)
            """
        )
        return cursor.fetchone()


def _position(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT lifecycle_state, current_quantity, position_lifecycle_version
            FROM handa_live.position WHERE position_id='position-1'
            """
        )
        return cursor.fetchone()


def _request(connection, request_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT current_state, current_attempt_id
            FROM handa_live.effect_request WHERE effect_request_id=%s
            """,
            (request_id,),
        )
        return cursor.fetchone()


def _classification(value):
    status = getattr(value, "classification", None)
    if status is None:
        status = getattr(value, "status", None)
    return getattr(status, "value", status)


def _effect_request_id(value):
    return getattr(value, "effect_request_id", None)


def _assert_fail_closed(error, *needles):
    text = str(error.value if hasattr(error, "value") else error).upper()
    assert any(needle.upper() in text for needle in needles)


def test_c4d001_public_coordinator_boundary():
    module = importlib.import_module(MODULE)
    coordinator = getattr(module, "EffectApplicationCoordinator")
    assert inspect.isclass(coordinator)
    assert "ledger" in inspect.signature(coordinator).parameters
    assert "position_authority" in inspect.signature(coordinator).parameters
    apply_signature = inspect.signature(coordinator.apply)
    assert {
        "logical_binding",
        "application_attempt_id",
        "claimant_id",
        "position_id",
        "receipt",
        "applied_quantity",
    } <= set(apply_signature.parameters)


def test_c4d002_new_canonical_binding_applies_once(connection):
    ledger = _seed_position(connection)
    binding = _binding()
    receipt = _receipt()
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    coordinator = _coordinator(ledger, authority)
    result = _apply(coordinator, binding, receipt)
    assert _effect_request_id(result) == binding.effect_request_id
    assert _request(connection, binding.effect_request_id) == (
        "APPLIED", "attempt-new"
    )
    assert _counts(connection)[1:] == (1, 1, 1, 1)
    assert _position(connection) == ("ACTIVE", Decimal("6"), 2)


def test_c4d003_existing_authorized_binding_applies_once(connection):
    ledger, binding, receipt = _seed_authorized(connection)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    result = _apply(_coordinator(ledger, authority), binding, receipt)
    assert _effect_request_id(result) == binding.effect_request_id
    assert _counts(connection)[1:] == (1, 1, 1, 1)
    assert _position(connection) == ("ACTIVE", Decimal("6"), 2)


def test_c4d004_applied_binding_uses_c4c_replay(connection, monkeypatch):
    ledger, authority, binding, receipt = _seed_applied(connection)

    def forbidden(*args, **kwargs):
        raise AssertionError("APPLIED replay attempted a mutation")

    monkeypatch.setattr(ledger, "claim_application", forbidden)
    monkeypatch.setattr(ledger, "mark_applied", forbidden)
    monkeypatch.setattr(authority, "apply_reduction", forbidden)
    before = _counts(connection)
    result = _apply(_coordinator(ledger, authority), binding, receipt, attempt_id="replay")
    assert _effect_request_id(result) == binding.effect_request_id
    assert _counts(connection) == before


def test_c4d005_applied_replay_performs_zero_writes(connection, monkeypatch):
    ledger, authority, binding, receipt = _seed_applied(connection)

    def forbidden(*args, **kwargs):
        raise AssertionError("C4D replay attempted a write boundary")

    monkeypatch.setattr(ledger, "claim_application", forbidden)
    monkeypatch.setattr(ledger, "mark_applied", forbidden)
    monkeypatch.setattr(authority, "apply_reduction", forbidden)
    before = (_counts(connection), _position(connection), _request(connection, binding.effect_request_id))
    _apply(_coordinator(ledger, authority), binding, receipt, attempt_id="replay-zero-write")
    after = (_counts(connection), _position(connection), _request(connection, binding.effect_request_id))
    assert after == before


def test_c4d006_same_logical_effect_converges_under_concurrent_race(connection):
    ledger = _seed_position(connection)
    binding = _binding(logical_id="logical-race", request_id="request-race")
    receipt = _receipt("receipt-race")
    conn_a = psycopg2.connect(_database_url())
    conn_b = psycopg2.connect(_database_url())

    def invoke(conn, attempt_id):
        local_ledger = EffectApplicationLedger(conn)
        local_authority = PositionEffectAuthority(connection=conn, ledger=local_ledger)
        return _apply(_coordinator(local_ledger, local_authority), binding, receipt, attempt_id=attempt_id)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda item: invoke(*item),
                    ((conn_a, "attempt-race-a"), (conn_b, "attempt-race-b")),
                )
            )
    finally:
        conn_a.close()
        conn_b.close()
    assert [_effect_request_id(result) for result in results] == [
        binding.effect_request_id,
        binding.effect_request_id,
    ]
    assert _counts(connection)[1:] == (1, 1, 1, 1)
    assert _position(connection) == ("ACTIVE", Decimal("6"), 2)


def test_c4d007_mark_applied_failure_rolls_back_position_mutation(connection, monkeypatch):
    ledger, binding, receipt = _seed_authorized(connection)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    before = (_counts(connection), _position(connection), _request(connection, binding.effect_request_id))

    def fail_mark(*args, **kwargs):
        raise RuntimeError("synthetic mark_applied failure")

    monkeypatch.setattr(ledger, "mark_applied", fail_mark)
    with pytest.raises(RuntimeError, match="synthetic mark_applied failure"):
        _apply(_coordinator(ledger, authority), binding, receipt)
    assert (_counts(connection), _position(connection), _request(connection, binding.effect_request_id)) == before


def test_c4d008_position_effect_failure_rolls_back_ledger_claim(connection, monkeypatch):
    ledger, binding, receipt = _seed_authorized(connection)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    before = (_counts(connection), _position(connection), _request(connection, binding.effect_request_id))

    def fail_position(*args, **kwargs):
        raise RuntimeError("synthetic position effect failure")

    monkeypatch.setattr(authority, "apply_reduction", fail_position)
    with pytest.raises(RuntimeError, match="synthetic position effect failure"):
        _apply(_coordinator(ledger, authority), binding, receipt)
    assert (_counts(connection), _position(connection), _request(connection, binding.effect_request_id)) == before


def test_c4d009_outcome_unknown_requires_recovery_and_never_auto_recovers(connection, monkeypatch):
    ledger, binding, receipt = _seed_unknown(connection)

    def forbidden(*args, **kwargs):
        raise AssertionError("C4D invoked recovery authority")

    monkeypatch.setattr(ledger, "recover_application", forbidden)
    before = _counts(connection)
    result = _apply(_coordinator(ledger, PositionEffectAuthority(connection=connection, ledger=ledger)), binding, receipt)
    assert _classification(result) == "RECOVERY_REQUIRED"
    assert _counts(connection) == before


def test_c4d010_applying_never_gets_a_second_claim(connection, monkeypatch):
    ledger, binding, receipt = _seed_authorized(connection)
    ledger.claim_application(
        binding.effect_request_id,
        application_attempt_id="attempt-applying",
        claimant_id="existing-worker",
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("APPLYING request was claimed again")

    monkeypatch.setattr(ledger, "claim_application", forbidden)
    result = _apply(_coordinator(ledger, PositionEffectAuthority(connection=connection, ledger=ledger)), binding, receipt, attempt_id="attempt-second")
    assert _classification(result) == "RECOVERY_REQUIRED"
    assert _request(connection, binding.effect_request_id) == (
        "APPLYING", "attempt-applying"
    )


def test_c4d011_failed_without_effect_never_auto_reapplies(connection, monkeypatch):
    ledger, binding, receipt = _seed_failed_without_effect(connection)

    def forbidden(*args, **kwargs):
        raise AssertionError("terminal FAILED_WITHOUT_EFFECT was reapplied")

    monkeypatch.setattr(ledger, "claim_application", forbidden)
    monkeypatch.setattr(ledger, "mark_applied", forbidden)
    before = _counts(connection)
    result = _apply(_coordinator(ledger, PositionEffectAuthority(connection=connection, ledger=ledger)), binding, receipt, attempt_id="attempt-reapply")
    assert _classification(result) == "FAILED_WITHOUT_EFFECT"
    assert _counts(connection) == before


def test_c4d012_conflicting_canonical_binding_fails_closed(connection):
    ledger, binding, receipt = _seed_authorized(connection)
    _ledger_test._decision(
        connection,
        decision_id="decision-other",
        context_id="context-a",
        intent_id="intent-a",
        sequence=2,
    )
    connection.commit()
    conflicting = _binding(
        logical_id=binding.logical_identity.logical_effect_id,
        request_id="request-conflict-candidate",
        authority_decision_id="decision-other",
        decision_sequence=2,
    )
    before = (_counts(connection), _position(connection))
    with pytest.raises(Exception) as error:
        _apply(_coordinator(ledger, PositionEffectAuthority(connection=connection, ledger=ledger)), conflicting, receipt)
    _assert_fail_closed(error, "CONFLICT", "FAIL_CLOSED")
    assert (_counts(connection), _position(connection)) == before


def test_c4d013_c4c_durable_contradiction_prevents_reapply(connection):
    ledger, binding, receipt = _seed_contradictory_applied(connection)
    coordinator = _coordinator(ledger, PositionEffectAuthority(connection=connection, ledger=ledger))
    with pytest.raises(Exception) as error:
        _apply(coordinator, binding, receipt, attempt_id="attempt-contradiction-replay")
    _assert_fail_closed(error, "DURABLE_DATA_CONTRADICTION")
    assert _counts(connection)[1:] == (1, 1, 1, 1)


def test_c4d014_recovery_applied_without_position_event_prevents_reapply(connection):
    ledger, binding, receipt = _seed_recovery_applied_without_position_event(connection)
    coordinator = _coordinator(ledger, PositionEffectAuthority(connection=connection, ledger=ledger))
    with pytest.raises(Exception) as error:
        _apply(coordinator, binding, receipt, attempt_id="attempt-recovery-replay")
    _assert_fail_closed(error, "APPLIED_POSITION_RESULT_NOT_RECONSTRUCTABLE")
    assert _counts(connection)[1:] == (1, 1, 0, 0)


def test_c4d015_post_commit_caller_loss_replay_is_idempotent(connection):
    ledger, authority, binding, receipt = _seed_applied(connection)
    coordinator = _coordinator(ledger, authority)
    first = _apply(coordinator, binding, receipt, attempt_id="lost-response")
    second = _apply(coordinator, binding, receipt, attempt_id="new-invocation")
    assert _effect_request_id(first) == _effect_request_id(second) == binding.effect_request_id
    assert _counts(connection)[1:] == (1, 1, 1, 1)
    assert _position(connection) == ("ACTIVE", Decimal("6"), 2)


def test_c4d016_execution_extent_cannot_be_consumed_twice(connection):
    ledger = _seed_position(connection)
    first = _binding(logical_id="logical-first", request_id="request-first")
    second = _binding(logical_id="logical-second", request_id="request-second")
    receipt = _receipt("receipt-shared")
    _bind(ledger, first)
    _bind(ledger, second)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    coordinator = _coordinator(ledger, authority)
    _apply(coordinator, first, receipt, attempt_id="attempt-first")
    with pytest.raises(Exception) as error:
        _apply(coordinator, second, receipt, attempt_id="attempt-second")
    _assert_fail_closed(error, "EXTENT", "already", "duplicate", "unique")
    assert _counts(connection)[1:] == (1, 1, 1, 1)
    assert _position(connection) == ("ACTIVE", Decimal("6"), 2)


def test_c4d017_coordinator_has_no_external_submit_or_retry_capability():
    module, coordinator_type = _coordinator_or_not_yet_reached()
    source = inspect.getsource(module)
    forbidden = (
        "order_market",
        "submit_order",
        "external_submit",
        "resubmit",
        "retry_order",
        "recover_application",
    )
    assert all(token not in source for token in forbidden)
    public_methods = {
        name for name, member in inspect.getmembers(coordinator_type, inspect.isfunction)
        if not name.startswith("_")
    }
    assert public_methods <= {"apply"}
