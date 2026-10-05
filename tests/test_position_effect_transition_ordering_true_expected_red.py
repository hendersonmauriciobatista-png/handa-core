"""True expected-RED tests for the desired persistent REDUCE/CLOSE ordering."""

import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest

from core.execution.operational_effect_adapter import EffectType, LogicalEffectIdentity
from core.persistence.effect_application_ledger import EffectApplicationLedger
from core.position.position_effect_authority import PositionEffectAuthority
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
EXPECTED_DATABASE_URL = (
    "postgresql://handa_test:handa_test_only@127.0.0.1:55432/handa_test"
)


def _database_url():
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.fail("TEST_DATABASE_URL is required for PostgreSQL falsifiers")
    parsed = urlparse(value)
    if value != EXPECTED_DATABASE_URL or parsed.port != 55432:
        pytest.fail("refusing non-governed PostgreSQL target")
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


def _binding(*, logical_effect_id, effect_request_id, effect_type):
    return {
        "logical_identity": LogicalEffectIdentity("intent-a", logical_effect_id),
        "effect_request_id": effect_request_id,
        "effect_type": effect_type,
        "authority_decision_id": "decision-a",
        "reconciliation_context_id": "context-a",
        "decision_sequence": 1,
        "authority_contract_version": "v1",
    }


def _binding_values(binding):
    return {
        "reconciliation_context_id": binding["reconciliation_context_id"],
        "semantic_decision_id": binding["authority_decision_id"],
        "decision_sequence": binding["decision_sequence"],
        "authority_contract_version": binding["authority_contract_version"],
    }


def _receipt(receipt_id, order_id, quantity):
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
        "producer_id": "position-ordering-true-red",
        "payload": {"receipt_id": receipt_id},
    }


def _create_open(connection):
    binding = _binding(
        logical_effect_id="logical-open",
        effect_request_id="request-open",
        effect_type=EffectType.OPEN,
    )
    ledger = EffectApplicationLedger(connection)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)
    with ledger.transaction_scope() as cursor:
        ledger.bind_logical_effect(cursor=cursor, **binding)
        ledger.claim_application(
            "request-open", application_attempt_id="attempt-open", cursor=cursor
        )
        authority.apply_open(
            position_id="position-1",
            intended_quantity=10,
            receipt=_receipt("position-receipt-request-open", "order-open", 10),
            intent_id="intent-a",
            symbol="BTCUSDC",
            effect_request_id="request-open",
            cursor=cursor,
            **_binding_values(binding),
        )
        ledger.mark_applied(
            "request-open",
            application_attempt_id="attempt-open",
            receipt=_ledger_receipt("ledger-receipt-open"),
            cursor=cursor,
        )


def _durable_effect_state(connection, effect_request_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_state FROM handa_live.effect_request "
            "WHERE effect_request_id=%s",
            (effect_request_id,),
        )
        request_state = cursor.fetchone()[0]
        cursor.execute(
            "SELECT attempt_state FROM handa_live.application_attempt "
            "WHERE effect_request_id=%s",
            (effect_request_id,),
        )
        attempt_state = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT effect_type, previous_quantity, applied_quantity,
                   resulting_quantity
            FROM handa_live.position_effect_event
            WHERE effect_request_id=%s
            """,
            (effect_request_id,),
        )
        event = cursor.fetchone()
        cursor.execute(
            "SELECT lifecycle_state, current_quantity "
            "FROM handa_live.position WHERE position_id='position-1'"
        )
        position = cursor.fetchone()
        cursor.execute(
            "SELECT COUNT(*) FROM handa_live.position_receipt "
            "WHERE receipt_id=%s",
            (f"position-receipt-{effect_request_id}",),
        )
        receipt_count = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COUNT(*) FROM handa_live.applied_effect "
            "WHERE effect_request_id=%s",
            (effect_request_id,),
        )
        applied_count = cursor.fetchone()[0]
    return request_state, attempt_state, event, position, receipt_count, applied_count


def test_peo_open_baseline_remains_protected(connection):
    _create_open(connection)
    assert _durable_effect_state(connection, "request-open") == (
        "APPLIED",
        "APPLIED",
        ("OPEN", 0, 10, 10),
        ("ACTIVE", 10),
        1,
        1,
    )


def test_peo_green_001_persistent_reduce_desired_behavior(connection):
    _create_open(connection)
    binding = _binding(
        logical_effect_id="logical-reduce",
        effect_request_id="request-reduce",
        effect_type=EffectType.REDUCE,
    )
    ledger = EffectApplicationLedger(connection)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)

    # Assert the complete persistent REDUCE path and durable post-commit state.
    with ledger.transaction_scope() as cursor:
        ledger.bind_logical_effect(cursor=cursor, **binding)
        ledger.claim_application(
            "request-reduce", application_attempt_id="attempt-reduce", cursor=cursor
        )
        authority.apply_reduction(
            position_id="position-1",
            applied_quantity=4,
            receipt=_receipt(
                "position-receipt-request-reduce", "order-reduce", 4
            ),
            effect_request_id="request-reduce",
            cursor=cursor,
            **_binding_values(binding),
        )
        ledger.mark_applied(
            "request-reduce",
            application_attempt_id="attempt-reduce",
            receipt=_ledger_receipt("ledger-receipt-reduce"),
            cursor=cursor,
        )

    assert _durable_effect_state(connection, "request-reduce") == (
        "APPLIED",
        "APPLIED",
        ("REDUCE", 10, 4, 6),
        ("ACTIVE", 6),
        1,
        1,
    )


def test_peo_green_002_persistent_close_desired_behavior(connection):
    _create_open(connection)
    binding = _binding(
        logical_effect_id="logical-close",
        effect_request_id="request-close",
        effect_type=EffectType.CLOSE,
    )
    ledger = EffectApplicationLedger(connection)
    authority = PositionEffectAuthority(connection=connection, ledger=ledger)

    # Assert the complete persistent CLOSE path and durable post-commit state.
    with ledger.transaction_scope() as cursor:
        ledger.bind_logical_effect(cursor=cursor, **binding)
        ledger.claim_application(
            "request-close", application_attempt_id="attempt-close", cursor=cursor
        )
        authority.apply_close(
            position_id="position-1",
            receipt=_receipt("position-receipt-request-close", "order-close", 10),
            effect_request_id="request-close",
            cursor=cursor,
            **_binding_values(binding),
        )
        ledger.mark_applied(
            "request-close",
            application_attempt_id="attempt-close",
            receipt=_ledger_receipt("ledger-receipt-close"),
            cursor=cursor,
        )

    assert _durable_effect_state(connection, "request-close") == (
        "APPLIED",
        "APPLIED",
        ("CLOSE", 10, 10, 0),
        ("CLOSED", 0),
        1,
        1,
    )
