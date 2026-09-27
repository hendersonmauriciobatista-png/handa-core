import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest

from core.execution.live_order_models import LiveOrderIntent, OrderSide
from core.persistence.live_order_store import (
    LiveOrderStore,
    live_order_resource_scope,
)
from core.persistence.persistence_coordinator import (
    DatabaseIdentity,
    PersistenceCoordinator,
)
from core.persistence.transaction_context import (
    InvalidCapabilityRequest,
    UniqueConflict,
    VersionConflict,
)


EXPECTED_DATABASE = "handa_test"
EXPECTED_USER = "handa_test"
EXPECTED_HOSTS = {"127.0.0.1", "localhost"}
EXPECTED_PORT = 55432
MIGRATION = (
    Path(__file__).parents[2]
    / "core"
    / "persistence"
    / "migrations"
    / "001_create_handa_live.sql"
)
MIGRATION_002 = (
    Path(__file__).parents[2]
    / "core"
    / "persistence"
    / "migrations"
    / "002_relax_may_have_been_submitted_certainty.sql"
)


def _connect_test_database():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("TEST_DATABASE_URL is required; refusing Store test.")
    parsed = urlparse(database_url)
    if (
        parsed.hostname not in EXPECTED_HOSTS
        or parsed.port != EXPECTED_PORT
        or parsed.path.lstrip("/") != EXPECTED_DATABASE
        or parsed.username != EXPECTED_USER
    ):
        pytest.fail("TEST_DATABASE_URL does not identify the governed local test database.")
    return psycopg2.connect(database_url)


@pytest.fixture()
def store_and_connection():
    database_url = os.environ["TEST_DATABASE_URL"]
    connection = _connect_test_database()
    with connection.cursor() as cursor:
        cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
        cursor.execute(MIGRATION.read_text(encoding="utf-8"))
        cursor.execute(MIGRATION_002.read_text(encoding="utf-8"))
    connection.commit()
    coordinator = PersistenceCoordinator(
        database_url,
        DatabaseIdentity(
            allowed_hosts=frozenset(EXPECTED_HOSTS),
            port=EXPECTED_PORT,
            database=EXPECTED_DATABASE,
            user=EXPECTED_USER,
        ),
        resource_scope=live_order_resource_scope(),
    )
    store = LiveOrderStore(coordinator)
    try:
        yield store, connection
    finally:
        coordinator.close()
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
        connection.commit()
        connection.close()


def _intent(intent_id: str, client_order_id: str, symbol: str = "BTCUSDC"):
    return LiveOrderIntent(
        intent_id=intent_id,
        client_order_id=client_order_id,
        slot_id=f"slot-{intent_id}",
        symbol=symbol,
        side=OrderSide.BUY,
        requested_quote_amount=Decimal("10.00000000"),
        policy_context="test-policy",
    )


def _prepare(store, intent_id, client_order_id, expected_version=0):
    return store.record_submission_preparation(
        intent_id=intent_id,
        attempt_id=f"attempt-{intent_id}",
        attempt_sequence=1,
        venue="BINANCE_SPOT",
        account_scope="test-account",
        client_order_id=client_order_id,
        expected_version=expected_version,
    )


def _handoff(store, intent_id, expected_version):
    return store.record_external_handoff(
        intent_id=intent_id,
        expected_version=expected_version,
    )


def _observation(store, intent_id, evidence_id, order_id, expected_version, effects=()):
    store.record_exchange_observation(
        evidence_id=evidence_id,
        intent_id=intent_id,
        evidence_sequence=1,
        symbol="BTCUSDC",
        exchange_order_id=order_id,
        exchange_status="PARTIALLY_FILLED",
        raw_snapshot={"orderId": order_id, "status": "PARTIALLY_FILLED"},
        observed_at=datetime.now(timezone.utc),
        expected_version=expected_version,
        normalized_revision={
            "normalized_revision_id": f"revision-{evidence_id}",
            "revision_sequence": 1,
            "exchange_status": "PARTIALLY_FILLED",
            "normalized_status": "PARTIALLY_FILLED",
            "provenance": {"source": "exchange"},
            "normalized_payload": {"executed": True},
        },
        trade_effects=effects,
    )


