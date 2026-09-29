import os
import json
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest


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
MIGRATION_003 = (
    Path(__file__).parents[2]
    / "core"
    / "persistence"
    / "migrations"
    / "003_reconciliation_evidence.sql"
)
MIGRATION_004 = (
    Path(__file__).parents[2]
    / "core"
    / "persistence"
    / "migrations"
    / "004_external_order_observation_contract.sql"
)
MIGRATION_005 = (
    Path(__file__).parents[2]
    / "core"
    / "persistence"
    / "migrations"
    / "005_decision_ledger.sql"
)


def _connect_test_database():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("TEST_DATABASE_URL is required; refusing schema test.")

    parsed = urlparse(database_url)
    if (
        parsed.hostname not in EXPECTED_HOSTS
        or parsed.port != EXPECTED_PORT
        or parsed.path.lstrip("/") != EXPECTED_DATABASE
        or parsed.username != EXPECTED_USER
    ):
        pytest.fail("TEST_DATABASE_URL does not identify the governed local test database.")

    connection = psycopg2.connect(database_url)
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user")
        assert cursor.fetchone() == (EXPECTED_DATABASE, EXPECTED_USER)
    return connection


@pytest.fixture()
def schema_connection():
    connection = _connect_test_database()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            cursor.execute(MIGRATION.read_text(encoding="utf-8"))
        connection.commit()
        yield connection
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
        connection.commit()
        connection.close()


@pytest.fixture()
def schema_v2_connection():
    connection = _connect_test_database()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            cursor.execute(MIGRATION.read_text(encoding="utf-8"))
            cursor.execute(MIGRATION_002.read_text(encoding="utf-8"))
            if MIGRATION_003.exists():
                cursor.execute(MIGRATION_003.read_text(encoding="utf-8"))
            cursor.execute(MIGRATION_004.read_text(encoding="utf-8"))
            cursor.execute(MIGRATION_005.read_text(encoding="utf-8"))
        connection.commit()
        yield connection
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
        connection.commit()
        connection.close()


def _insert_intent(connection, intent_id, client_order_id, symbol="BTCUSDC", **overrides):
    values = {
        "intent_id": intent_id,
        "venue": "BINANCE_SPOT",
        "account_scope": "test-account",
        "client_order_id": client_order_id,
        "slot_id": "slot-1",
        "symbol": symbol,
        "side": "BUY",
        "requested_quote_amount": Decimal("10.00000000"),
        "submission_lifecycle_state": "READY_TO_SUBMIT",
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join(["%s"] * len(values))
    with connection.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO handa_live.order_intent ({columns}) VALUES ({placeholders})",
            tuple(values.values()),
        )


def test_schema_creates_all_resources_and_has_no_credential_columns(schema_connection):
    with schema_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'handa_live'
            ORDER BY table_name
            """
        )
        assert [row[0] for row in cursor.fetchall()] == [
            "exchange_evidence",
            "normalized_evidence",
            "order_intent",
            "reconciliation",
            "submission_attempt",
            "trade_effect",
        ]
        cursor.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'handa_live'
            AND column_name ILIKE '%credential%'
               OR table_schema = 'handa_live' AND column_name ILIKE '%secret%'
            """
        )
        assert cursor.fetchall() == []


