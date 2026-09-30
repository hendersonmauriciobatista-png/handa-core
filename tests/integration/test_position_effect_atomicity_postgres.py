"""PostgreSQL expected-red falsifiers for shared Position Effect atomicity."""

import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest

from core.persistence.effect_application_ledger import EffectApplicationLedger
from core.position.position_effect_authority import PositionEffectAuthority


ROOT = Path(__file__).parents[2]
MIGRATIONS = [
    ROOT / "core" / "persistence" / "migrations" / name
    for name in (
        "001_create_handa_live.sql",
        "002_relax_may_have_been_submitted_certainty.sql",
        "003_reconciliation_evidence.sql",
        "004_external_order_observation_contract.sql",
        "005_decision_ledger.sql",
        "006_effect_application_ledger.sql",
        "007_position_effect_authority.sql",
    )
]
EXPECTED_URL = "postgresql://handa_test:handa_test_only@127.0.0.1:55432/handa_test"


def _database_url():
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL falsifiers")
    parsed = urlparse(value)
    if value != EXPECTED_URL:
        pytest.fail("refusing non-governed PostgreSQL target")
    if (
        parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.port != 55432
        or parsed.username != "handa_test"
        or parsed.path.lstrip("/") != "handa_test"
    ):
        pytest.fail("refusing non-disposable PostgreSQL target")
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
        yield conn
    finally:
        conn.rollback()
        with conn.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
        conn.commit()
        conn.close()


def _base(connection, effect_request_id, effect_type):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.order_intent
            (intent_id, venue, account_scope, client_order_id, slot_id, symbol,
             side, requested_quote_amount, submission_lifecycle_state)
            VALUES ('intent-1', 'TEST', 'test', 'client-1', 'slot-1',
                    'BTCUSDC', 'BUY', 10, 'READY_TO_SUBMIT')
            """
        )
        cursor.execute(
            """
            INSERT INTO handa_live.reconciliation_context
            (context_id, intent_id, context_sequence, context_state)
            VALUES ('context-1', 'intent-1', 1, 'ACTIVE')
            """
        )
        cursor.execute(
            """
            INSERT INTO handa_live.semantic_decision
            (decision_id, context_id, intent_id, decision_sequence,
             evaluation_time, decision_scope, authority_state,
             execution_occurred, order_outcome_terminal, execution_extent,
             final_partial_outcome, evaluated_input_snapshot,
             authority_contract_version, decision_schema_version,
             evidence_normalization_version, lineage_completeness_status)
            VALUES ('decision-1', 'context-1', 'intent-1', 1, CURRENT_TIMESTAMP,
                    'ORDER_OUTCOME', 'RESOLVED', '{"value":"UNKNOWN"}',
                    '{"value":"UNKNOWN"}', '{"value":"UNKNOWN"}',
                    '{"value":"UNKNOWN"}', '{"source":"test"}',
                    'v1', 'v1', 'v1', 'LINEAGE_INCOMPLETE')
            """
        )
        cursor.execute(
            """
            INSERT INTO handa_live.effect_request
            (effect_request_id, effect_type, intent_id, reconciliation_context_id,
             current_state)
            VALUES (%s, %s, 'intent-1', 'context-1', 'AUTHORIZED')
            """,
            (effect_request_id, effect_type),
        )
        cursor.execute(
            """
            INSERT INTO handa_live.authority_binding
            (effect_request_id, authority_decision_id, intent_id,
             reconciliation_context_id, decision_sequence,
             authority_contract_version)
            VALUES (%s, 'decision-1', 'intent-1', 'context-1', 1, 'v1')
            """,
            (effect_request_id,),
        )
        cursor.execute(
            """
            INSERT INTO handa_live.lifecycle_event
            (effect_request_id, event_sequence, previous_state, next_state,
             event_kind, reason, application_attempt_id,
             recovery_authority_id, recovery_policy_version, evidence_ids)
            VALUES (%s, 1, NULL, 'AUTHORIZED', 'AUTHORITY_ACCEPTED',
                    'effect authority accepted', NULL, NULL, NULL, %s)
            """,
            (effect_request_id, []),
        )
    connection.commit()


def _binding():
    return {
        "intent_id": "intent-1",
        "symbol": "BTCUSDC",
        "reconciliation_context_id": "context-1",
        "semantic_decision_id": "decision-1",
        "decision_sequence": 1,
        "authority_contract_version": "v1",
    }


def _additional_request(connection, effect_request_id, effect_type):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.effect_request
            (effect_request_id, effect_type, intent_id, reconciliation_context_id,
             current_state)
            VALUES (%s, %s, 'intent-1', 'context-1', 'AUTHORIZED')
            """,
            (effect_request_id, effect_type),
        )
        cursor.execute(
            """
            INSERT INTO handa_live.authority_binding
            (effect_request_id, authority_decision_id, intent_id,
             reconciliation_context_id, decision_sequence,
             authority_contract_version)
            VALUES (%s, 'decision-1', 'intent-1', 'context-1', 1, 'v1')
            """,
            (effect_request_id,),
        )
        cursor.execute(
            """
            INSERT INTO handa_live.lifecycle_event
            (effect_request_id, event_sequence, previous_state, next_state,
             event_kind, reason, application_attempt_id,
             recovery_authority_id, recovery_policy_version, evidence_ids)
            VALUES (%s, 1, NULL, 'AUTHORIZED', 'AUTHORITY_ACCEPTED',
                    'effect authority accepted', NULL, NULL, NULL, %s)
            """,
            (effect_request_id, []),
        )
    connection.commit()