def _effect(trade_id, evidence_id):
    return {
        "symbol": "BTCUSDC",
        "exchange_order_id": "order-1",
        "exchange_trade_id": trade_id,
        "price": Decimal("100.12000000"),
        "gross_base_qty": Decimal("0.01000000"),
        "quote_qty": Decimal("1.001200000000"),
        "commission_amount": Decimal("0.00010000"),
        "commission_asset": "USDC",
        "evidence_id": evidence_id,
    }


def test_pre_submit_and_unknown_boundary(store_and_connection):
    store, connection = store_and_connection
    created = store.create_intent(
        _intent("intent-1", "client-1"),
        venue="BINANCE_SPOT",
        account_scope="test-account",
    )
    assert created["submission_lifecycle_state"] == "READY_TO_SUBMIT"
    assert created["execution_certainty"] is None

    prepared = _prepare(store, "intent-1", "client-1")
    assert prepared["submission_lifecycle_state"] == "SUBMISSION_ATTEMPTED"
    assert prepared["execution_certainty"] is None

    handed_off = _handoff(store, "intent-1", prepared["current_version"])
    assert handed_off["submission_lifecycle_state"] == "MAY_HAVE_BEEN_SUBMITTED"
    assert handed_off["execution_certainty"] == "UNKNOWN"
    assert handed_off["reconciliation_state"] == "PENDING"

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT execution_certainty, reconciliation_state FROM handa_live.order_intent WHERE intent_id = %s",
            ("intent-1",),
        )
        assert cursor.fetchone() == ("UNKNOWN", "PENDING")


def test_unknown_cannot_be_reprepared_or_cleared(store_and_connection):
    store, _ = store_and_connection
    store.create_intent(_intent("intent-1", "client-1"), venue="BINANCE_SPOT", account_scope="test-account")
    prepared = _prepare(store, "intent-1", "client-1")
    handed_off = _handoff(store, "intent-1", prepared["current_version"])

    with pytest.raises(ValueError):
        _prepare(store, "intent-1", "client-1", handed_off["current_version"])


@pytest.mark.parametrize(
    "mismatch",
    [
        {"venue": "OTHER_VENUE"},
        {"account_scope": "other-account"},
        {"client_order_id": "other-client"},
    ],
)
def test_submission_preparation_rejects_identity_mismatch(
    store_and_connection, mismatch
):
    store, _ = store_and_connection
    store.create_intent(
        _intent("intent-mismatch", "client-1"),
        venue="BINANCE_SPOT",
        account_scope="test-account",
    )
    preparation = {
        "intent_id": "intent-mismatch",
        "attempt_id": "attempt-intent-mismatch",
        "attempt_sequence": 1,
        "venue": "BINANCE_SPOT",
        "account_scope": "test-account",
        "client_order_id": "client-1",
        "expected_version": 0,
    }
    preparation.update(mismatch)
    with pytest.raises(ValueError, match="identity does not match"):
        store.record_submission_preparation(**preparation)

    prepared = _prepare(store, "intent-mismatch", "client-1")
    assert prepared["submission_lifecycle_state"] == "SUBMISSION_ATTEMPTED"


def test_namespace_conflict_and_same_symbol_multiple_intents(store_and_connection):
    store, _ = store_and_connection
    store.create_intent(_intent("intent-1", "client-1"), venue="BINANCE_SPOT", account_scope="test-account")
    with pytest.raises(UniqueConflict):
        store.create_intent(_intent("intent-2", "client-1", "ETHUSDC"), venue="BINANCE_SPOT", account_scope="test-account")

    store.create_intent(_intent("intent-3", "client-3"), venue="BINANCE_SPOT", account_scope="test-account")
    assert store.find_by_client_namespace(
        venue="BINANCE_SPOT", account_scope="test-account", client_order_id="client-3"
    )["intent_id"] == "intent-3"


def test_version_conflict_has_no_automatic_retry(store_and_connection):
    store, _ = store_and_connection
    store.create_intent(_intent("intent-1", "client-1"), venue="BINANCE_SPOT", account_scope="test-account")
    with pytest.raises(VersionConflict):
        _prepare(store, "intent-1", "client-1", expected_version=99)

    prepared = _prepare(store, "intent-1", "client-1", expected_version=0)
    assert prepared["current_version"] == 1


