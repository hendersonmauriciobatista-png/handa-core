"""Focused PostgreSQL contracts for Slice 2B1.

Rows inserted directly by these tests are explicitly test fixtures.  They are
not production approval, activation, evaluation, or issuance APIs.
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest

from core.execution.live_order_models import LiveOrderIntent, OrderSide
from core.execution.submission_authority import submission_fingerprint
from core.persistence.live_order_store import LiveOrderStore, live_order_resource_scope
from core.persistence.persistence_coordinator import DatabaseIdentity, PersistenceCoordinator
from tests.integration.test_submission_authorization_postgres import (
    EXPECTED_DATABASE,
    EXPECTED_HOSTS,
    EXPECTED_PORT,
    EXPECTED_URL,
    EXPECTED_USER,
    _bootstrap,
)


ROOT = Path(__file__).parents[2]
IDENTITY = DatabaseIdentity(EXPECTED_HOSTS, EXPECTED_PORT, EXPECTED_DATABASE, EXPECTED_USER)


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


@pytest.fixture()
def prepared():
    url = _database_url()
    _bootstrap(url)
    try:
        yield url
    finally:
        connection = psycopg2.connect(url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            connection.commit()
        finally:
            connection.close()


def _execute(url: str, statement: str, parameters=()):
    connection = psycopg2.connect(url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            rows = cursor.fetchall() if cursor.description else None
        connection.commit()
        return rows
    finally:
        connection.close()


def _seed_lineage(url: str, prefix: str):
    intent_id = f"{prefix}-intent"
    attempt_id = f"{prefix}-attempt"
    client_order_id = f"{prefix}-client"
    coordinator = PersistenceCoordinator(
        url, IDENTITY, resource_scope=live_order_resource_scope()
    )
    try:
        store = LiveOrderStore(coordinator)
        store.create_intent(
            LiveOrderIntent(
                intent_id=intent_id,
                client_order_id=client_order_id,
                slot_id=f"{prefix}-slot",
                symbol="HYPEUSDC",
                side=OrderSide.BUY,
                requested_quote_amount=Decimal("41.4117522032984"),
                policy_context="TEST_FIXTURE_AUTHORITY_ONLY",
            ),
            venue="MOCK",
            account_scope="TEST",
        )
        store.record_submission_preparation(
            intent_id=intent_id,
            attempt_id=attempt_id,
            attempt_sequence=1,
            venue="MOCK",
            account_scope="TEST",
            client_order_id=client_order_id,
            expected_version=0,
        )
    finally:
        coordinator.close()
    return intent_id, attempt_id, client_order_id


def _insert_envelope(url: str, envelope_id: str = "envelope-001"):
    _execute(
        url,
        """
        INSERT INTO handa_live.authority_envelope (
            authority_envelope_id, runtime_mode, venue, account_scope,
            allowed_sides, strategy_version, decision_contract_version,
            policy_version, risk_policy_version, valid_from, valid_until,
            configuration_digest, authority_contract_version, approved_by,
            approval_reason
        ) VALUES (
            %s, 'OBSERVE_ONLY', 'MOCK', 'TEST', ARRAY['BUY'],
            'strategy-test-v1', 'decision-contract-v1', 'policy-test-v1',
            'risk-policy-test-v1', CURRENT_TIMESTAMP - INTERVAL '1 second',
            CURRENT_TIMESTAMP + INTERVAL '30 seconds',
            'configuration-digest-test-001', 'submission-authority-v1',
            'fixture-human-only', 'TEST_FIXTURE_AUTHORITY_ONLY'
        )
        """,
        (envelope_id,),
    )


def _insert_decision(
    url: str,
    intent_id: str,
    attempt_id: str,
    envelope_id: str,
    decision_id: str = "decision-001",
    sequence: int = 1,
    outcome: str = "ALLOW",
):
    _execute(
        url,
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
            %s, %s, %s, %s, %s, %s, %s, %s, 'TEST_FIXTURE_AUTHORITY_ONLY',
            %s, %s, 'decision-contract-v1', 'decision-engine-test-v1',
            'policy-test-v1', 'risk-policy-test-v1', 'strategy-test-v1',
            'input-snapshot-test', 'decision-semantics-test', 0, 0,
            'OBSERVE_ONLY', 'MOCK', 'TEST',
            CURRENT_TIMESTAMP - INTERVAL '1 second',
            CASE WHEN %s = 'BLOCK'
                 THEN CURRENT_TIMESTAMP - INTERVAL '1 second'
                 ELSE CURRENT_TIMESTAMP + INTERVAL '30 seconds'
            END
        )
        """,
        (
            decision_id,
            intent_id,
            attempt_id,
            f"TEST_ONLY_EVALUATION_IDENTITY-{decision_id}",
            f"TEST_ONLY_EVALUATION_DIGEST-{decision_id}",
            envelope_id,
            sequence,
            outcome,
            f"intent-digest-{intent_id}",
            f"attempt-digest-{attempt_id}",
            outcome,
        ),
    )