def test_namespace_and_exchange_order_identity_boundaries(schema_connection):
    _insert_intent(schema_connection, "i-1", "client-1", symbol="BTCUSDC")
    with pytest.raises(psycopg2.errors.UniqueViolation):
        _insert_intent(schema_connection, "i-2", "client-1", symbol="ETHUSDC")
    schema_connection.rollback()

    _insert_intent(schema_connection, "i-1", "client-1", symbol="BTCUSDC")
    _insert_intent(schema_connection, "i-2", "client-2", symbol="ETHUSDC")
    _insert_intent(schema_connection, "i-3", "client-3", symbol="BTCUSDC")
    with schema_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.submission_attempt
            (attempt_id, intent_id, attempt_sequence, venue, account_scope,
             client_order_id, submission_lifecycle_state)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            ("a-1", "i-1", 1, "BINANCE_SPOT", "test-account", "client-1", "SUBMISSION_ATTEMPTED"),
        )
        cursor.execute(
            """
            INSERT INTO handa_live.submission_attempt
            (attempt_id, intent_id, attempt_sequence, venue, account_scope,
             client_order_id, submission_lifecycle_state)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            ("a-2", "i-2", 1, "BINANCE_SPOT", "test-account", "client-2", "SUBMISSION_ATTEMPTED"),
        )
        cursor.execute(
            """
            INSERT INTO handa_live.exchange_evidence
            (evidence_id, intent_id, attempt_id, evidence_sequence, symbol,
             exchange_order_id, raw_snapshot, observed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """,
            ("e-1", "i-1", "a-1", 1, "BTCUSDC", "same-order", "{}"),
        )
        cursor.execute(
            """
            INSERT INTO handa_live.exchange_evidence
            (evidence_id, intent_id, attempt_id, evidence_sequence, symbol,
             exchange_order_id, raw_snapshot, observed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """,
            ("e-2", "i-2", "a-2", 1, "ETHUSDC", "same-order", "{}"),
        )
    schema_connection.commit()


def test_composite_lineage_and_revision_sequences(schema_connection):
    _insert_intent(schema_connection, "i-1", "client-1")
    _insert_intent(schema_connection, "i-2", "client-2", symbol="ETHUSDC")
    with schema_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.submission_attempt
            (attempt_id, intent_id, attempt_sequence, venue, account_scope,
             client_order_id, submission_lifecycle_state)
            VALUES ('a-1', 'i-1', 1, 'BINANCE_SPOT', 'test-account', 'client-1', 'SUBMISSION_ATTEMPTED')
            """
        )
        cursor.execute(
            """
            INSERT INTO handa_live.exchange_evidence
            (evidence_id, intent_id, attempt_id, evidence_sequence, symbol,
             exchange_order_id, raw_snapshot, observed_at)
            VALUES ('e-1', 'i-1', 'a-1', 1, 'BTCUSDC', 'order-1', '{}', CURRENT_TIMESTAMP)
            """
        )
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            cursor.execute(
                """
                INSERT INTO handa_live.trade_effect
                (symbol, exchange_order_id, exchange_trade_id, evidence_id, intent_id,
                 price, gross_base_qty, quote_qty, commission_amount, commission_asset)
                VALUES ('BTCUSDC', 'order-1', 'trade-1', 'e-1', 'i-2',
                        100, 1, 100, 0, 'USDC')
                """
            )
    schema_connection.rollback()

    _insert_intent(schema_connection, "i-1", "client-1")
    with schema_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.submission_attempt
            (attempt_id, intent_id, attempt_sequence, venue, account_scope,
             client_order_id, submission_lifecycle_state)
            VALUES ('a-1', 'i-1', 1, 'BINANCE_SPOT', 'test-account', 'client-1', 'SUBMISSION_ATTEMPTED')
            """
        )
        cursor.execute(
            """
            INSERT INTO handa_live.exchange_evidence
            (evidence_id, intent_id, attempt_id, evidence_sequence, symbol,
             exchange_order_id, raw_snapshot, observed_at)
            VALUES ('e-1', 'i-1', 'a-1', 1, 'BTCUSDC', 'order-1', '{}', CURRENT_TIMESTAMP)
            """
        )
        with pytest.raises(psycopg2.errors.CheckViolation):
            cursor.execute(
                """
                INSERT INTO handa_live.normalized_evidence
                (normalized_revision_id, evidence_id, intent_id, revision_sequence,
                 normalized_status, provenance, normalized_payload)
                VALUES ('n-0', 'e-1', 'i-1', 0, 'UNKNOWN', '{}', '{}')
                """
            )
    schema_connection.rollback()
    _insert_intent(schema_connection, "i-1", "client-1")
    with schema_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.submission_attempt
            (attempt_id, intent_id, attempt_sequence, venue, account_scope,
             client_order_id, submission_lifecycle_state)
            VALUES ('a-1', 'i-1', 1, 'BINANCE_SPOT', 'test-account', 'client-1', 'SUBMISSION_ATTEMPTED')
            """
        )
        with pytest.raises(psycopg2.errors.CheckViolation):
            cursor.execute(
                """
                INSERT INTO handa_live.reconciliation
                (reconciliation_id, intent_id, decision_sequence,
                 reconciliation_state, execution_certainty)
                VALUES ('r-0', 'i-1', 0, 'PENDING', 'UNKNOWN')
                """
            )


def test_trade_effect_identity_and_lineage_constraints(schema_connection):
    _insert_intent(schema_connection, "i-1", "client-1")
    with schema_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.submission_attempt
            (attempt_id, intent_id, attempt_sequence, venue, account_scope,
             client_order_id, submission_lifecycle_state)
            VALUES ('a-1', 'i-1', 1, 'BINANCE_SPOT', 'test-account', 'client-1', 'SUBMISSION_ATTEMPTED')
            """
        )
        cursor.execute(
            """
            INSERT INTO handa_live.exchange_evidence
            (evidence_id, intent_id, attempt_id, evidence_sequence, symbol,
             exchange_order_id, raw_snapshot, observed_at)
            VALUES ('e-1', 'i-1', 'a-1', 1, 'BTCUSDC', 'order-1', '{}', CURRENT_TIMESTAMP)
            """
        )
        effect = (
            "BTCUSDC", "order-1", "trade-1", "e-1", "i-1",
            Decimal("100.12000000"), Decimal("0.01000000"),
            Decimal("1.001200000000"), Decimal("0.00010000"), "USDC",
        )
        cursor.execute(
            """
            INSERT INTO handa_live.trade_effect
            (symbol, exchange_order_id, exchange_trade_id, evidence_id, intent_id,
             price, gross_base_qty, quote_qty, commission_amount, commission_asset)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            effect,
        )
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cursor.execute(
                """
                INSERT INTO handa_live.trade_effect
                (symbol, exchange_order_id, exchange_trade_id, evidence_id, intent_id,
                 price, gross_base_qty, quote_qty, commission_amount, commission_asset)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                effect,
            )
    schema_connection.rollback()
    _insert_intent(schema_connection, "i-1", "client-1")
    with schema_connection.cursor() as cursor:
        cursor.execute(
            "SELECT price, gross_base_qty, quote_qty, commission_amount FROM handa_live.trade_effect"
        )
        assert cursor.fetchone() is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"side": "BUY", "requested_quote_amount": Decimal("1"), "requested_base_qty": Decimal("1")},
        {"side": "SELL", "requested_quote_amount": Decimal("1"), "requested_base_qty": None},
        {"side": "BUY", "requested_quote_amount": Decimal("0"), "requested_base_qty": None},
    ],
)
def test_invalid_sizing_is_rejected(schema_connection, overrides):
    with pytest.raises(psycopg2.errors.CheckViolation):
        _insert_intent(schema_connection, "invalid", "client-invalid", **overrides)
    schema_connection.rollback()


def test_execution_certainty_boundary_constraints(schema_connection):
    def attempt(intent_id, client_order_id, **overrides):
        try:
            _insert_intent(
                schema_connection,
                intent_id,
                client_order_id,
                **overrides,
            )
        except psycopg2.errors.CheckViolation:
            schema_connection.rollback()
            return False
        schema_connection.rollback()
        return True

    assert attempt(
        "pre-handoff-null", "client-pre-handoff-null",
        execution_certainty=None,
        reconciliation_state=None,
    )
    assert not attempt(
        "unknown-null", "client-unknown-null",
        submission_lifecycle_state="SUBMISSION_ATTEMPTED",
        execution_certainty="UNKNOWN",
        reconciliation_state=None,
    )
    assert attempt(
        "unknown-pending", "client-unknown-pending",
        submission_lifecycle_state="SUBMISSION_ATTEMPTED",
        execution_certainty="UNKNOWN",
        reconciliation_state="PENDING",
    )
    assert attempt(
        "unknown-blocked", "client-unknown-blocked",
        submission_lifecycle_state="SUBMISSION_ATTEMPTED",
        execution_certainty="UNKNOWN",
        reconciliation_state="BLOCKED",
    )
    assert not attempt(
        "unknown-resolved", "client-unknown-resolved",
        submission_lifecycle_state="SUBMISSION_ATTEMPTED",
        execution_certainty="UNKNOWN",
        reconciliation_state="RESOLVED",
    )
    assert not attempt(
        "may-have-null", "client-may-have-null",
        submission_lifecycle_state="MAY_HAVE_BEEN_SUBMITTED",
        execution_certainty=None,
        reconciliation_state="PENDING",
    )
    assert attempt(
        "may-have-unknown", "client-may-have-unknown",
        submission_lifecycle_state="MAY_HAVE_BEEN_SUBMITTED",
        execution_certainty="UNKNOWN",
        reconciliation_state="PENDING",
    )
    assert not attempt(
        "ready-unknown", "client-ready-unknown",
        submission_lifecycle_state="READY_TO_SUBMIT",
        execution_certainty="UNKNOWN",
        reconciliation_state="PENDING",
    )
    assert not attempt(
        "no-effect-null", "client-no-effect-null",
        submission_lifecycle_state="SUBMISSION_ATTEMPTED",
        execution_certainty="NO_EFFECT_CONFIRMED",
        reconciliation_state=None,
    )

    _insert_intent(
        schema_connection,
        "unknown-query",
        "client-unknown-query",
        submission_lifecycle_state="MAY_HAVE_BEEN_SUBMITTED",
        execution_certainty="UNKNOWN",
        reconciliation_state="BLOCKED",
    )
    with schema_connection.cursor() as cursor:
        cursor.execute(
            "SELECT intent_id FROM handa_live.order_intent WHERE execution_certainty = 'UNKNOWN' AND symbol = %s",
            ("BTCUSDC",),
        )
        assert cursor.fetchone() == ("unknown-query",)


def test_migration_002_allows_terminal_reconciliation_without_clearing_handoff(
    schema_v2_connection,
):
    connection = schema_v2_connection

    def attempt(intent_id, client_order_id, **overrides):
        try:
            _insert_intent(connection, intent_id, client_order_id, **overrides)
        except psycopg2.errors.CheckViolation:
            connection.rollback()
            return False
        connection.rollback()
        return True

    assert attempt(
        "may-terminal-no-effect",
        "client-may-terminal-no-effect",
        submission_lifecycle_state="MAY_HAVE_BEEN_SUBMITTED",
        execution_certainty="NO_EFFECT_CONFIRMED",
        reconciliation_state="RESOLVED",
    )
    assert attempt(
        "may-terminal-execution",
        "client-may-terminal-execution",
        submission_lifecycle_state="MAY_HAVE_BEEN_SUBMITTED",
        execution_certainty="EXECUTION_CONFIRMED",
        reconciliation_state="RESOLVED",
    )
    assert not attempt(
        "may-null",
        "client-may-null",
        submission_lifecycle_state="MAY_HAVE_BEEN_SUBMITTED",
        execution_certainty=None,
        reconciliation_state="PENDING",
    )
    assert not attempt(
        "unknown-null",
        "client-unknown-null",
        submission_lifecycle_state="MAY_HAVE_BEEN_SUBMITTED",
        execution_certainty="UNKNOWN",
        reconciliation_state=None,
    )
    assert not attempt(
        "unknown-resolved",
        "client-unknown-resolved",
        submission_lifecycle_state="MAY_HAVE_BEEN_SUBMITTED",
        execution_certainty="UNKNOWN",
        reconciliation_state="RESOLVED",
    )
    assert not attempt(
        "terminal-pending",
        "client-terminal-pending",
        submission_lifecycle_state="MAY_HAVE_BEEN_SUBMITTED",
        execution_certainty="EXECUTION_CONFIRMED",
        reconciliation_state="PENDING",
    )
    assert not attempt(
        "terminal-blocked",
        "client-terminal-blocked",
        submission_lifecycle_state="MAY_HAVE_BEEN_SUBMITTED",
        execution_certainty="NO_EFFECT_CONFIRMED",
        reconciliation_state="BLOCKED",
    )
    assert not attempt(
        "ready-unknown",
        "client-ready-unknown",
        submission_lifecycle_state="READY_TO_SUBMIT",
        execution_certainty="UNKNOWN",
        reconciliation_state="PENDING",
    )
    assert attempt(
        "attempted-null",
        "client-attempted-null",
        submission_lifecycle_state="SUBMISSION_ATTEMPTED",
        execution_certainty=None,
        reconciliation_state=None,
    )

    for certainty in ("NO_EFFECT_CONFIRMED", "EXECUTION_CONFIRMED"):
        for reconciliation_state in (None, "PENDING", "BLOCKED", "RESOLVED"):
            suffix = f"{certainty.lower()}-{reconciliation_state or 'null'}"
            assert attempt(
                f"terminal-matrix-{suffix}",
                f"client-terminal-matrix-{suffix}",
                submission_lifecycle_state="MAY_HAVE_BEEN_SUBMITTED",
                execution_certainty=certainty,
                reconciliation_state=reconciliation_state,
            ) is (reconciliation_state == "RESOLVED")

    _insert_intent(
        connection,
        "unresolved",
        "client-unresolved",
        submission_lifecycle_state="MAY_HAVE_BEEN_SUBMITTED",
        execution_certainty="UNKNOWN",
        reconciliation_state="BLOCKED",
    )
    _insert_intent(
        connection,
        "resolved",
        "client-resolved",
        symbol="ETHUSDC",
        submission_lifecycle_state="MAY_HAVE_BEEN_SUBMITTED",
        execution_certainty="EXECUTION_CONFIRMED",
        reconciliation_state="RESOLVED",
    )
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT intent_id FROM handa_live.order_intent
            WHERE execution_certainty = 'UNKNOWN'
              AND reconciliation_state IN ('PENDING', 'BLOCKED')
            ORDER BY intent_id
            """
        )
        assert [row[0] for row in cursor.fetchall()] == ["unresolved"]


