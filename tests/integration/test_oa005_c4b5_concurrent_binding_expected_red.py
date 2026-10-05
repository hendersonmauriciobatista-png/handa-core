"""C4B-5 falsifiers for real cross-session canonical-binding contention."""

from importlib import import_module
import inspect
import os
from pathlib import Path
import queue
import threading
import time
from types import SimpleNamespace
from urllib.parse import urlparse

import psycopg2
import pytest

from core.execution.operational_effect_adapter import EffectType, LogicalEffectIdentity
from core.persistence.effect_application_ledger import EffectApplicationLedger
from tests.integration import test_effect_application_ledger_postgres as _postgres


ROOT = Path(__file__).parents[2]
MIGRATIONS_DIR = ROOT / "core" / "persistence" / "migrations"
EXPECTED_DATABASE = "handa_test"
EXPECTED_USER = "handa_test"
EXPECTED_HOSTS = {"127.0.0.1", "localhost"}
EXPECTED_PORT = 55432
BLOCK_TIMEOUT_SECONDS = 5.0
JOIN_TIMEOUT_SECONDS = 5.0


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


def _connect():
    try:
        return psycopg2.connect(_database_url())
    except (OSError, psycopg2.Error) as exc:
        pytest.skip(f"ENVIRONMENT_BLOCKED: disposable PostgreSQL unavailable: {exc}")


@pytest.fixture()
def connection():
    connection = _connect()
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
        connection.close()
        cleanup = _connect()
        try:
            with cleanup.cursor() as cursor:
                cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            cleanup.commit()
        finally:
            cleanup.close()


def _bind_kwargs(
    *,
    logical_id="logical-c4b5",
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


def _counts(connection, logical_id=None):
    with connection.cursor() as cursor:
        if logical_id is None:
            cursor.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM handa_live.effect_request),
                    (SELECT COUNT(*) FROM handa_live.authority_binding),
                    (SELECT COUNT(*) FROM handa_live.lifecycle_event)
                """
            )
        else:
            cursor.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM handa_live.effect_request
                     WHERE intent_id='intent-a' AND logical_effect_id=%s),
                    (SELECT COUNT(*) FROM handa_live.authority_binding ab
                     JOIN handa_live.effect_request er
                       ON er.effect_request_id=ab.effect_request_id
                     WHERE er.intent_id='intent-a' AND er.logical_effect_id=%s),
                    (SELECT COUNT(*) FROM handa_live.lifecycle_event le
                     JOIN handa_live.effect_request er
                       ON er.effect_request_id=le.effect_request_id
                     WHERE er.intent_id='intent-a' AND er.logical_effect_id=%s)
                """,
                (logical_id, logical_id, logical_id),
            )
        return cursor.fetchone()


def _start_uncommitted_binding(connection, values):
    ledger = EffectApplicationLedger(connection)
    cursor = connection.cursor()
    cursor.execute("BEGIN")
    cursor.execute("SELECT pg_backend_pid()")
    backend_pid = cursor.fetchone()[0]
    result = ledger.bind_logical_effect(cursor=cursor, **values)
    return cursor, backend_pid, result


def _wait_for_blocking(observer, blocked_pid, blocker_pid):
    deadline = time.monotonic() + BLOCK_TIMEOUT_SECONDS
    evidence = []
    while time.monotonic() < deadline:
        with observer.cursor() as cursor:
            cursor.execute("SELECT pg_blocking_pids(%s)", (blocked_pid,))
            blockers = cursor.fetchone()[0]
        evidence.append(tuple(blockers))
        if blocker_pid in blockers:
            return True, evidence
        time.sleep(0.02)
    return False, evidence