def _insert_authorization(url: str, intent_id: str, attempt_id: str, authorization_id: str, decision_id: str):
    client_order_id = f"{intent_id.removesuffix('-intent')}-client"
    fingerprint = submission_fingerprint(
        intent_id=intent_id,
        submission_attempt_id=attempt_id,
        client_order_id=client_order_id,
        venue="MOCK",
        account_scope="TEST",
        symbol="HYPEUSDC",
        side="BUY",
        requested_quote_amount=Decimal("41.4117522032984"),
        requested_base_qty=None,
    )
    _execute(
        url,
        """
        INSERT INTO handa_live.submission_authorization (
            submission_authorization_id, intent_id, submission_attempt_id,
            client_order_id, venue, account_scope, symbol, side,
            requested_quote_amount, requested_base_qty,
            authority_reference_id, issuer_id, authority_contract_version,
            authorization_sequence, submission_fingerprint, authorization_state
        ) VALUES (%s, %s, %s, %s, 'MOCK', 'TEST', 'HYPEUSDC', 'BUY',
                  %s, NULL, %s, 'fixture-issuer-only',
                  'submission-authority-v1', 1, %s, 'AUTHORIZED')
        """,
        (
            authorization_id,
            intent_id,
            attempt_id,
            client_order_id,
            Decimal("41.4117522032984"),
            decision_id,
            fingerprint,
        ),
    )


def test_migration_010_initializes_fail_safe_singleton(prepared):
    rows = _execute(
        prepared,
        """
        SELECT operational_mode, active_authority_envelope_id,
               global_safety_epoch, runtime_generation, current_version
        FROM handa_live.operational_authority_state
        WHERE state_id = TRUE
        """,
    )
    assert rows == [("OBSERVE_ONLY", None, 0, 0, 0)]


