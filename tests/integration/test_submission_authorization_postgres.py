"""Focused PostgreSQL tests for the durable one-time claim boundary."""

from __future__ import annotations

import os
import threading
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import urlparse

import psycopg2
import pytest

from core.execution.governed_mock_submission_gateway import GovernedMockSubmissionGateway
from core.execution.live_order_models import LiveOrderIntent, OrderSide
from core.execution.submission_authority import (
    ClaimDisposition,
    ClaimedSubmissionCapability,
    SubmissionClaimRequest,
    is_valid_claimed_submission_capability,
    submission_fingerprint,
)
from core.persistence.live_order_store import LiveOrderStore, live_order_resource_scope
from core.persistence.persistence_coordinator import DatabaseIdentity, PersistenceCoordinator
from core.persistence.submission_authorization_store import (
    SubmissionAuthorizationStore,
    submission_authorization_resource_scope,
)
from core.persistence.transaction_context import PersistenceFailure


ROOT = Path(__file__).parents[2]
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
        "009_submission_authorization.sql",
        "010_submission_authority_envelope_and_decision.sql",
        "011_pre_execution_evaluation_idempotency.sql",
    )
)
EXPECTED_URL = "postgresql://handa_test:handa_test_only@127.0.0.1:55432/handa_test"
EXPECTED_DATABASE = "handa_test"
EXPECTED_USER = "handa_test"
EXPECTED_HOSTS = frozenset({"127.0.0.1", "localhost"})
EXPECTED_PORT = 55432


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value != EXPECTED_URL:
        pytest.skip("ENVIRONMENT_BLOCKED: disposable local PostgreSQL is required")
    parsed = urlparse(value)
    if (
        parsed.hostname not in EXPECTED_HOSTS
        or parsed.port != EXPECTED_PORT
        or parsed.path.lstrip("/") != EXPECTED_DATABASE
        or parsed.username != EXPECTED_USER
    ):
        pytest.fail("test database identity is outside the governed disposable database")
    return value


def _identity() -> DatabaseIdentity:
    return DatabaseIdentity(EXPECTED_HOSTS, EXPECTED_PORT, EXPECTED_DATABASE, EXPECTED_USER)


def _bootstrap(url: str) -> None:
    connection = psycopg2.connect(url)
    try:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            for migration in MIGRATIONS:
                cursor.execute(migration.read_text(encoding="utf-8"))
        connection.commit()
    finally:
        connection.close()


def _coordinator(url: str) -> PersistenceCoordinator:
    return PersistenceCoordinator(
        url,
        _identity(),
        resource_scope=submission_authorization_resource_scope(),
    )


def _request(**overrides) -> SubmissionClaimRequest:
    values = {
        "submission_authorization_id": "auth-submit-001",
        "expected_version": 0,
        "claimant_id": "runtime-claimant-001",
        "intent_id": "intent-submit-001",
        "submission_attempt_id": "attempt-submit-001",
        "client_order_id": "client-submit-001",
        "venue": "MOCK",
        "account_scope": "TEST",
        "symbol": "HYPEUSDC",
        "side": "BUY",
        "requested_quote_amount": Decimal("41.4117522032984"),
        "requested_base_qty": None,
    }
    values["submission_fingerprint"] = submission_fingerprint(**{
        key: values[key]
        for key in (
            "intent_id", "submission_attempt_id", "client_order_id", "venue",
            "account_scope", "symbol", "side", "requested_quote_amount",
            "requested_base_qty",
        )
    })
    values.update(overrides)
    return SubmissionClaimRequest(**values)