def test_atomic_observation_and_contradictory_evidence(store_and_connection):
    store, connection = store_and_connection
    store.create_intent(_intent("intent-1", "client-1"), venue="BINANCE_SPOT", account_scope="test-account")
    prepared = _prepare(store, "intent-1", "client-1")
    handed_off = _handoff(store, "intent-1", prepared["current_version"])
    effect = _effect("trade-1", "evidence-1")
    _observation(store, "intent-1", "evidence-1", "order-1", handed_off["current_version"], [effect])

    with pytest.raises(UniqueConflict):
        _observation(store, "intent-1", "evidence-2", "order-1", handed_off["current_version"] + 1, [
            {**effect, "exchange_trade_id": "trade-2", "evidence_id": "evidence-2"},
            {**effect, "evidence_id": "evidence-2"},
        ])

    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM handa_live.exchange_evidence")
        assert cursor.fetchone() == (1,)
        cursor.execute("SELECT COUNT(*) FROM handa_live.trade_effect")
        assert cursor.fetchone() == (1,)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.exchange_evidence
            (evidence_id, intent_id, evidence_sequence, symbol, raw_snapshot, observed_at)
            VALUES ('evidence-3', 'intent-1', 2, 'BTCUSDC', %s, CURRENT_TIMESTAMP)
            """,
            ("{}",),
        )
    connection.commit()
    page = store.enumerate_evidence(intent_id="intent-1", limit=10)
    assert [row["evidence_id"] for row in page.rows] == ["evidence-1", "evidence-3"]


def test_recovery_queries_and_exact_decimal(store_and_connection):
    store, connection = store_and_connection
    for number in range(3):
        intent_id = f"intent-{number}"
        client_id = f"client-{number}"
        store.create_intent(_intent(intent_id, client_id), venue="BINANCE_SPOT", account_scope="test-account")
        prepared = _prepare(store, intent_id, client_id)
        _handoff(store, intent_id, prepared["current_version"])

    page = store.find_unresolved(limit=2)
    assert len(page.rows) == 2
    assert page.next_cursor is not None
    second_page = store.find_unresolved(limit=2, cursor=page.next_cursor)
    assert len(second_page.rows) == 1
    by_symbol = store.find_unresolved_by_symbol(symbol="BTCUSDC", limit=10)
    assert len(by_symbol.rows) == 3

    store, connection = store, connection
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT requested_quote_amount FROM handa_live.order_intent WHERE intent_id = 'intent-0'"
        )
        assert cursor.fetchone()[0] == Decimal("10.00000000")


def test_reconciliation_is_persisted_but_not_derived(store_and_connection):
    store, _ = store_and_connection
    created = store.create_intent(_intent("intent-1", "client-1"), venue="BINANCE_SPOT", account_scope="test-account")
    prepared = _prepare(store, "intent-1", "client-1")
    handed_off = _handoff(store, "intent-1", prepared["current_version"])
    with pytest.raises(InvalidCapabilityRequest):
        store.append_reconciliation_decision(
            reconciliation_id="recon-bad",
            intent_id="intent-1",
            decision_sequence=1,
            reconciliation_state="PENDING",
            execution_certainty="NO_EFFECT_CONFIRMED",
            expected_version=handed_off["current_version"],
        )
    with pytest.raises(InvalidCapabilityRequest):
        store.append_reconciliation_decision(
            reconciliation_id="recon-execution-pending",
            intent_id="intent-1",
            decision_sequence=1,
            reconciliation_state="PENDING",
            execution_certainty="EXECUTION_CONFIRMED",
            expected_version=handed_off["current_version"],
        )

    resolved = store.append_reconciliation_decision(
        reconciliation_id="recon-1",
        intent_id="intent-1",
        decision_sequence=1,
        reconciliation_state="RESOLVED",
        execution_certainty="NO_EFFECT_CONFIRMED",
        expected_version=handed_off["current_version"],
        decision_reason="test authority decision",
    )
    assert resolved["execution_certainty"] == "NO_EFFECT_CONFIRMED"
    assert created["intent_id"] == "intent-1"


def test_exchange_correlation_query(store_and_connection):
    store, _ = store_and_connection
    store.create_intent(_intent("intent-1", "client-1"), venue="BINANCE_SPOT", account_scope="test-account")
    prepared = _prepare(store, "intent-1", "client-1")
    handed_off = _handoff(store, "intent-1", prepared["current_version"])
    _observation(store, "intent-1", "evidence-1", "order-1", handed_off["current_version"])
    page = store.find_by_exchange_correlation(symbol="BTCUSDC", exchange_order_id="order-1")
    assert [row["intent_id"] for row in page.rows] == ["intent-1"]