def test_schema_relations_and_migration_are_present(prepared):
    rows = _execute(
        prepared,
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'handa_live'
          AND table_name IN (
              'authority_envelope', 'authority_envelope_event',
              'operational_authority_state', 'pre_execution_decision'
          )
        ORDER BY table_name
        """,
    )
    assert [row[0] for row in rows] == [
        "authority_envelope",
        "authority_envelope_event",
        "operational_authority_state",
        "pre_execution_decision",
    ]


def test_envelope_version_is_database_owned_and_unique(prepared):
    _insert_envelope(prepared, "envelope-a")
    _insert_envelope(prepared, "envelope-b")
    rows = _execute(
        prepared,
        "SELECT envelope_version FROM handa_live.authority_envelope ORDER BY envelope_version",
    )
    assert rows == [(1,), (2,)]


def test_envelope_rejects_invalid_side_sets_and_validity(prepared):
    with pytest.raises(psycopg2.Error):
        _execute(
            prepared,
            """
            INSERT INTO handa_live.authority_envelope (
                authority_envelope_id, runtime_mode, venue, account_scope,
                allowed_sides, strategy_version, decision_contract_version,
                policy_version, risk_policy_version, valid_from, valid_until,
                configuration_digest, authority_contract_version, approved_by,
                approval_reason
            ) VALUES (
                'envelope-invalid-sides', 'OBSERVE_ONLY', 'MOCK', 'TEST',
                ARRAY['BUY', 'BUY'], 's', 'd', 'p', 'r',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '30 seconds',
                'c', 'a', 'h', 'reason'
            )
            """,
        )

    with pytest.raises(psycopg2.Error):
        _execute(
            prepared,
            """
            INSERT INTO handa_live.authority_envelope (
                authority_envelope_id, runtime_mode, venue, account_scope,
                allowed_sides, strategy_version, decision_contract_version,
                policy_version, risk_policy_version, valid_from, valid_until,
                configuration_digest, authority_contract_version, approved_by,
                approval_reason
            ) VALUES (
                'envelope-invalid-time', 'OBSERVE_ONLY', 'MOCK', 'TEST',
                ARRAY['BUY'], 's', 'd', 'p', 'r', CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP, 'c', 'a', 'h', 'reason'
            )
            """,
        )

def test_envelope_definition_is_immutable(prepared):
    _insert_envelope(prepared)
    with pytest.raises(psycopg2.Error):
        _execute(
            prepared,
            "UPDATE handa_live.authority_envelope SET approval_reason='tampered' WHERE authority_envelope_id='envelope-001'",
        )
    with pytest.raises(psycopg2.Error):
        _execute(
            prepared,
            "DELETE FROM handa_live.authority_envelope WHERE authority_envelope_id='envelope-001'",
        )


def test_event_types_are_bounded_append_only_and_sequenced(prepared):
    _insert_envelope(prepared)
    _execute(
        prepared,
        """
        INSERT INTO handa_live.authority_envelope_event (
            event_id, authority_envelope_id, event_sequence, event_type,
            actor_id, reason, safety_epoch_after, runtime_generation_after
        ) VALUES ('event-001', 'envelope-001', 1, 'ACTIVATED',
                  'fixture', 'TEST_FIXTURE_AUTHORITY_ONLY', 1, 1)
        """,
    )
    with pytest.raises(psycopg2.Error):
        _execute(
            prepared,
            """
            INSERT INTO handa_live.authority_envelope_event (
                event_id, authority_envelope_id, event_sequence, event_type,
                actor_id, reason, safety_epoch_after, runtime_generation_after
            ) VALUES ('event-duplicate', 'envelope-001', 1, 'REVOKED',
                      'fixture', 'reason', 2, 1)
            """,
        )
    with pytest.raises(psycopg2.Error):
        _execute(
            prepared,
            "UPDATE handa_live.authority_envelope_event SET reason='tampered' WHERE event_id='event-001'",
        )
    with pytest.raises(psycopg2.Error):
        _execute(
            prepared,
            """
            INSERT INTO handa_live.authority_envelope_event (
                event_id, authority_envelope_id, event_sequence, event_type,
                actor_id, reason, safety_epoch_after, runtime_generation_after
            ) VALUES ('event-invalid', 'envelope-001', 2, 'APPROVED',
                      'fixture', 'reason', 1, 1)
            """,
        )


def test_state_is_singleton(prepared):
    with pytest.raises(psycopg2.Error):
        _execute(
            prepared,
            """
            INSERT INTO handa_live.operational_authority_state (
                state_id, operational_mode, global_safety_epoch,
                runtime_generation, current_version, changed_by, change_reason
            ) VALUES (TRUE, 'OBSERVE_ONLY', 0, 0, 0, 'fixture', 'reason')
            """,
        )
    with pytest.raises(psycopg2.Error):
        _execute(
            prepared,
            """
            INSERT INTO handa_live.operational_authority_state (
                state_id, operational_mode, global_safety_epoch,
                runtime_generation, current_version, changed_by, change_reason
            ) VALUES (FALSE, 'OBSERVE_ONLY', 0, 0, 0, 'fixture', 'reason')
            """,
        )


def test_preexecution_allow_and_block_are_durable_and_latest_is_readable(prepared):
    intent_id, attempt_id, _ = _seed_lineage(prepared, "decision")
    _insert_envelope(prepared)
    _insert_decision(prepared, intent_id, attempt_id, "envelope-001", "decision-allow", 1, "ALLOW")
    _insert_decision(prepared, intent_id, attempt_id, "envelope-001", "decision-block", 2, "BLOCK")
    rows = _execute(
        prepared,
        "SELECT decision_outcome FROM handa_live.pre_execution_decision ORDER BY decision_sequence",
    )
    assert rows == [("ALLOW",), ("BLOCK",)]

    from core.persistence.pre_execution_decision_store import (
        PreExecutionDecisionStore,
        pre_execution_decision_resource_scope,
    )

    coordinator = PersistenceCoordinator(
        prepared, IDENTITY, resource_scope=pre_execution_decision_resource_scope()
    )
    try:
        latest = PreExecutionDecisionStore(coordinator).get_latest_for_attempt(attempt_id)
        assert latest["pre_execution_decision_id"] == "decision-block"
        assert latest["decision_outcome"] == "BLOCK"
    finally:
        coordinator.close()


def test_preexecution_is_immutable_and_lineage_is_strong(prepared):
    intent_id, attempt_id, _ = _seed_lineage(prepared, "lineage")
    _insert_envelope(prepared)
    _insert_decision(prepared, intent_id, attempt_id, "envelope-001")
    with pytest.raises(psycopg2.Error):
        _execute(
            prepared,
            "UPDATE handa_live.pre_execution_decision SET decision_outcome='BLOCK' WHERE pre_execution_decision_id='decision-001'",
        )
    with pytest.raises(psycopg2.Error):
        _execute(
            prepared,
            "DELETE FROM handa_live.pre_execution_decision WHERE pre_execution_decision_id='decision-001'",
        )

    _insert_authorization(prepared, intent_id, attempt_id, "auth-lineage", "decision-001")
    with pytest.raises(psycopg2.Error):
        _insert_authorization(prepared, intent_id, attempt_id, "auth-wrong-ref", "missing-decision")


def test_duplicate_decision_sequence_and_identity_are_rejected(prepared):
    intent_id, attempt_id, _ = _seed_lineage(prepared, "duplicate")
    _insert_envelope(prepared)
    _insert_decision(
        prepared,
        intent_id,
        attempt_id,
        "envelope-001",
        "decision-001",
        1,
        "ALLOW",
    )
    with pytest.raises(psycopg2.Error):
        _insert_decision(
            prepared,
            intent_id,
            attempt_id,
            "envelope-001",
            "decision-002",
            1,
            "BLOCK",
        )

    other_intent, other_attempt, _ = _seed_lineage(prepared, "duplicate-other")
    with pytest.raises(psycopg2.Error):
        _insert_decision(
            prepared,
            other_intent,
            other_attempt,
            "envelope-001",
            "decision-001",
            1,
            "BLOCK",
        )
    with pytest.raises(psycopg2.Error):
        _insert_decision(
            prepared,
            intent_id,
            attempt_id,
            "envelope-001",
            "decision-001",
            2,
            "BLOCK",
        )


def test_authority_lineage_rejects_decision_from_another_intent_or_attempt(prepared):
    intent_a, attempt_a, _ = _seed_lineage(prepared, "lineage-a")
    intent_b, attempt_b, _ = _seed_lineage(prepared, "lineage-b")
    _insert_envelope(prepared)
    with pytest.raises(psycopg2.Error):
        _insert_decision(prepared, intent_a, attempt_b, "envelope-001", "decision-wrong-attempt")
    _insert_decision(prepared, intent_b, attempt_b, "envelope-001", "decision-b")
    with pytest.raises(psycopg2.Error):
        _insert_authorization(prepared, intent_a, attempt_a, "auth-cross-intent", "decision-b")


def test_2b1_stores_remain_read_only_and_claim_store_cannot_issue():
    envelope_source = (ROOT / "core" / "persistence" / "authority_envelope_store.py").read_text()
    state_source = (ROOT / "core" / "persistence" / "operational_authority_state_store.py").read_text()
    decision_source = (ROOT / "core" / "persistence" / "pre_execution_decision_store.py").read_text()
    for source in (envelope_source, state_source, decision_source):
        assert "submission_authorization" not in source
        assert "create_authorization" not in source
        assert "issue_authorization" not in source
        assert "approve_envelope" not in source
        assert "activate_envelope" not in source
        assert "revoke_envelope" not in source
        assert "create_allow_decision" not in source

    assert not (ROOT / "core" / "execution" / "pre_execution_decision.py").exists()

    from core.persistence.submission_authorization_store import SubmissionAuthorizationStore

    assert not hasattr(SubmissionAuthorizationStore, "create_authorization")