def test_migration_002_preserves_identity_and_decimal_contract(schema_v2_connection):
    connection = schema_v2_connection
    value = Decimal("10.00000000")
    _insert_intent(connection, "i-1", "client-1", requested_quote_amount=value)
    _insert_intent(connection, "i-2", "client-2", symbol="BTCUSDC")
    connection.commit()
    with pytest.raises(psycopg2.errors.UniqueViolation):
        _insert_intent(connection, "i-3", "client-1", symbol="ETHUSDC")
    connection.rollback()

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT requested_quote_amount FROM handa_live.order_intent WHERE intent_id = 'i-1'"
        )
        assert cursor.fetchone()[0] == value
        cursor.execute(
            """
            SELECT indexdef FROM pg_indexes
            WHERE schemaname = 'handa_live'
              AND indexname = 'order_intent_unresolved_symbol_idx'
            """
        )
        assert "(symbol, intent_id)" in cursor.fetchone()[0]


def test_exact_decimal_round_trip_and_numeric_rejection(schema_connection):
    value = Decimal("0.00123000")
    _insert_intent(
        schema_connection,
        "decimal",
        "client-decimal",
        requested_quote_amount=value,
    )
    with schema_connection.cursor() as cursor:
        cursor.execute(
            "SELECT requested_quote_amount FROM handa_live.order_intent WHERE intent_id = 'decimal'"
        )
        assert cursor.fetchone()[0] == value
        with pytest.raises(psycopg2.errors.CheckViolation):
            cursor.execute(
                "UPDATE handa_live.order_intent SET requested_quote_amount = -1 WHERE intent_id = 'decimal'"
            )


