"""PostgreSQL-backed falsifiers for DB-002..DB-023."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from urllib.parse import urlparse

import psycopg2
import pytest

from core.persistence.live_order_store import LiveOrderStore, live_order_resource_scope
from core.persistence.persistence_coordinator import DatabaseIdentity, PersistenceCoordinator


ROOT = Path(__file__).parents[2]
MIGRATIONS = [
    ROOT / "core" / "persistence" / "migrations" / name
    for name in (
        "001_create_handa_live.sql",
        "002_relax_may_have_been_submitted_certainty.sql",
        "003_reconciliation_evidence.sql",
        "004_external_order_observation_contract.sql",
        "005_decision_ledger.sql",
    )
]
EXPECTED_DATABASE = "handa_test"
EXPECTED_USER = "handa_test"
EXPECTED_HOSTS = {"127.0.0.1", "localhost"}
EXPECTED_PORT = 55432


def _database_url():
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.fail("TEST_DATABASE_URL is required; refusing database falsifier.")
    parsed = urlparse(value)
    if (
        parsed.hostname not in EXPECTED_HOSTS
        or parsed.port != EXPECTED_PORT
        or parsed.path.lstrip("/") != EXPECTED_DATABASE
        or parsed.username != EXPECTED_USER
    ):
        pytest.fail("TEST_DATABASE_URL is not the authorized local disposable database.")
    return value


def _connect():
    return psycopg2.connect(_database_url())


@pytest.fixture()
def connection():
    connection = _connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            for migration in MIGRATIONS:
                cursor.execute(migration.read_text(encoding="utf-8"))
        connection.commit()
        yield connection
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
        connection.commit()
        connection.close()


def _intent(connection, intent_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.order_intent
            (intent_id, venue, account_scope, client_order_id, slot_id, symbol,
             side, requested_quote_amount, submission_lifecycle_state)
            VALUES (%s, 'BINANCE_SPOT', 'test-account', %s, %s, 'BTCUSDC',
                    'BUY', 10, 'READY_TO_SUBMIT')
            """,
            (intent_id, f"client-{intent_id}", f"slot-{intent_id}"),
        )


def _context(connection, context_id, intent_id, sequence, state="ACTIVE", closed=False):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.reconciliation_context
            (context_id, intent_id, context_sequence, context_state, closed_at,
             closure_reason)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                context_id,
                intent_id,
                sequence,
                state,
                datetime.now(timezone.utc) if closed else None,
                "test-closed" if closed else None,
            ),
        )


def _decision_values(decision_id, context_id, intent_id, sequence=1):
    return (
        decision_id,
        context_id,
        intent_id,
        sequence,
        datetime.now(timezone.utc),
        "ORDER_OUTCOME",
        "PENDING",
        '{"value": "UNKNOWN"}',
        '{"value": "UNKNOWN"}',
        '{"value": "UNKNOWN"}',
        '{"value": "UNKNOWN"}',
        '{"source": "db-test"}',
        "v1",
        "v1",
        "v1",
        "LINEAGE_INCOMPLETE",
    )


def _decision(connection, decision_id, context_id, intent_id, sequence=1):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.semantic_decision
            (decision_id, context_id, intent_id, decision_sequence, evaluation_time,
             decision_scope, authority_state, execution_occurred,
             order_outcome_terminal, execution_extent, final_partial_outcome,
             evaluated_input_snapshot, authority_contract_version,
             decision_schema_version, evidence_normalization_version,
             lineage_completeness_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s::jsonb, %s, %s, %s, %s)
            """,
            _decision_values(decision_id, context_id, intent_id, sequence),
        )


def _evidence(connection, evidence_id, intent_id, order_id="order-1"):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.exchange_evidence
            (evidence_id, intent_id, evidence_sequence, symbol, exchange_order_id,
             exchange_status, raw_snapshot, observed_at)
            VALUES (%s, %s, 1, 'BTCUSDC', %s, 'FILLED', %s::jsonb, %s)
            """,
            (evidence_id, intent_id, order_id, '{"status":"FILLED"}', datetime.now(timezone.utc)),
        )