def _receipt(order_id, quantity=10):
    return {
        "exchange": "TEST",
        "order_id": order_id,
        "executed_base_qty": quantity,
        "executed_quote_qty": 100,
        "weighted_price": 100,
        "status": "FILLED",
        "fills": [{"trade_id": f"trade-{order_id}", "quantity": quantity}],
    }


def _new_connection():
    return psycopg2.connect(_database_url())


def _durable_counts(connection, effect_request_id, position_id="position-1"):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_state FROM handa_live.effect_request "
            "WHERE effect_request_id=%s",
            (effect_request_id,),
        )
        ledger_state = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COUNT(*) FROM handa_live.application_attempt "
            "WHERE effect_request_id=%s",
            (effect_request_id,),
        )
        attempts = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COUNT(*) FROM handa_live.position WHERE position_id=%s",
            (position_id,),
        )
        positions = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM handa_live.position_receipt")
        receipts = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM handa_live.position_effect_event")
        events = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM handa_live.applied_effect")
        applied_effects = cursor.fetchone()[0]
    return ledger_state, attempts, positions, receipts, events, applied_effects


def test_atx001_rollback_after_claim_before_position_mutation(connection):
    _base(connection, "effect-1", "POSITION_OPEN")
    ledger = EffectApplicationLedger(connection)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    with pytest.raises(RuntimeError, match="ATX-001"):
        with ledger.transaction_scope() as cursor:
            ledger.claim_application("effect-1", application_attempt_id="attempt-1", cursor=cursor)
            raise RuntimeError("ATX-001 injected failure")
            authority.apply_open(
                position_id="position-1", intended_quantity=10,
                receipt=_receipt("buy-1"), effect_request_id="effect-1",
                cursor=cursor, **_binding()
            )
    fresh = _new_connection()
    try:
        assert _durable_counts(fresh, "effect-1") == ("AUTHORIZED", 0, 0, 0, 0, 0)
    finally:
        fresh.close()