def test_sequence_constraints_and_rollback(schema_connection):
    _insert_intent(schema_connection, "i-1", "client-1")
    with pytest.raises(psycopg2.errors.CheckViolation):
        with schema_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO handa_live.submission_attempt
                (attempt_id, intent_id, attempt_sequence, venue, account_scope,
                 client_order_id, submission_lifecycle_state)
                VALUES ('a-1', 'i-1', 0, 'BINANCE_SPOT', 'test-account', 'client-1', 'SUBMISSION_ATTEMPTED')
                """
            )
    schema_connection.rollback()
    with schema_connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM handa_live.submission_attempt")
        assert cursor.fetchone() == (0,)


def _insert_lineage_fixture(connection, *, include_second_intent=False, second_revision=False):
    _insert_intent(
        connection,
        "i-1",
        "client-1",
        submission_lifecycle_state="MAY_HAVE_BEEN_SUBMITTED",
        execution_certainty="UNKNOWN",
        reconciliation_state="PENDING",
    )
    if include_second_intent:
        _insert_intent(
            connection,
            "i-2",
            "client-2",
            symbol="ETHUSDC",
            submission_lifecycle_state="MAY_HAVE_BEEN_SUBMITTED",
            execution_certainty="UNKNOWN",
            reconciliation_state="PENDING",
        )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.submission_attempt
            (attempt_id, intent_id, attempt_sequence, venue, account_scope,
             client_order_id, submission_lifecycle_state)
            VALUES
              ('a-1', 'i-1', 1, 'BINANCE_SPOT', 'test-account', 'client-1', 'MAY_HAVE_BEEN_SUBMITTED')
            """
        )
        cursor.execute(
            """
            INSERT INTO handa_live.exchange_evidence
            (evidence_id, intent_id, attempt_id, evidence_sequence, symbol,
             exchange_order_id, raw_snapshot, observed_at)
            VALUES ('e-1', 'i-1', 'a-1', 1, 'BTCUSDC', 'order-1', '{}', CURRENT_TIMESTAMP)
            """
        )
        cursor.execute(
            """
            INSERT INTO handa_live.normalized_evidence
            (normalized_revision_id, evidence_id, intent_id, revision_sequence,
             normalized_status, provenance, normalized_payload)
            VALUES ('n-1', 'e-1', 'i-1', 1, 'UNKNOWN', '{}', '{}')
            """
        )

        if second_revision:
            cursor.execute(
                """
                INSERT INTO handa_live.submission_attempt
                (attempt_id, intent_id, attempt_sequence, venue, account_scope,
                 client_order_id, submission_lifecycle_state)
                VALUES
                  ('a-1b', 'i-1', 2, 'BINANCE_SPOT', 'test-account', 'client-1', 'MAY_HAVE_BEEN_SUBMITTED')
                """
            )
            cursor.execute(
                """
                INSERT INTO handa_live.exchange_evidence
                (evidence_id, intent_id, attempt_id, evidence_sequence, symbol,
                 exchange_order_id, raw_snapshot, observed_at)
                VALUES ('e-1b', 'i-1', 'a-1b', 2, 'BTCUSDC', 'order-1', '{}', CURRENT_TIMESTAMP)
                """
            )
            cursor.execute(
                """
                INSERT INTO handa_live.normalized_evidence
                (normalized_revision_id, evidence_id, intent_id, revision_sequence,
                 normalized_status, provenance, normalized_payload)
                VALUES ('n-1b', 'e-1b', 'i-1', 1, 'UNKNOWN', '{}', '{}')
                """
            )

        if include_second_intent:
            cursor.execute(
                """
                INSERT INTO handa_live.submission_attempt
                (attempt_id, intent_id, attempt_sequence, venue, account_scope,
                 client_order_id, submission_lifecycle_state)
                VALUES
                  ('a-2', 'i-2', 1, 'BINANCE_SPOT', 'test-account', 'client-2', 'MAY_HAVE_BEEN_SUBMITTED')
                """
            )
            cursor.execute(
                """
                INSERT INTO handa_live.exchange_evidence
                (evidence_id, intent_id, attempt_id, evidence_sequence, symbol,
                 exchange_order_id, raw_snapshot, observed_at)
                VALUES ('e-2', 'i-2', 'a-2', 1, 'ETHUSDC', 'order-2', '{}', CURRENT_TIMESTAMP)
                """
            )
            cursor.execute(
                """
                INSERT INTO handa_live.normalized_evidence
                (normalized_revision_id, evidence_id, intent_id, revision_sequence,
                 normalized_status, provenance, normalized_payload)
                VALUES ('n-2', 'e-2', 'i-2', 1, 'UNKNOWN', '{}', '{}')
                """
            )

        cursor.execute(
            """
            INSERT INTO handa_live.reconciliation
            (reconciliation_id, intent_id, decision_sequence,
             reconciliation_state, execution_certainty)
            VALUES ('r-1', 'i-1', 1, 'PENDING', 'UNKNOWN')
            """
        )