def _normalized(connection, revision_id, evidence_id, intent_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.normalized_evidence
            (normalized_revision_id, evidence_id, intent_id, revision_sequence,
             exchange_status, normalized_status, provenance, normalized_payload)
            VALUES (%s, %s, %s, 1, 'FILLED', 'FILLED', '{}'::jsonb, '{}'::jsonb)
            """,
            (revision_id, evidence_id, intent_id),
        )


def _trade(connection, evidence_id, intent_id, trade_id="trade-1", order_id="order-1"):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.trade_effect
            (symbol, exchange_order_id, exchange_trade_id, evidence_id, intent_id,
             price, gross_base_qty, quote_qty, commission_amount, commission_asset)
            VALUES ('BTCUSDC', %s, %s, %s, %s, 100, .1, 10, 0, 'USDC')
            """,
            (order_id, trade_id, evidence_id, intent_id),
        )


def _reference(connection, reference_id, decision_id, intent_id, kind, **extra):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.decision_evidence_reference
            (reference_id, decision_id, intent_id, evidence_kind, semantic_role)
            VALUES (%s, %s, %s, %s, 'test')
            """,
            (reference_id, decision_id, intent_id, kind),
        )
        if kind == "EXCHANGE_OBSERVATION":
            cursor.execute(
                "INSERT INTO handa_live.decision_exchange_observation_ref VALUES (%s, %s, %s)",
                (reference_id, extra["evidence_id"], intent_id),
            )
        elif kind == "NORMALIZED_REVISION":
            cursor.execute(
                "INSERT INTO handa_live.decision_normalized_revision_ref VALUES (%s, %s, %s)",
                (reference_id, extra["normalized_revision_id"], intent_id),
            )
        elif kind == "TRADE_FILL":
            cursor.execute(
                "INSERT INTO handa_live.decision_trade_fill_ref VALUES (%s, 'BTCUSDC', %s, %s, %s)",
                (reference_id, extra["exchange_order_id"], extra["exchange_trade_id"], intent_id),
            )
        else:
            cursor.execute(
                "INSERT INTO handa_live.decision_contradiction_basis_ref VALUES (%s, %s, %s)",
                (reference_id, extra["basis_reference_id"], intent_id),
            )


def _expect_rejected(connection, statement, params=(), reason=None):
    with pytest.raises(psycopg2.Error) as error:
        with connection.cursor() as cursor:
            cursor.execute(statement, params)
    message = str(error.value)
    connection.rollback()
    if reason:
        assert reason in message
    return message


def test_db002_multiple_historical_contexts_per_intent(connection):
    _intent(connection, "i-1")
    _context(connection, "c-1", "i-1", 1, "CLOSED", closed=True)
    _context(connection, "c-2", "i-1", 2, "CLOSED", closed=True)
    _context(connection, "c-3", "i-1", 3)
    connection.commit()
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM handa_live.reconciliation_context WHERE intent_id='i-1'")
        assert cursor.fetchone() == (3,)


def test_db003_second_active_context_rejected(connection):
    _intent(connection, "i-1")
    _context(connection, "c-1", "i-1", 1)
    connection.commit()
    _expect_rejected(
        connection,
        "INSERT INTO handa_live.reconciliation_context VALUES (%s,%s,2,'ACTIVE',CURRENT_TIMESTAMP,NULL,NULL)",
        ("c-2", "i-1"),
        "reconciliation_context_one_active_per_intent",
    )


def test_db004_context_sequence_uniqueness(connection):
    _intent(connection, "i-1")
    _context(connection, "c-1", "i-1", 1)
    connection.commit()
    _expect_rejected(
        connection,
        "INSERT INTO handa_live.reconciliation_context (context_id,intent_id,context_sequence,context_state,created_at,closed_at,closure_reason) VALUES ('c-2','i-1',1,'CLOSED',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'duplicate')",
        reason="reconciliation_context_intent_id_context_sequence_key",
    )


def test_db005_decision_sequence_uniqueness(connection):
    _intent(connection, "i-1")
    _context(connection, "c-1", "i-1", 1)
    _decision(connection, "d-1", "c-1", "i-1")
    connection.commit()
    _expect_rejected(
        connection,
        "INSERT INTO handa_live.semantic_decision (decision_id,context_id,intent_id,decision_sequence,evaluation_time,decision_scope,authority_state,execution_occurred,order_outcome_terminal,execution_extent,final_partial_outcome,unknown_reason,contradiction_result,decision_reason,evaluated_input_snapshot,authority_contract_version,decision_schema_version,evidence_normalization_version,lineage_completeness_status) SELECT 'd-2',context_id,intent_id,1,evaluation_time,decision_scope,authority_state,execution_occurred,order_outcome_terminal,execution_extent,final_partial_outcome,unknown_reason,contradiction_result,decision_reason,evaluated_input_snapshot,authority_contract_version,decision_schema_version,evidence_normalization_version,lineage_completeness_status FROM handa_live.semantic_decision WHERE decision_id='d-1'",
        reason="semantic_decision_context_id_decision_sequence_key",
    )


def test_db006_sequence_gaps_accepted(connection):
    _intent(connection, "i-1")
    _context(connection, "c-1", "i-1", 1, "CLOSED", closed=True)
    _context(connection, "c-3", "i-1", 3)
    _decision(connection, "d-1", "c-3", "i-1", 1)
    _decision(connection, "d-3", "c-3", "i-1", 3)
    connection.commit()
    with connection.cursor() as cursor:
        cursor.execute("SELECT context_sequence FROM handa_live.reconciliation_context WHERE intent_id='i-1' ORDER BY context_sequence")
        assert [row[0] for row in cursor.fetchall()] == [1, 3]
        cursor.execute("SELECT decision_sequence FROM handa_live.semantic_decision WHERE context_id='c-3' ORDER BY decision_sequence")
        assert [row[0] for row in cursor.fetchall()] == [1, 3]


def test_db007_semantic_decision_update_rejected(connection):
    _intent(connection, "i-1"); _context(connection, "c-1", "i-1", 1); _decision(connection, "d-1", "c-1", "i-1"); connection.commit()
    _expect_rejected(connection, "UPDATE handa_live.semantic_decision SET decision_reason='mutated' WHERE decision_id='d-1'", reason="semantic decision ledger rows are immutable")


def test_db008_semantic_decision_delete_rejected(connection):
    _intent(connection, "i-1"); _context(connection, "c-1", "i-1", 1); _decision(connection, "d-1", "c-1", "i-1"); connection.commit()
    _expect_rejected(connection, "DELETE FROM handa_live.semantic_decision WHERE decision_id='d-1'", reason="semantic decision ledger rows are immutable")


def test_db009_typed_lineage_update_delete_rejected(connection):
    _intent(connection, "i-1"); _context(connection, "c-1", "i-1", 1); _decision(connection, "d-1", "c-1", "i-1"); _evidence(connection, "e-1", "i-1"); _normalized(connection, "n-1", "e-1", "i-1"); _trade(connection, "e-1", "i-1");
    _reference(connection, "r-1", "d-1", "i-1", "EXCHANGE_OBSERVATION", evidence_id="e-1")
    _reference(connection, "r-2", "d-1", "i-1", "NORMALIZED_REVISION", normalized_revision_id="n-1")
    _reference(connection, "r-3", "d-1", "i-1", "TRADE_FILL", exchange_order_id="order-1", exchange_trade_id="trade-1")
    _reference(connection, "r-4", "d-1", "i-1", "CONTRADICTION_BASIS", basis_reference_id="r-1")
    connection.commit()
    for table, reference_id in (
        ("decision_evidence_reference", "r-1"),
        ("decision_exchange_observation_ref", "r-1"),
        ("decision_normalized_revision_ref", "r-2"),
        ("decision_trade_fill_ref", "r-3"),
        ("decision_contradiction_basis_ref", "r-4"),
    ):
        _expect_rejected(connection, f"UPDATE handa_live.{table} SET reference_id=reference_id WHERE reference_id=%s", (reference_id,), reason="semantic decision ledger rows are immutable")
        _expect_rejected(connection, f"DELETE FROM handa_live.{table} WHERE reference_id=%s", (reference_id,), reason="semantic decision ledger rows are immutable")


def test_db010_context_cross_intent_mismatch_rejected(connection):
    _intent(connection, "i-1"); _intent(connection, "i-2"); _context(connection, "c-1", "i-1", 1); connection.commit()
    _expect_rejected(connection, "INSERT INTO handa_live.semantic_decision (decision_id,context_id,intent_id,decision_sequence,evaluation_time,decision_scope,authority_state,execution_occurred,order_outcome_terminal,execution_extent,final_partial_outcome,evaluated_input_snapshot,authority_contract_version,decision_schema_version,evidence_normalization_version,lineage_completeness_status) VALUES ('d-1','c-1','i-2',1,CURRENT_TIMESTAMP,'ORDER_OUTCOME','PENDING','{}','{}','{}','{}','{}','v1','v1','v1','LINEAGE_INCOMPLETE')", reason="violates foreign key constraint")


def test_db011_decision_cross_intent_mismatch_rejected(connection):
    _intent(connection, "i-1"); _context(connection, "c-1", "i-1", 1); _decision(connection, "d-1", "c-1", "i-1"); connection.commit()
    _expect_rejected(connection, "INSERT INTO handa_live.decision_evidence_reference VALUES ('r-1','d-1','wrong','EXCHANGE_OBSERVATION','test')", reason="violates foreign key constraint")


@pytest.mark.parametrize("kind,statement,params", [
    ("exchange", "INSERT INTO handa_live.decision_exchange_observation_ref VALUES ('r-wrong','e-1','i-2')", ()),
    ("normalized", "INSERT INTO handa_live.decision_normalized_revision_ref VALUES ('r-wrong','n-1','i-2')", ()),
    ("trade", "INSERT INTO handa_live.decision_trade_fill_ref VALUES ('r-wrong','BTCUSDC','order-1','trade-1','i-2')", ()),
])
def test_db012_to_db014_wrong_intent_lineage_rejected(connection, kind, statement, params):
    _intent(connection, "i-1"); _intent(connection, "i-2"); _context(connection, "c-1", "i-1", 1); _decision(connection, "d-1", "c-1", "i-1")
    if kind == "exchange":
        _evidence(connection, "e-1", "i-1")
        _reference(connection, "r-1", "d-1", "i-1", "EXCHANGE_OBSERVATION", evidence_id="e-1")
    elif kind == "normalized":
        _evidence(connection, "e-1", "i-1"); _normalized(connection, "n-1", "e-1", "i-1")
        _reference(connection, "r-1", "d-1", "i-1", "NORMALIZED_REVISION", normalized_revision_id="n-1")
    else:
        _evidence(connection, "e-1", "i-1"); _trade(connection, "e-1", "i-1")
        _reference(connection, "r-1", "d-1", "i-1", "TRADE_FILL", exchange_order_id="order-1", exchange_trade_id="trade-1")
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO handa_live.decision_evidence_reference (reference_id,decision_id,intent_id,evidence_kind,semantic_role) VALUES ('r-wrong','d-1','i-1','EXCHANGE_OBSERVATION','wrong-intent-test')"
        )
    connection.commit()
    _expect_rejected(connection, statement, params, reason="violates foreign key constraint")


def test_db015_contradiction_basis_integrity_enforced(connection):
    _intent(connection, "i-1"); _context(connection, "c-1", "i-1", 1); _decision(connection, "d-1", "c-1", "i-1")
    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO handa_live.decision_evidence_reference VALUES ('r-1','d-1','i-1','EXCHANGE_OBSERVATION','test')")
    connection.commit()
    _expect_rejected(connection, "INSERT INTO handa_live.decision_contradiction_basis_ref VALUES ('r-1','r-1','i-1')", reason="violates check constraint")


def test_db016_submission_attempt_context_mismatch_rejected(connection):
    _intent(connection, "i-1"); _intent(connection, "i-2"); _context(connection, "c-1", "i-1", 1); connection.commit()
    _expect_rejected(connection, "INSERT INTO handa_live.submission_attempt (attempt_id,intent_id,attempt_sequence,context_id,venue,account_scope,client_order_id,submission_lifecycle_state) VALUES ('a-1','i-2',1,'c-1','BINANCE_SPOT','test-account','client-i-2','SUBMISSION_ATTEMPTED')", reason="violates foreign key constraint")


def test_db017_current_projection_cross_intent_mismatch_rejected(connection):
    _intent(connection, "i-1"); _intent(connection, "i-2"); _context(connection, "c-1", "i-1", 1); _decision(connection, "d-1", "c-1", "i-1"); connection.commit()
    _expect_rejected(connection, "UPDATE handa_live.order_intent SET current_context_id='c-1' WHERE intent_id='i-2'", reason="violates foreign key constraint")


def test_db018_rollback_creates_no_semantic_history(connection):
    _intent(connection, "i-1"); _context(connection, "c-1", "i-1", 1); connection.commit()
    with pytest.raises(RuntimeError):
        with connection:
            _decision(connection, "d-rollback", "c-1", "i-1")
            raise RuntimeError("forced rollback")
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM handa_live.semantic_decision WHERE decision_id='d-rollback'")
        assert cursor.fetchone() == (0,)


def _concurrent_context_sequence(intent_id, context_id, barrier):
    connection = _connect(); connection.autocommit = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("BEGIN")
            barrier.wait()
            cursor.execute("SELECT intent_id FROM handa_live.order_intent WHERE intent_id=%s FOR UPDATE", (intent_id,))
            cursor.execute("SELECT COALESCE(MAX(context_sequence),0)+1 FROM handa_live.reconciliation_context WHERE intent_id=%s", (intent_id,))
            sequence = cursor.fetchone()[0]
            cursor.execute("INSERT INTO handa_live.reconciliation_context (context_id,intent_id,context_sequence,context_state,closed_at,closure_reason) VALUES (%s,%s,%s,'CLOSED',CURRENT_TIMESTAMP,'concurrent-test')", (context_id, intent_id, sequence))
        connection.commit(); return sequence
    finally:
        connection.close()


def _concurrent_decision_sequence(context_id, intent_id, decision_id, barrier):
    connection = _connect(); connection.autocommit = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("BEGIN")
            barrier.wait()
            cursor.execute("SELECT context_id FROM handa_live.reconciliation_context WHERE context_id=%s FOR UPDATE", (context_id,))
            cursor.execute("SELECT COALESCE(MAX(decision_sequence),0)+1 FROM handa_live.semantic_decision WHERE context_id=%s", (context_id,))
            sequence = cursor.fetchone()[0]
            cursor.execute("INSERT INTO handa_live.semantic_decision (decision_id,context_id,intent_id,decision_sequence,evaluation_time,decision_scope,authority_state,execution_occurred,order_outcome_terminal,execution_extent,final_partial_outcome,evaluated_input_snapshot,authority_contract_version,decision_schema_version,evidence_normalization_version,lineage_completeness_status) VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP,'ORDER_OUTCOME','PENDING','{}','{}','{}','{}','{}','v1','v1','v1','LINEAGE_INCOMPLETE')", (decision_id, context_id, intent_id, sequence))
        connection.commit(); return sequence
    finally:
        connection.close()


def test_db019_concurrent_context_sequence_allocation_preserves_uniqueness(connection):
    _intent(connection, "i-1"); connection.commit()
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        sequences = list(pool.map(lambda value: _concurrent_context_sequence("i-1", value, barrier), ("c-1", "c-2")))
    assert sorted(sequences) == [1, 2]


def test_db020_concurrent_decision_sequence_allocation_preserves_uniqueness(connection):
    _intent(connection, "i-1"); _context(connection, "c-1", "i-1", 1); connection.commit()
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        sequences = list(pool.map(lambda value: _concurrent_decision_sequence("c-1", "i-1", value, barrier), ("d-1", "d-2")))
    assert sorted(sequences) == [1, 2]


def test_db021_migration004_structured_fields_remain_store_accessible(connection):
    _intent(connection, "i-1"); connection.commit()
    coordinator = PersistenceCoordinator(_database_url(), DatabaseIdentity(frozenset(EXPECTED_HOSTS), EXPECTED_PORT, EXPECTED_DATABASE, EXPECTED_USER), resource_scope=live_order_resource_scope())
    try:
        LiveOrderStore(coordinator).record_exchange_observation(evidence_id="e-1", intent_id="i-1", evidence_sequence=1, symbol="BTCUSDC", raw_snapshot={}, observed_at=datetime.now(timezone.utc), client_order_id_observed="client-i-1", order_type="LIMIT", time_in_force="GTC", orig_qty=Decimal("1"), orig_quote_order_qty=Decimal("10"), executed_qty=Decimal("1"), cumulative_quote_qty=Decimal("10"), observation_class="ORDER_STATE", observation_source="BINANCE_SPOT_ORDER_QUERY")
    finally:
        coordinator.close()
    with connection.cursor() as cursor:
        cursor.execute("SELECT client_order_id_observed, order_type, time_in_force, orig_qty, orig_quote_order_qty, executed_qty, cumulative_quote_qty, observation_class, observation_source FROM handa_live.exchange_evidence WHERE evidence_id='e-1'")
        assert cursor.fetchone() == ('client-i-1', 'LIMIT', 'GTC', Decimal('1'), Decimal('10'), Decimal('1'), Decimal('10'), 'ORDER_STATE', 'BINANCE_SPOT_ORDER_QUERY')


def test_db022_legacy_records_remain_intact(connection):
    _intent(connection, "i-1"); _evidence(connection, "e-1", "i-1");
    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO handa_live.reconciliation (reconciliation_id,intent_id,decision_sequence,reconciliation_state,execution_certainty) VALUES ('r-legacy','i-1',1,'PENDING','UNKNOWN')")
    connection.commit()
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM handa_live.reconciliation WHERE reconciliation_id='r-legacy'")
        assert cursor.fetchone() == (1,)
        cursor.execute("SELECT count(*) FROM handa_live.exchange_evidence WHERE evidence_id='e-1'")
        assert cursor.fetchone() == (1,)


def test_db023_no_synthetic_semantic_decisions_or_lineage_created(connection):
    _intent(connection, "i-1"); _evidence(connection, "e-1", "i-1");
    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO handa_live.reconciliation (reconciliation_id,intent_id,decision_sequence,reconciliation_state,execution_certainty) VALUES ('r-legacy','i-1',1,'PENDING','UNKNOWN')")
    connection.commit()
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM handa_live.semantic_decision")
        assert cursor.fetchone() == (0,)
        cursor.execute("SELECT count(*) FROM handa_live.decision_evidence_reference")
        assert cursor.fetchone() == (0,)


def _parent_reference(connection, reference_id, decision_id, intent_id, kind):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.decision_evidence_reference
            (reference_id, decision_id, intent_id, evidence_kind, semantic_role)
            VALUES (%s, %s, %s, %s, 'identity-gap-test')
            """,
            (reference_id, decision_id, intent_id, kind),
        )