def _race(
    connection,
    *,
    logical_id="logical-c4b5",
    logical_id_b=None,
    candidate_a="request-a",
    candidate_b="request-b",
    b_values=None,
    winner_action="commit",
):
    session_a = _connect()
    observer = _connect()
    ready = queue.Queue()
    outcome = queue.Queue()
    release_started = threading.Event()

    values_a = _bind_kwargs(logical_id=logical_id, request_id=candidate_a)
    values_b = dict(
        _bind_kwargs(logical_id=logical_id_b or logical_id, request_id=candidate_b),
        **(b_values or {}),
    )

    def session_b_worker():
        session_b = _connect()
        try:
            ledger = EffectApplicationLedger(session_b)
            with session_b.cursor() as cursor:
                cursor.execute("BEGIN")
                cursor.execute("SELECT pg_backend_pid()")
                ready.put(cursor.fetchone()[0])
                release_started.wait(BLOCK_TIMEOUT_SECONDS)
                try:
                    result = ledger.bind_logical_effect(cursor=cursor, **values_b)
                    cursor.execute("SELECT 1")
                    outcome.put(
                        {
                            "kind": "result",
                            "disposition": result.disposition.value,
                            "binding_id": result.binding.effect_request_id,
                            "usable": cursor.fetchone() == (1,),
                        }
                    )
                except Exception as exc:
                    usable = False
                    try:
                        cursor.execute("SELECT 1")
                        usable = cursor.fetchone() == (1,)
                    except Exception:
                        pass
                    outcome.put(
                        {
                            "kind": "error",
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                            "usable": usable,
                        }
                    )
                finally:
                    session_b.rollback()
        finally:
            session_b.close()

    try:
        cursor_a, pid_a, result_a = _start_uncommitted_binding(session_a, values_a)
        thread = threading.Thread(target=session_b_worker, daemon=True)
        started_at = time.monotonic()
        thread.start()
        pid_b = ready.get(timeout=BLOCK_TIMEOUT_SECONDS)
        release_started.set()
        contention, evidence = _wait_for_blocking(observer, pid_b, pid_a)
        if winner_action == "commit":
            session_a.commit()
        else:
            session_a.rollback()
        thread.join(JOIN_TIMEOUT_SECONDS)
        if thread.is_alive():
            raise AssertionError("UNBOUNDED_WAIT: session B did not complete")
        result_b = outcome.get(timeout=1)
        elapsed = time.monotonic() - started_at
        return {
            "a": result_a,
            "a_id": candidate_a,
            "b": result_b,
            "b_id": candidate_b,
            "pid_a": pid_a,
            "pid_b": pid_b,
            "contention": contention,
            "lock_evidence": evidence,
            "elapsed": elapsed,
        }
    finally:
        release_started.set()
        try:
            session_a.rollback()
        finally:
            cursor_a.close()
            session_a.close()
            observer.close()


def test_c4b5001_real_same_logical_convergence(connection):
    race = _race(connection)
    assert race["contention"] is True
    assert race["a"].disposition.value == "CREATED_CANONICAL_BINDING"
    assert race["b"]["disposition"] == "EXISTING_VALID_BINDING"
    assert race["b"]["binding_id"] == "request-a"
    assert _counts(connection, "logical-c4b5") == (1, 1, 1)


def test_c4b5002_actual_contention_is_observed(connection):
    race = _race(connection, logical_id="logical-lock")
    assert race["contention"] is True
    assert any(race["pid_a"] in blockers for blockers in race["lock_evidence"])


def test_c4b5003_single_canonical_effect_request(connection):
    _race(connection, logical_id="logical-single")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*), MIN(effect_request_id)
            FROM handa_live.effect_request
            WHERE intent_id='intent-a' AND logical_effect_id='logical-single'
            """
        )
        assert cursor.fetchone() == (1, "request-a")


def test_c4b5004_single_authority_foundation(connection):
    _race(connection, logical_id="logical-foundation")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                COUNT(DISTINCT ab.effect_request_id),
                COUNT(DISTINCT le.lifecycle_event_id),
                MIN(er.current_state),
                COUNT(aa.application_attempt_id)
            FROM handa_live.effect_request er
            JOIN handa_live.authority_binding ab
              ON ab.effect_request_id=er.effect_request_id
            JOIN handa_live.lifecycle_event le
              ON le.effect_request_id=er.effect_request_id
            LEFT JOIN handa_live.application_attempt aa
              ON aa.effect_request_id=er.effect_request_id
            WHERE er.logical_effect_id='logical-foundation'
            """
        )
        assert cursor.fetchone() == (1, 1, "AUTHORIZED", 0)


def test_c4b5005_loser_candidate_never_durable(connection):
    _race(connection, logical_id="logical-loser")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM handa_live.effect_request
            WHERE effect_request_id='request-b'
               OR logical_effect_id='logical-loser'
            """
        )
        assert cursor.fetchone() == (1,)
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM handa_live.authority_binding ab
            LEFT JOIN handa_live.effect_request er
              ON er.effect_request_id=ab.effect_request_id
            WHERE ab.effect_request_id='request-b'
               OR er.logical_effect_id='logical-loser'
            """
        )
        assert cursor.fetchone() == (1,)


def test_c4b5006_caller_transaction_survives_handled_collision(connection):
    race = _race(connection, logical_id="logical-usable")
    assert race["b"]["kind"] == "result"
    assert race["b"]["usable"] is True


def test_c4b5007_concurrent_authority_conflict(connection):
    race = _race(
        connection,
        logical_id="logical-conflict",
        b_values={"effect_type": EffectType.CLOSE},
    )
    assert race["contention"] is True
    assert race["b"]["disposition"] == "CONFLICTING_BINDING"
    assert race["b"]["binding_id"] == "request-a"