def _insert_reconciliation_evidence(connection, reconciliation_id, intent_id, normalized_revision_id):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.reconciliation_evidence
            (reconciliation_id, intent_id, normalized_revision_id)
            VALUES (%s, %s, %s)
            """,
            (reconciliation_id, intent_id, normalized_revision_id),
        )


def test_migration_003_relation_shape_and_history_is_additive(schema_v2_connection):
    connection = schema_v2_connection
    _insert_lineage_fixture(connection)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'handa_live'
              AND table_name = 'reconciliation_evidence'
            ORDER BY ordinal_position
            """
        )
        assert [row[0] for row in cursor.fetchall()] == [
            "reconciliation_id",
            "intent_id",
            "normalized_revision_id",
        ]
        cursor.execute(
            "SELECT COUNT(*) FROM handa_live.reconciliation_evidence"
        )
        assert cursor.fetchone() == (0,)


def test_reconciliation_evidence_rejects_unknown_reconciliation(schema_v2_connection):
    connection = schema_v2_connection
    _insert_lineage_fixture(connection)
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        _insert_reconciliation_evidence(connection, "missing", "i-1", "n-1")


def test_reconciliation_evidence_rejects_unknown_normalized_revision(schema_v2_connection):
    connection = schema_v2_connection
    _insert_lineage_fixture(connection)
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        _insert_reconciliation_evidence(connection, "r-1", "i-1", "missing")