@pytest.fixture()
def prepared():
    url = _database_url()
    _bootstrap(url)
    live_coordinator = PersistenceCoordinator(
        url, _identity(), resource_scope=live_order_resource_scope()
    )
    live_store = LiveOrderStore(live_coordinator)
    live_store.create_intent(
        LiveOrderIntent(
            intent_id="intent-submit-001",
            client_order_id="client-submit-001",
            slot_id="slot-submit-001",
            symbol="HYPEUSDC",
            side=OrderSide.BUY,
            requested_quote_amount=Decimal("41.4117522032984"),
            policy_context="TEST_FIXTURE_ONLY",
        ),
        venue="MOCK",
        account_scope="TEST",
    )
    live_store.record_submission_preparation(
        intent_id="intent-submit-001",
        attempt_id="attempt-submit-001",
        attempt_sequence=1,
        venue="MOCK",
        account_scope="TEST",
        client_order_id="client-submit-001",
        expected_version=0,
    )
    fingerprint = submission_fingerprint(
        intent_id="intent-submit-001",
        submission_attempt_id="attempt-submit-001",
        client_order_id="client-submit-001",
        venue="MOCK",
        account_scope="TEST",
        symbol="HYPEUSDC",
        side="BUY",
        requested_quote_amount=Decimal("41.4117522032984"),
        requested_base_qty=None,
    )
    connection = psycopg2.connect(url)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.authority_envelope (
                authority_envelope_id, runtime_mode, venue, account_scope,
                allowed_sides, strategy_version, decision_contract_version,
                policy_version, risk_policy_version, valid_from, valid_until,
                configuration_digest, authority_contract_version, approved_by,
                approval_reason
            ) VALUES (
                'envelope-submit-001', 'OBSERVE_ONLY', 'MOCK', 'TEST',
                ARRAY['BUY'], 'strategy-test-v1', 'decision-contract-v1',
                'policy-test-v1', 'risk-policy-test-v1',
                CURRENT_TIMESTAMP - INTERVAL '1 second',
                CURRENT_TIMESTAMP + INTERVAL '30 seconds',
                'configuration-digest-test-001', 'submission-authority-v1',
                'fixture-human-only', 'TEST_FIXTURE_AUTHORITY_ONLY'
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO handa_live.pre_execution_decision (
                pre_execution_decision_id, intent_id, submission_attempt_id,
                evaluation_request_id, evaluation_request_digest,
                authority_envelope_id, decision_sequence, decision_outcome,
                decision_reason, intent_semantic_digest,
                submission_attempt_semantic_digest, decision_contract_version,
                decision_engine_version, policy_version, risk_policy_version,
                strategy_version, input_snapshot_digest, decision_semantics_digest,
                global_safety_epoch, runtime_generation, runtime_mode, venue,
                account_scope, evaluated_at, valid_until
            ) VALUES (
                'pre-execution-decision-submit-001',
                'intent-submit-001', 'attempt-submit-001',
                'TEST_ONLY_EVALUATION_IDENTITY-submit-001',
                'TEST_ONLY_EVALUATION_DIGEST-submit-001',
                'envelope-submit-001', 1, 'ALLOW',
                'TEST_FIXTURE_AUTHORITY_ONLY',
                'intent-digest-submit-001', 'attempt-digest-submit-001',
                'decision-contract-v1', 'decision-engine-test-v1',
                'policy-test-v1', 'risk-policy-test-v1', 'strategy-test-v1',
                'input-snapshot-submit-001', 'decision-semantics-submit-001',
                0, 0, 'OBSERVE_ONLY', 'MOCK', 'TEST',
                CURRENT_TIMESTAMP - INTERVAL '1 second',
                CURRENT_TIMESTAMP + INTERVAL '30 seconds'
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO handa_live.submission_authorization (
                submission_authorization_id, intent_id, submission_attempt_id,
                client_order_id, venue, account_scope, symbol, side,
                requested_quote_amount, requested_base_qty,
                authority_reference_id, issuer_id, authority_contract_version,
                authorization_sequence, submission_fingerprint, authorization_state
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, %s, 'AUTHORIZED')
            """,
            (
                "auth-submit-001", "intent-submit-001", "attempt-submit-001",
                "client-submit-001", "MOCK", "TEST", "HYPEUSDC", "BUY",
                Decimal("41.4117522032984"), None,
                "pre-execution-decision-submit-001",
                "fixture-issuer-only", "submission-authority-v1", 1, fingerprint,
            ),
        )
    connection.commit()
    claim_coordinator = _coordinator(url)
    try:
        yield url, claim_coordinator, SubmissionAuthorizationStore(claim_coordinator)
    finally:
        claim_coordinator.close()
        live_coordinator.close()
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
        connection.commit()
        connection.close()


def test_migration_creates_submission_authorization_contract(prepared):
    url, _, _ = prepared
    connection = psycopg2.connect(url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'handa_live' AND table_name = 'submission_authorization'
                ORDER BY ordinal_position
                """
            )
            columns = [row[0] for row in cursor.fetchall()]
        assert "submission_fingerprint" in columns
        assert "claimed_at" in columns
        assert "current_version" in columns
    finally:
        connection.close()


def test_fingerprint_is_deterministic_and_decimal_safe():
    first = submission_fingerprint(
        intent_id="i", submission_attempt_id="a", client_order_id="c",
        venue="MOCK", account_scope="TEST", symbol="BTCUSDC", side="BUY",
        requested_quote_amount=Decimal("10.000"), requested_base_qty=None,
    )
    second = submission_fingerprint(
        intent_id="i", submission_attempt_id="a", client_order_id="c",
        venue="MOCK", account_scope="TEST", symbol="BTCUSDC", side="BUY",
        requested_quote_amount=Decimal("1E+1"), requested_base_qty=None,
    )
    assert first == second
    with pytest.raises(TypeError):
        submission_fingerprint(
            intent_id="i", submission_attempt_id="a", client_order_id="c",
            venue="MOCK", account_scope="TEST", symbol="BTCUSDC", side="BUY",
            requested_quote_amount=10.0,
        )


def test_single_claim_commits_once_and_restart_cannot_rearm(prepared):
    _, coordinator, store = prepared
    result = store.claim_authorization(_request())
    assert result.disposition is ClaimDisposition.CLAIMED
    assert result.capability is not None
    assert result.capability.claimed_version == 1
    assert result.capability.claimed_at is not None
    assert is_valid_claimed_submission_capability(result.capability)

    coordinator.close()
    restarted = _coordinator(_database_url())
    try:
        restarted_result = SubmissionAuthorizationStore(restarted).claim_authorization(_request())
        assert restarted_result.disposition is ClaimDisposition.ALREADY_CLAIMED
        assert restarted_result.capability is None
    finally:
        restarted.close()


def test_identity_mismatches_fail_closed_without_partial_claim(prepared):
    _, _, store = prepared
    mismatches = (
        {"intent_id": "wrong-intent"},
        {"submission_attempt_id": "wrong-attempt"},
        {"client_order_id": "wrong-client"},
        {"venue": "OTHER"},
        {"account_scope": "OTHER"},
        {"symbol": "BTCUSDC"},
        {"side": "SELL"},
        {"requested_quote_amount": Decimal("99")},
        {"submission_fingerprint": "00" * 32},
        {"expected_version": 1},
    )
    for mismatch in mismatches:
        result = store.claim_authorization(_request(**mismatch))
        assert result.disposition is ClaimDisposition.CONFLICT
        assert result.capability is None
        assert store.get_authorization("auth-submit-001")["authorization_state"] == "AUTHORIZED"


def test_cross_session_race_has_one_winner_and_no_retry(prepared):
    url, _, _ = prepared
    barrier = threading.Barrier(2)
    results = []
    errors = []

    def worker(claimant):
        coordinator = _coordinator(url)
        try:
            barrier.wait(timeout=10)
            results.append(
                SubmissionAuthorizationStore(coordinator).claim_authorization(
                    _request(claimant_id=claimant)
                )
            )
        except Exception as exc:  # pragma: no cover - surfaced by assertion below
            errors.append(exc)
        finally:
            coordinator.close()

    threads = [
        threading.Thread(target=worker, args=("claimant-a",)),
        threading.Thread(target=worker, args=("claimant-b",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    assert not errors
    assert len(results) == 2
    assert sum(result.disposition is ClaimDisposition.CLAIMED for result in results) == 1
    assert sum(result.capability is not None for result in results) == 1
    assert any(result.disposition is ClaimDisposition.ALREADY_CLAIMED for result in results)


@pytest.mark.parametrize(
    "sql",
    (
        "UPDATE handa_live.submission_authorization SET client_order_id = 'tampered' WHERE submission_authorization_id = 'auth-submit-001'",
        "UPDATE handa_live.submission_authorization SET requested_quote_amount = 99 WHERE submission_authorization_id = 'auth-submit-001'",
        "UPDATE handa_live.submission_authorization SET issuer_id = 'tampered' WHERE submission_authorization_id = 'auth-submit-001'",
        "UPDATE handa_live.submission_authorization SET authority_reference_id = 'tampered' WHERE submission_authorization_id = 'auth-submit-001'",
        "UPDATE handa_live.submission_authorization SET submission_fingerprint = 'tampered' WHERE submission_authorization_id = 'auth-submit-001'",
        "DELETE FROM handa_live.submission_authorization WHERE submission_authorization_id = 'auth-submit-001'",
    ),
)
def test_direct_sql_cannot_mutate_or_delete_authorization(prepared, sql):
    url, _, _ = prepared
    connection = psycopg2.connect(url)
    try:
        with connection.cursor() as cursor:
            with pytest.raises(psycopg2.Error):
                cursor.execute(sql)
        connection.rollback()
    finally:
        connection.close()


def test_direct_sql_cannot_reverse_claim_and_claim_fields_are_database_owned(prepared):
    url, _, store = prepared
    result = store.claim_authorization(_request())
    assert result.disposition is ClaimDisposition.CLAIMED
    connection = psycopg2.connect(url)
    try:
        with pytest.raises(psycopg2.Error):
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE handa_live.submission_authorization SET authorization_state = 'AUTHORIZED' WHERE submission_authorization_id = 'auth-submit-001'"
                )
        connection.rollback()
    finally:
        connection.close()


def test_capability_cannot_be_manually_forged_or_mutated(prepared):
    _, _, store = prepared
    result = store.claim_authorization(_request())
    capability = result.capability
    with pytest.raises(ValueError):
        ClaimedSubmissionCapability(
            submission_authorization_id="auth-submit-001", intent_id="intent-submit-001",
            submission_attempt_id="attempt-submit-001", client_order_id="client-submit-001",
            venue="MOCK", account_scope="TEST", symbol="HYPEUSDC", side="BUY",
            requested_quote_amount=Decimal("41.4117522032984"), requested_base_qty=None,
            submission_fingerprint="x", issuer_id="x", authority_reference_id="x",
            authority_contract_version="x", claimed_by="x", claimed_at=capability.claimed_at,
            claimed_version=1,
        )
    with pytest.raises(AttributeError):
        capability.client_order_id = "tampered"


def test_persistence_failure_rolls_back_claim_atomically(prepared):
    url, _, store = prepared
    connection = psycopg2.connect(url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE FUNCTION handa_live.test_reject_claim()
                RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    RAISE EXCEPTION 'test-only persistence failure';
                END;
                $$
                """
            )
            cursor.execute(
                """
                CREATE TRIGGER test_reject_claim_trigger
                BEFORE UPDATE ON handa_live.submission_authorization
                FOR EACH ROW EXECUTE FUNCTION handa_live.test_reject_claim()
                """
            )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(PersistenceFailure):
        store.claim_authorization(_request())

    connection = psycopg2.connect(url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT authorization_state, current_version, claimed_by, claimed_at FROM handa_live.submission_authorization WHERE submission_authorization_id = 'auth-submit-001'"
            )
            assert cursor.fetchone() == ("AUTHORIZED", 0, None, None)
            cursor.execute(
                "DROP TRIGGER test_reject_claim_trigger ON handa_live.submission_authorization"
            )
            cursor.execute("DROP FUNCTION handa_live.test_reject_claim()")
        connection.commit()
    finally:
        connection.close()


def test_new_production_components_have_no_authority_or_application_leak():
    sources = "\n".join(
        (
            (ROOT / "core" / "execution" / "submission_authority.py").read_text(encoding="utf-8"),
            (ROOT / "core" / "persistence" / "submission_authorization_store.py").read_text(encoding="utf-8"),
        )
    )
    forbidden = (
        "DecisionEngine", "BuySignal", "GovernedMockSubmissionGateway", "MockExecutor",
        "EffectEligibility", "OperationalApplicationBinding", "effect_request_id",
        "application_attempt_id", "PositionBinding", "PositionEffectAuthority",
        "PositionManager", "SlotController", "create_authorization", "grant_authority",
        "effect_request_id", "application_attempt_id",
    )
    assert not any(token in sources for token in forbidden)


def test_cw_a_has_no_external_call_and_cw_b_composes_existing_fw2_once(prepared, monkeypatch, tmp_path):
    _, _, store = prepared
    claim = store.claim_authorization(_request())
    assert claim.disposition is ClaimDisposition.CLAIMED

    # Window A: a restart sees CLAIMED and therefore has no capability to submit.
    restarted = _coordinator(_database_url())
    try:
        assert SubmissionAuthorizationStore(restarted).claim_authorization(_request()).capability is None
    finally:
        restarted.close()

    # Window B is a test-only composition with the already-existing FW2 gateway.
    from tests.test_fw2_governed_mock_lost_response_expected_red import (
        _fresh_executor,
        _signal,
    )

    executor, state_path = _fresh_executor(monkeypatch, tmp_path)
    executor.execute_buy = Mock(wraps=executor.execute_buy)
    gateway = GovernedMockSubmissionGateway(executor)
    gateway.submit_buy(_signal(), client_order_id=claim.capability.client_order_id)
    assert executor.execute_buy.call_count == 1
    assert state_path.exists()
