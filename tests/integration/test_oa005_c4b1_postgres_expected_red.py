"""PostgreSQL falsifiers for the implemented C4B-1 schema foundation.

The fixture uses only the disposable local test database and applies the
published migration chain through 008.  No production schema is created by
this file.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest

from core.persistence.effect_application_ledger import EffectApplicationLedgerError
from tests.integration import test_effect_application_ledger_postgres as _postgres


ROOT = Path(__file__).parents[2]
MIGRATIONS_DIR = ROOT / "core" / "persistence" / "migrations"
MIGRATIONS = tuple(
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
EXPECTED_DATABASE = "handa_test"
EXPECTED_USER = "handa_test"
EXPECTED_HOSTS = {"127.0.0.1", "localhost"}
EXPECTED_PORT = 55432


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
        pytest.skip(
            "ENVIRONMENT_BLOCKED: TEST_DATABASE_URL is not the disposable "
            "handa_test database"
        )
    return value


def _connect():
    try:
        return psycopg2.connect(_database_url())
    except (OSError, psycopg2.Error) as exc:
        pytest.skip(f"ENVIRONMENT_BLOCKED: disposable PostgreSQL unavailable: {exc}")


@pytest.fixture()
def connection():
    connection = _connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user")
            assert cursor.fetchone() == (EXPECTED_DATABASE, EXPECTED_USER)
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


def _column_exists(connection, table_name, column_name):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'handa_live'
                  AND table_name = %s
                  AND column_name = %s
            )
            """,
            (table_name, column_name),
        )
        return cursor.fetchone()[0]


def _effect_request_indexes(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'handa_live'
              AND tablename = 'effect_request'
            ORDER BY indexname
            """
        )
        return cursor.fetchall()


def _insert_logical_request(
    connection, request_id, *, intent_id="intent-a", context_id="context-a", logical_id
):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.effect_request
                (effect_request_id, effect_type, intent_id,
                 reconciliation_context_id, logical_effect_id, current_state)
            VALUES (%s, 'TEST_EFFECT', %s, %s, %s, 'AUTHORIZED')
            """,
            (request_id, intent_id, context_id, logical_id),
        )
    connection.commit()


def test_c4b1_db001_logical_effect_id_column_is_text_nullable_without_default(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema='handa_live'
              AND table_name='effect_request'
              AND column_name='logical_effect_id'
            """
        )
        assert cursor.fetchone() == ("text", "YES", None)


def test_c4b1_db002_current_generic_effect_request_insert_succeeds(connection):
    _postgres._base(connection)
    result = _postgres._request(_postgres._ledger(connection))
    assert result.effect_request_id == "request-a"
    assert result.state == "AUTHORIZED"


def test_c4b1_db003_logical_effect_id_is_nullable_for_legacy_rows(connection):
    _postgres._base(connection)
    result = _postgres._request(_postgres._ledger(connection), request_id="legacy-null")
    assert result.state == "AUTHORIZED"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT logical_effect_id FROM handa_live.effect_request "
            "WHERE effect_request_id='legacy-null'"
        )
        assert cursor.fetchone() == (None,)


def test_c4b1_db004_partial_logical_unique_index_is_enforced(connection):
    _postgres._base(connection)
    ledger = _postgres._ledger(connection)
    _postgres._request(ledger, request_id="legacy-null-a")
    _postgres._request(ledger, request_id="legacy-null-b")
    _insert_logical_request(connection, "logical-a", logical_id="logical-a")
    with connection.cursor() as cursor:
        with pytest.raises(psycopg2.errors.UniqueViolation):
            cursor.execute(
                """
                INSERT INTO handa_live.effect_request
                    (effect_request_id, effect_type, intent_id,
                     reconciliation_context_id, logical_effect_id, current_state)
                VALUES ('logical-b', 'TEST_EFFECT', 'intent-a',
                        'context-a', 'logical-a', 'AUTHORIZED')
                """
            )
    connection.rollback()
    _postgres._intent(connection, intent_id="intent-b")
    _postgres._context(
        connection,
        context_id="context-b",
        intent_id="intent-b",
    )
    connection.commit()
    _insert_logical_request(
        connection,
        "logical-c",
        intent_id="intent-b",
        context_id="context-b",
        logical_id="logical-a",
    )
    _insert_logical_request(
        connection,
        "logical-d",
        logical_id="logical-b",
    )
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM handa_live.effect_request
            WHERE logical_effect_id IS NULL
            """
        )
        assert cursor.fetchone() == (2,)
    definitions = _effect_request_indexes(connection)
    logical_index = [
        definition.lower()
        for name, definition in definitions
        if name == "effect_request_logical_identity_uq"
    ]
    assert len(logical_index) == 1
    assert "(intent_id, logical_effect_id)" in logical_index[0]
    assert "where (logical_effect_id is not null)" in logical_index[0]


def test_c4b1_db005_effect_request_id_primary_key_remains_protected(connection):
    _postgres._base(connection)
    ledger = _postgres._ledger(connection)
    _postgres._request(ledger)
    with pytest.raises(EffectApplicationLedgerError):
        _postgres._request(ledger)


def test_c4b1_db006_no_synthetic_logical_identity_exists(connection):
    _postgres._base(connection)
    ledger = _postgres._ledger(connection)
    _postgres._request(ledger, request_id="legacy-a")
    _postgres._request(ledger, request_id="legacy-b")
    migration_text = "\n".join(
        path.read_text(encoding="utf-8").lower() for path in MIGRATIONS
    )
    assert "update handa_live.effect_request" not in migration_text
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT effect_request_id, logical_effect_id
            FROM handa_live.effect_request
            WHERE effect_request_id IN ('legacy-a', 'legacy-b')
            ORDER BY effect_request_id
            """
        )
        assert cursor.fetchall() == [("legacy-a", None), ("legacy-b", None)]


def test_c4b1_db007_no_substitute_logical_identity_constraint_exists(connection):
    definitions = _effect_request_indexes(connection)
    logical_indexes = [
        definition.lower()
        for _, definition in definitions
        if "logical_effect_id" in definition.lower()
    ]
    assert logical_indexes == [
        next(
            definition.lower()
            for name, definition in definitions
            if name == "effect_request_logical_identity_uq"
        )
    ]


def test_c4b1_db008_database_represents_migration_008_head(connection):
    assert tuple(path.name for path in MIGRATIONS)[-1] == "008_effect_request_logical_binding.sql"
    assert (MIGRATIONS_DIR / "008_effect_request_logical_binding.sql").exists()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM pg_indexes
            WHERE schemaname='handa_live'
              AND tablename='effect_request'
              AND indexname='effect_request_logical_identity_uq'
            """
        )
        assert cursor.fetchone() == (1,)


def test_c4b1_db009_current_ledger_remains_generic(connection):
    _postgres._base(connection)
    result = _postgres._request(_postgres._ledger(connection))
    assert result.state == "AUTHORIZED"
    assert result.effect_request_id == "request-a"


def test_c4b1_db010_no_c4b_implementation_leakage_exists(connection):
    ledger_source = (
        ROOT / "core" / "persistence" / "effect_application_ledger.py"
    ).read_text(encoding="utf-8")
    assert "logical_effect_id" not in ledger_source
    assert "bind_logical_effect" not in ledger_source
    assert "lookup_logical_binding" not in ledger_source
    assert "AppliedEffectReplayRecord" not in ledger_source
    assert "PositionEffectResult" not in ledger_source