def test_reconciliation_evidence_rejects_cross_intent_association(schema_v2_connection):
    connection = schema_v2_connection
    _insert_lineage_fixture(connection, include_second_intent=True)
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        _insert_reconciliation_evidence(connection, "r-1", "i-1", "n-2")


def test_reconciliation_evidence_rejects_duplicate_association(schema_v2_connection):
    connection = schema_v2_connection
    _insert_lineage_fixture(connection)
    _insert_reconciliation_evidence(connection, "r-1", "i-1", "n-1")
    with pytest.raises(psycopg2.errors.UniqueViolation):
        _insert_reconciliation_evidence(connection, "r-1", "i-1", "n-1")


def test_one_reconciliation_references_multiple_revisions(schema_v2_connection):
    connection = schema_v2_connection
    _insert_lineage_fixture(connection, second_revision=True)
    _insert_reconciliation_evidence(connection, "r-1", "i-1", "n-1")
    _insert_reconciliation_evidence(connection, "r-1", "i-1", "n-1b")
    connection.commit()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT normalized_revision_id
            FROM handa_live.reconciliation_evidence
            WHERE reconciliation_id = 'r-1'
            ORDER BY normalized_revision_id
            """
        )
        assert [row[0] for row in cursor.fetchall()] == ["n-1", "n-1b"]


def test_one_revision_supports_multiple_reconciliation_decisions(schema_v2_connection):
    connection = schema_v2_connection
    _insert_lineage_fixture(connection)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.reconciliation
            (reconciliation_id, intent_id, decision_sequence,
             reconciliation_state, execution_certainty)
            VALUES ('r-2', 'i-1', 2, 'BLOCKED', 'UNKNOWN')
            """
        )
    _insert_reconciliation_evidence(connection, "r-1", "i-1", "n-1")
    _insert_reconciliation_evidence(connection, "r-2", "i-1", "n-1")
    connection.commit()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT reconciliation_id
            FROM handa_live.reconciliation_evidence
            WHERE normalized_revision_id = 'n-1'
            ORDER BY reconciliation_id
            """
        )
        assert [row[0] for row in cursor.fetchall()] == ["r-1", "r-2"]


def test_migrations_001_and_002_do_not_contain_lineage_relation():
    assert "reconciliation_evidence" not in MIGRATION.read_text(encoding="utf-8")
    assert "reconciliation_evidence" not in MIGRATION_002.read_text(encoding="utf-8")


MIGRATION_004_COLUMNS = (
    "client_order_id_observed",
    "order_type",
    "time_in_force",
    "orig_qty",
    "orig_quote_order_qty",
    "executed_qty",
    "cumulative_quote_qty",
    "observation_class",
    "observation_source",
)

OBSERVATION_CLASSES = (
    "ORDER_STATE",
    "EXECUTION_EVENT",
    "TRADE_RECORD",
)

OBSERVATION_SOURCES = (
    "BINANCE_SPOT_ORDER_RESPONSE",
    "BINANCE_SPOT_ORDER_QUERY",
    "BINANCE_SPOT_EXECUTION_REPORT",
    "BINANCE_SPOT_TRADE_QUERY",
)


def _assert_migration_004_columns(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'handa_live'
              AND table_name = 'exchange_evidence'
              AND column_name = ANY(%s)
            ORDER BY ordinal_position
            """,
            (list(MIGRATION_004_COLUMNS),),
        )
        assert [row[0] for row in cursor.fetchall()] == list(MIGRATION_004_COLUMNS)