def test_db024_parent_child_exchange_lineage_identity_gap(connection):
    _intent(connection, "intent-a"); _intent(connection, "intent-b")
    _context(connection, "context-a", "intent-a", 1)
    _decision(connection, "decision-a", "context-a", "intent-a")
    _evidence(connection, "evidence-b", "intent-b", order_id="order-b")
    _parent_reference(connection, "reference-a", "decision-a", "intent-a", "EXCHANGE_OBSERVATION")
    connection.commit()
    _expect_rejected(
        connection,
        "INSERT INTO handa_live.decision_exchange_observation_ref (reference_id,evidence_id,intent_id) VALUES ('reference-a','evidence-b','intent-b')",
        reason="decision_exchange_observation_ref_reference_id_intent_id_fkey",
    )


def test_db025_parent_child_normalized_lineage_identity_gap(connection):
    _intent(connection, "intent-a"); _intent(connection, "intent-b")
    _context(connection, "context-a", "intent-a", 1)
    _decision(connection, "decision-a", "context-a", "intent-a")
    _evidence(connection, "evidence-b", "intent-b", order_id="order-b")
    _normalized(connection, "revision-b", "evidence-b", "intent-b")
    _parent_reference(connection, "reference-a", "decision-a", "intent-a", "NORMALIZED_REVISION")
    connection.commit()
    _expect_rejected(
        connection,
        "INSERT INTO handa_live.decision_normalized_revision_ref (reference_id,normalized_revision_id,intent_id) VALUES ('reference-a','revision-b','intent-b')",
        reason="decision_normalized_revision_ref_reference_id_intent_id_fkey",
    )