def test_atx002_rollback_after_receipt_evidence_start(connection):
    _base(connection, "effect-1", "POSITION_OPEN")
    ledger = EffectApplicationLedger(connection)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    with pytest.raises(RuntimeError, match="ATX-002"):
        with ledger.transaction_scope() as cursor:
            ledger.claim_application("effect-1", application_attempt_id="attempt-1", cursor=cursor)
            authority.apply_open(
                position_id="position-1", intended_quantity=10,
                receipt=_receipt("buy-1"), effect_request_id="effect-1",
                cursor=cursor, **_binding()
            )
            with connection.cursor() as probe:
                probe.execute("SELECT COUNT(*) FROM handa_live.position")
                assert probe.fetchone()[0] == 1
                probe.execute("SELECT COUNT(*) FROM handa_live.position_receipt")
                assert probe.fetchone()[0] == 1
            raise RuntimeError("ATX-002 injected failure")
    fresh = _new_connection()
    try:
        assert _durable_counts(fresh, "effect-1") == ("AUTHORIZED", 0, 0, 0, 0, 0)
    finally:
        fresh.close()


def test_atx003_rollback_after_position_mutation_before_ledger_applied(connection):
    _base(connection, "effect-1", "POSITION_OPEN")
    ledger = EffectApplicationLedger(connection)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    with pytest.raises(RuntimeError, match="ATX-003"):
        with ledger.transaction_scope() as cursor:
            ledger.claim_application("effect-1", application_attempt_id="attempt-1", cursor=cursor)
            authority.apply_open(
                position_id="position-1", intended_quantity=10,
                receipt=_receipt("buy-1"), effect_request_id="effect-1",
                cursor=cursor, **_binding()
            )
            with connection.cursor() as probe:
                probe.execute("SELECT COUNT(*) FROM handa_live.position_effect_event")
                assert probe.fetchone()[0] == 1
            raise RuntimeError("ATX-003 injected failure")
    fresh = _new_connection()
    try:
        assert _durable_counts(fresh, "effect-1") == ("AUTHORIZED", 0, 0, 0, 0, 0)
    finally:
        fresh.close()


def test_atx004_rollback_after_mark_applied_before_outer_commit(connection):
    _base(connection, "effect-1", "POSITION_OPEN")
    ledger = EffectApplicationLedger(connection)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    with pytest.raises(RuntimeError, match="ATX-004"):
        with ledger.transaction_scope() as cursor:
            ledger.claim_application("effect-1", application_attempt_id="attempt-1", cursor=cursor)
            authority.apply_open(
                position_id="position-1", intended_quantity=10,
                receipt=_receipt("buy-1"), effect_request_id="effect-1",
                cursor=cursor, **_binding()
            )
            ledger.mark_applied(
                "effect-1", application_attempt_id="attempt-1",
                receipt={"receipt_id": "receipt-1", "schema_version": "v1",
                         "producer_id": "test", "payload": {}}, cursor=cursor
            )
            with connection.cursor() as probe:
                probe.execute(
                    "SELECT current_state FROM handa_live.effect_request "
                    "WHERE effect_request_id='effect-1'"
                )
                assert probe.fetchone()[0] == "APPLIED"
                probe.execute("SELECT COUNT(*) FROM handa_live.applied_effect")
                assert probe.fetchone()[0] == 1
            raise RuntimeError("ATX-004 injected failure")
    fresh = _new_connection()
    try:
        assert _durable_counts(fresh, "effect-1") == ("AUTHORIZED", 0, 0, 0, 0, 0)
    finally:
        fresh.close()


def test_atx005_successful_shared_commit(connection):
    _base(connection, "effect-1", "POSITION_OPEN")
    ledger = EffectApplicationLedger(connection)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    with ledger.transaction_scope() as cursor:
        ledger.claim_application("effect-1", application_attempt_id="attempt-1", cursor=cursor)
        authority.apply_open(
            position_id="position-1", intended_quantity=10,
            receipt=_receipt("buy-1"), effect_request_id="effect-1",
            cursor=cursor, **_binding()
        )
        ledger.mark_applied(
            "effect-1", application_attempt_id="attempt-1",
            receipt={"receipt_id": "receipt-1", "schema_version": "v1",
                     "producer_id": "test", "payload": {}}, cursor=cursor
        )
    fresh = _new_connection()
    try:
        assert _durable_counts(fresh, "effect-1") == ("APPLIED", 1, 1, 1, 1, 1)
    finally:
        fresh.close()