def _insert_future_observation(connection, evidence_id, evidence_sequence, **overrides):
    values = {
        "evidence_id": evidence_id,
        "intent_id": "i-1",
        "evidence_sequence": evidence_sequence,
        "symbol": "BTCUSDC",
        "exchange_order_id": "order-1",
        "raw_snapshot": '{"status":"FILLED"}',
        "observed_at": "CURRENT_TIMESTAMP",
        "observation_class": "ORDER_STATE",
        "observation_source": "BINANCE_SPOT_ORDER_QUERY",
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join(
        "CURRENT_TIMESTAMP" if value == "CURRENT_TIMESTAMP" else "%s"
        for value in values.values()
    )
    parameters = tuple(
        value for value in values.values() if value != "CURRENT_TIMESTAMP"
    )
    with connection.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO handa_live.exchange_evidence ({columns}) VALUES ({placeholders})",
            parameters,
        )


def test_migration_004_columns_are_present(schema_v2_connection):
    _assert_migration_004_columns(schema_v2_connection)


def test_historical_rows_remain_valid_with_new_columns_null(schema_v2_connection):
    connection = schema_v2_connection
    _assert_migration_004_columns(connection)
    _insert_intent(connection, "i-1", "client-1")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.exchange_evidence
            (evidence_id, intent_id, evidence_sequence, symbol,
             raw_snapshot, observed_at)
            VALUES ('e-1', 'i-1', 1, 'BTCUSDC', '{}', CURRENT_TIMESTAMP)
            """
        )
        cursor.execute(
            """
            SELECT client_order_id_observed, order_type, time_in_force,
                   orig_qty, orig_quote_order_qty, executed_qty,
                   cumulative_quote_qty, observation_class, observation_source
            FROM handa_live.exchange_evidence
            WHERE evidence_id = 'e-1'
            """
        )
        assert cursor.fetchone() == (None,) * 9


def test_minimal_structured_observation_allows_optional_identifiers_absent(
    schema_v2_connection,
):
    connection = schema_v2_connection
    _assert_migration_004_columns(connection)
    _insert_intent(connection, "i-1", "client-1")
    _insert_future_observation(
        connection,
        "e-1",
        1,
        exchange_order_id=None,
        observation_class="ORDER_STATE",
        observation_source="BINANCE_SPOT_ORDER_RESPONSE",
    )


@pytest.mark.parametrize(
    "field",
    ["orig_qty", "orig_quote_order_qty", "executed_qty"],
)
def test_structured_quantities_reject_negative_values(schema_v2_connection, field):
    connection = schema_v2_connection
    _assert_migration_004_columns(connection)
    _insert_intent(connection, "i-1", "client-1")
    with pytest.raises(psycopg2.errors.CheckViolation):
        _insert_future_observation(connection, "e-1", 1, **{field: Decimal("-1")})


def test_structured_quantities_accept_non_negative_values(schema_v2_connection):
    connection = schema_v2_connection
    _assert_migration_004_columns(connection)
    _insert_intent(connection, "i-1", "client-1")
    _insert_future_observation(
        connection,
        "e-1",
        1,
        orig_qty=Decimal("0"),
        orig_quote_order_qty=Decimal("10"),
        executed_qty=Decimal("0.1"),
        cumulative_quote_qty=Decimal("10.01"),
    )


def test_observation_class_uses_only_frozen_vocabulary(schema_v2_connection):
    connection = schema_v2_connection
    _assert_migration_004_columns(connection)
    _insert_intent(connection, "i-1", "client-1")
    for sequence, value in enumerate(OBSERVATION_CLASSES, start=1):
        _insert_future_observation(connection, f"e-{sequence}", sequence, observation_class=value)
    with pytest.raises(psycopg2.errors.CheckViolation):
        _insert_future_observation(connection, "e-invalid", 4, observation_class="OTHER")


def test_observation_source_uses_only_frozen_candidate_vocabulary(schema_v2_connection):
    connection = schema_v2_connection
    _assert_migration_004_columns(connection)
    _insert_intent(connection, "i-1", "client-1")
    for sequence, value in enumerate(OBSERVATION_SOURCES, start=1):
        _insert_future_observation(connection, f"e-{sequence}", sequence, observation_source=value)
    with pytest.raises(psycopg2.errors.CheckViolation):
        _insert_future_observation(connection, "e-invalid", 5, observation_source="OTHER")


def test_different_sources_for_same_order_can_coexist(schema_v2_connection):
    connection = schema_v2_connection
    _assert_migration_004_columns(connection)
    _insert_intent(connection, "i-1", "client-1")
    _insert_future_observation(
        connection,
        "e-1",
        1,
        observation_source="BINANCE_SPOT_ORDER_QUERY",
    )
    _insert_future_observation(
        connection,
        "e-2",
        2,
        observation_source="BINANCE_SPOT_EXECUTION_REPORT",
    )


def test_existing_intent_evidence_sequence_unique_constraint_remains_enforced(
    schema_v2_connection,
):
    connection = schema_v2_connection
    _assert_migration_004_columns(connection)
    _insert_intent(connection, "i-1", "client-1")
    _insert_future_observation(connection, "e-1", 1)
    with pytest.raises(psycopg2.errors.UniqueViolation):
        _insert_future_observation(connection, "e-2", 1)


def test_raw_snapshot_remains_preserved_with_structured_projection(schema_v2_connection):
    connection = schema_v2_connection
    _assert_migration_004_columns(connection)
    _insert_intent(connection, "i-1", "client-1")
    raw_snapshot = '{"status":"PARTIALLY_FILLED","executedQty":"0.1"}'
    _insert_future_observation(connection, "e-1", 1, raw_snapshot=raw_snapshot)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT raw_snapshot::text FROM handa_live.exchange_evidence WHERE evidence_id = 'e-1'"
        )
        retrieved_raw_snapshot = cursor.fetchone()[0]
        assert json.loads(retrieved_raw_snapshot) == json.loads(raw_snapshot)


def test_structured_observation_does_not_create_downstream_effects(schema_v2_connection):
    connection = schema_v2_connection
    _assert_migration_004_columns(connection)
    _insert_intent(connection, "i-1", "client-1")
    _insert_future_observation(connection, "e-1", 1)
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM handa_live.normalized_evidence")
        assert cursor.fetchone() == (0,)
        cursor.execute("SELECT COUNT(*) FROM handa_live.trade_effect")
        assert cursor.fetchone() == (0,)
        cursor.execute("SELECT COUNT(*) FROM handa_live.reconciliation")
        assert cursor.fetchone() == (0,)


def test_migration_history_001_002_003_remains_additive():
    migration_text = MIGRATION.read_text(encoding="utf-8")
    migration_002_text = MIGRATION_002.read_text(encoding="utf-8")
    migration_003_text = MIGRATION_003.read_text(encoding="utf-8")
    for column in MIGRATION_004_COLUMNS:
        assert column not in migration_text
        assert column not in migration_002_text
        assert column not in migration_003_text