def test_c4b5008_concurrent_conflict_does_not_overwrite(connection):
    _race(
        connection,
        logical_id="logical-preserve",
        b_values={
            "effect_type": EffectType.CLOSE,
            "authority_decision_id": "decision-other",
            "reconciliation_context_id": "context-other",
            "decision_sequence": 2,
            "authority_contract_version": "v2",
        },
    )
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT er.effect_request_id, er.effect_type,
                   ab.authority_decision_id, ab.reconciliation_context_id,
                   ab.decision_sequence, ab.authority_contract_version
            FROM handa_live.effect_request er
            JOIN handa_live.authority_binding ab
              ON ab.effect_request_id=er.effect_request_id
            WHERE er.logical_effect_id='logical-preserve'
            """
        )
        assert cursor.fetchone() == (
            "request-a", "OPEN", "decision-a", "context-a", 1, "v1"
        )


def test_c4b5009_winner_rollback_second_binder_succeeds(connection):
    race = _race(
        connection,
        logical_id="logical-rollback",
        winner_action="rollback",
    )
    assert race["contention"] is True
    assert race["b"]["disposition"] == "CREATED_CANONICAL_BINDING"
    assert race["b"]["binding_id"] == "request-b"


def test_c4b5010_rolled_back_candidate_leaves_no_orphan(connection):
    _race(connection, logical_id="logical-no-orphan", winner_action="rollback")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM handa_live.effect_request
                 WHERE effect_request_id='request-a'),
                (SELECT COUNT(*) FROM handa_live.authority_binding
                 WHERE effect_request_id='request-a'),
                (SELECT COUNT(*) FROM handa_live.lifecycle_event
                 WHERE effect_request_id='request-a')
            """
        )
        assert cursor.fetchone() == (0, 0, 0)


def test_c4b5011_cross_session_commit_durability(connection):
    session = _connect()
    try:
        EffectApplicationLedger(session).bind_logical_effect(
            **_bind_kwargs(logical_id="logical-durable", request_id="request-durable")
        )
    finally:
        session.close()
    fresh = _connect()
    try:
        lookup_values = _bind_kwargs(logical_id="logical-durable", request_id="ignored")
        lookup_values.pop("effect_request_id")
        result = EffectApplicationLedger(fresh).lookup_logical_binding(
            **lookup_values
        )
        assert result.disposition.value == "FOUND_VALID_BINDING"
        assert result.binding.effect_request_id == "request-durable"
    finally:
        fresh.close()


def test_c4b5012_cross_session_rebind_reuses_canonical(connection):
    session = _connect()
    try:
        ledger = EffectApplicationLedger(session)
        ledger.bind_logical_effect(
            **_bind_kwargs(logical_id="logical-rebind", request_id="request-canonical")
        )
    finally:
        session.close()
    fresh = _connect()
    try:
        result = EffectApplicationLedger(fresh).bind_logical_effect(
            **_bind_kwargs(logical_id="logical-rebind", request_id="request-third")
        )
        assert result.disposition.value == "EXISTING_VALID_BINDING"
        assert result.binding.effect_request_id == "request-canonical"
        with fresh.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM handa_live.effect_request WHERE effect_request_id='request-third'"
            )
            assert cursor.fetchone() == (0,)
    finally:
        fresh.close()


def test_c4b5013_concurrent_candidate_primary_key_collision(connection):
    race = _race(
        connection,
        logical_id="logical-one",
        logical_id_b="logical-two",
        candidate_a="request-shared",
        candidate_b="request-shared",
    )
    assert race["contention"] is True
    assert race["b"]["kind"] == "error"
    assert race["b"]["error_type"] == "EffectApplicationLedgerError"
    assert "candidate" not in race["b"]["error"]
    assert race["b"]["usable"] is True
    assert _counts(connection, "logical-two") == (0, 0, 0)


def test_c4b5014_bounded_completion_no_deadlock(connection):
    race = _race(connection, logical_id="logical-bounded")
    assert race["elapsed"] < BLOCK_TIMEOUT_SECONDS + JOIN_TIMEOUT_SECONDS
    assert race["contention"] is True


def test_c4b5015_c4b3_lookup_remains_read_only(connection):
    ledger = EffectApplicationLedger(connection)
    ledger.bind_logical_effect(**_bind_kwargs(logical_id="logical-read-only"))
    before = _counts(connection)
    lookup_values = _bind_kwargs(logical_id="logical-read-only", request_id="ignored")
    lookup_values.pop("effect_request_id")
    result = ledger.lookup_logical_binding(
        **lookup_values
    )
    assert result.disposition.value == "FOUND_VALID_BINDING"
    assert _counts(connection) == before
    assert "effect_request_id" not in inspect.signature(
        ledger.lookup_logical_binding
    ).parameters


def test_c4b5016_no_c4c_behavior_is_present():
    source = inspect.getsource(import_module("core.execution.operational_effect_adapter"))
    forbidden = (
        "AppliedEffectReplayRecord",
        "PositionEffectResult",
        "mark_applied",
        "claim_application",
    )
    assert all(token not in source for token in forbidden)


def test_c4b5017_no_c4d_behavior_is_present():
    source = inspect.getsource(import_module("core.execution.operational_effect_adapter"))
    forbidden = ("outer transaction", "order_market", "resubmit", "retry")
    assert all(token not in source for token in forbidden)


def test_c4b5018_operational_adapter_behavior_remains_unchanged():
    module = import_module("core.execution.operational_effect_adapter")

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