def test_atx006_post_commit_replay_idempotency(connection):
    _base(connection, "effect-1", "POSITION_OPEN")
    ledger = EffectApplicationLedger(connection)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    with ledger.transaction_scope() as cursor:
        ledger.claim_application("effect-1", application_attempt_id="attempt-1", cursor=cursor)
        authority.apply_open(
            position_id="position-1", intended_quantity=10,
            receipt=_receipt("buy-1"), effect_request_id="effect-1",
            cursor=cursor, **_binding()
        )
        ledger.mark_applied(
            "effect-1", application_attempt_id="attempt-1",
            receipt={"receipt_id": "receipt-1", "schema_version": "v1",
                     "producer_id": "test", "payload": {}}, cursor=cursor
        )
    with ledger.transaction_scope() as cursor:
        replay = authority.apply_open(
            position_id="position-1", intended_quantity=10,
            receipt=_receipt("buy-1"), effect_request_id="effect-1",
            cursor=cursor, **_binding()
        )
        assert replay.effect_request_id == "effect-1"
    fresh = _new_connection()
    try:
        assert _durable_counts(fresh, "effect-1") == ("APPLIED", 1, 1, 1, 1, 1)
    finally:
        fresh.close()


def test_atx006b_cross_request_execution_extent_reuse(connection):
    _base(connection, "effect-a", "POSITION_OPEN")
    ledger = EffectApplicationLedger(connection)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    receipt = _receipt("buy-1")
    with ledger.transaction_scope() as cursor:
        ledger.claim_application("effect-a", application_attempt_id="attempt-a", cursor=cursor)
        authority.apply_open(
            position_id="position-1", intended_quantity=10,
            receipt=receipt, effect_request_id="effect-a",
            cursor=cursor, **_binding()
        )
        ledger.mark_applied(
            "effect-a", application_attempt_id="attempt-a",
            receipt={"receipt_id": "receipt-a", "schema_version": "v1",
                     "producer_id": "test", "payload": {}}, cursor=cursor
        )

    _additional_request(connection, "effect-b", "POSITION_CLOSE")
    with pytest.raises(psycopg2.errors.UniqueViolation) as error:
        with ledger.transaction_scope() as cursor:
            ledger.claim_application("effect-b", application_attempt_id="attempt-b", cursor=cursor)
            authority.apply_close(
                position_id="position-1", receipt=receipt,
                effect_request_id="effect-b", cursor=cursor, **_binding()
            )
    assert "execution_extent_identity" in str(error.value)

    fresh = _new_connection()
    try:
        with fresh.cursor() as cursor:
            cursor.execute(
                "SELECT current_state FROM handa_live.effect_request "
                "WHERE effect_request_id='effect-a'"
            )
            assert cursor.fetchone()[0] == "APPLIED"
            cursor.execute(
                "SELECT current_state FROM handa_live.effect_request "
                "WHERE effect_request_id='effect-b'"
            )
            assert cursor.fetchone()[0] == "AUTHORIZED"
            cursor.execute(
                "SELECT lifecycle_state, current_quantity FROM handa_live.position "
                "WHERE position_id='position-1'"
            )
            assert cursor.fetchone() == ("ACTIVE", 10)
            cursor.execute(
                """
                SELECT COUNT(*) FROM handa_live.position_receipt
                WHERE execution_extent_identity = (
                    SELECT execution_extent_identity
                    FROM handa_live.position_receipt
                    WHERE receipt_id='position-receipt-effect-a'
                )
                """
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute(
                """
                SELECT COUNT(*) FROM handa_live.position_effect_event
                WHERE execution_extent_identity = (
                    SELECT execution_extent_identity
                    FROM handa_live.position_receipt
                    WHERE receipt_id='position-receipt-effect-a'
                )
                """
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT COUNT(*) FROM handa_live.applied_effect")
            assert cursor.fetchone()[0] == 1
    finally:
        fresh.close()
