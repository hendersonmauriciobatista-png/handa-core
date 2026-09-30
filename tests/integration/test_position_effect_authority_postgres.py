"""PostgreSQL falsifiers for migration-007 position invariants."""

import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest


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


def database_url():
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL falsifiers")
    parsed = urlparse(value)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != 55432:
        pytest.fail("refusing non-governed PostgreSQL target")
    if parsed.username != "handa_test" or parsed.path.lstrip("/") != "handa_test":
        pytest.fail("refusing non-disposable PostgreSQL target")
    return value


@pytest.fixture()
def connection():
    conn = psycopg2.connect(database_url())
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


def _base(conn):
    with conn.cursor() as cursor:
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
            (decision_id, context_id, intent_id, decision_sequence, evaluation_time,
             decision_scope, authority_state, execution_occurred,
             order_outcome_terminal, execution_extent, final_partial_outcome,
             evaluated_input_snapshot, authority_contract_version,
             decision_schema_version, evidence_normalization_version,
             lineage_completeness_status)
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
            VALUES ('effect-1', 'POSITION_OPEN', 'intent-1', 'context-1', 'AUTHORIZED')
            """
        )
        cursor.execute(
            """
            INSERT INTO handa_live.authority_binding
            (effect_request_id, authority_decision_id, intent_id,
             reconciliation_context_id, decision_sequence,
             authority_contract_version)
            VALUES ('effect-1', 'decision-1', 'intent-1', 'context-1', 1, 'v1')
            """
        )
    conn.commit()


def _position(conn, quantity="10"):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.position
            (position_id, intent_id, symbol, lifecycle_state, current_quantity,
             open_effect_request_id, position_lifecycle_version)
            VALUES ('position-1', 'intent-1', 'BTCUSDC', 'ACTIVE', %s,
                    'effect-1', 1)
            """,
            (quantity,),
        )
    conn.commit()


def test_position_quantity_state_consistency_is_database_owned(connection):
    _base(connection)
    with pytest.raises(psycopg2.Error) as error:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO handa_live.position
                (position_id, intent_id, symbol, lifecycle_state, current_quantity,
                 open_effect_request_id, position_lifecycle_version)
                VALUES ('position-bad', 'intent-1', 'BTCUSDC', 'ACTIVE', 0,
                        'effect-1', 1)
                """
            )
    assert "position" in str(error.value).lower()


def test_position_history_is_append_only(connection):
    _base(connection)
    _position(connection)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.position_receipt
            (receipt_id, external_order_identity, execution_extent_identity,
             executed_base_quantity, external_status, receipt_payload,
             receipt_digest, normalization_version)
            VALUES ('receipt-1', 'order-1', 'extent-1', 10, 'FILLED', '{}',
                    'digest-1', 'v1')
            """
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
            VALUES ('position-1', 'intent-1', 'OPEN', 'effect-1', 'attempt-1',
                    'order-1', 'extent-1', 'receipt-1', 0, 10, 10, 1,
                    'context-1', 'decision-1', 1, 'v1')
            """
        )
        connection.commit()
        with pytest.raises(psycopg2.Error) as error:
            cursor.execute(
                "UPDATE handa_live.position_effect_event SET applied_quantity=9"
            )
    assert "immutable" in str(error.value).lower()