def test_db026_parent_child_trade_lineage_identity_gap(connection):
    _intent(connection, "intent-a"); _intent(connection, "intent-b")
    _context(connection, "context-a", "intent-a", 1)
    _decision(connection, "decision-a", "context-a", "intent-a")
    _evidence(connection, "evidence-b", "intent-b", order_id="order-b")
    _trade(connection, "evidence-b", "intent-b", trade_id="trade-b", order_id="order-b")
    _parent_reference(connection, "reference-a", "decision-a", "intent-a", "TRADE_FILL")
    connection.commit()
    _expect_rejected(
        connection,
        "INSERT INTO handa_live.decision_trade_fill_ref (reference_id,symbol,exchange_order_id,exchange_trade_id,intent_id) VALUES ('reference-a','BTCUSDC','order-b','trade-b','intent-b')",
        reason="decision_trade_fill_ref_reference_id_intent_id_fkey",
    )


def test_db027_parent_child_contradiction_lineage_identity_gap(connection):
    _intent(connection, "intent-a"); _intent(connection, "intent-b")
    _context(connection, "context-a", "intent-a", 1)
    _decision(connection, "decision-a", "context-a", "intent-a")
    _context(connection, "context-b", "intent-b", 1)
    _decision(connection, "decision-b", "context-b", "intent-b")
    _parent_reference(connection, "reference-a", "decision-a", "intent-a", "CONTRADICTION_BASIS")
    _parent_reference(connection, "reference-b", "decision-b", "intent-b", "EXCHANGE_OBSERVATION")
    connection.commit()
    _expect_rejected(
        connection,
        "INSERT INTO handa_live.decision_contradiction_basis_ref (reference_id,basis_reference_id,intent_id) VALUES ('reference-a','reference-b','intent-b')",
        reason="decision_contradiction_basis_ref_reference_id_intent_id_fkey",
    )


def test_db028_cross_intent_predecessor_context_identity_gap(connection):
    _intent(connection, "intent-a"); _intent(connection, "intent-b")
    _context(connection, "context-a", "intent-a", 1, "CLOSED", closed=True)
    connection.commit()
    _expect_rejected(
        connection,
        """
        INSERT INTO handa_live.reconciliation_context
        (context_id,intent_id,context_sequence,context_state,predecessor_context_id,predecessor_intent_id,closed_at,closure_reason)
        VALUES ('context-b','intent-b',1,'CLOSED','context-a','intent-b',CURRENT_TIMESTAMP,'cross-intent-test')
        """,
        reason="reconciliation_context_predecessor_context_id_predecessor__fkey",
    )
