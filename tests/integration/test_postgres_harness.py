import os
from urllib.parse import urlparse

import psycopg2
import pytest

EXPECTED_DATABASE = "handa_test"
EXPECTED_USER = "handa_test"
EXPECTED_HOSTS = {"127.0.0.1", "localhost"}
EXPECTED_PORT = 55432


def _connect_test_database():
    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        pytest.fail(
            "TEST_DATABASE_URL is required; refusing database integration test."
        )

    parsed = urlparse(database_url)

    if (
        parsed.hostname not in EXPECTED_HOSTS
        or parsed.port != EXPECTED_PORT
        or parsed.path.lstrip("/") != EXPECTED_DATABASE
        or parsed.username != EXPECTED_USER
    ):
        pytest.fail(
            "TEST_DATABASE_URL does not identify the governed local test database; "
            "refusing connection."
        )

    connection = psycopg2.connect(database_url)

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user")
            database, user = cursor.fetchone()

        if database != EXPECTED_DATABASE or user != EXPECTED_USER:
            pytest.fail(
                "Database identity mismatch; refusing integration test. "
                f"Expected {EXPECTED_DATABASE}/{EXPECTED_USER}, "
                f"got {database}/{user}."
            )

        return connection

    except Exception:
        if not connection.closed:
            connection.close()
        raise


def test_postgres_test_harness_identity_and_rollback():
    connection = _connect_test_database()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TEMP TABLE handa_harness_probe "
                "(id INTEGER PRIMARY KEY, marker TEXT NOT NULL)"
            )
            cursor.execute(
                "INSERT INTO handa_harness_probe (id, marker) VALUES (%s, %s)",
                (1, "test-only"),
            )
            cursor.execute(
                "SELECT marker FROM handa_harness_probe WHERE id = %s",
                (1,),
            )
            assert cursor.fetchone() == ("test-only",)

        connection.rollback()

        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('pg_temp.handa_harness_probe')")
            assert cursor.fetchone() == (None,)

    finally:
        connection.close()
