import os
from urllib.parse import urlparse

import psycopg2
import pytest
import core.persistence.transaction_context as transaction_context_module

from core.persistence.persistence_coordinator import (
    DatabaseIdentity,
    PersistenceCoordinator,
    PersistenceFoundationError,
)
from core.persistence.transaction_context import TransactionContextError


EXPECTED_IDENTITY = DatabaseIdentity(
    allowed_hosts=frozenset({"127.0.0.1", "localhost"}),
    port=55432,
    database="handa_test",
    user="handa_test",
)
PROBE_TABLE = "handa_3a1_transaction_probe"


def _test_database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("TEST_DATABASE_URL is required; refusing integration test.")

    parsed = urlparse(database_url)
    if not EXPECTED_IDENTITY.matches_url(database_url):
        pytest.fail(
            "TEST_DATABASE_URL does not identify the governed local test database; "
            "refusing integration test."
        )
    assert parsed.username == EXPECTED_IDENTITY.user
    return database_url


def _coordinator(database_url: str, connect=psycopg2.connect):
    return PersistenceCoordinator(database_url, EXPECTED_IDENTITY, connect=connect)


class ParticipantA:
    def apply(self, context):
        context.insert(
            PROBE_TABLE,
            {"participant": "a", "marker": "first"},
        )


class ParticipantB:
    def __init__(self, fail=False):
        self.fail = fail

    def apply(self, context):
        context.insert(
            PROBE_TABLE,
            {"participant": "b", "marker": "second"},
        )
        if self.fail:
            raise RuntimeError("participant B failed")


@pytest.fixture
def probe_table():
    database_url = _test_database_url()
    connection = psycopg2.connect(database_url)
    try:
        connection.autocommit = False
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {PROBE_TABLE}")
            cursor.execute(
                f"CREATE TABLE {PROBE_TABLE} "
                "(participant TEXT PRIMARY KEY, marker TEXT NOT NULL)"
            )
        connection.commit()
        yield database_url
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {PROBE_TABLE}")
            connection.commit()
        finally:
            connection.close()


def _rows(database_url):
    connection = psycopg2.connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT participant, marker FROM {PROBE_TABLE} ORDER BY participant"
            )
            return cursor.fetchall()
    finally:
        connection.close()


def test_independent_participants_share_one_context(probe_table):
    coordinator = _coordinator(probe_table)
    participant_a = ParticipantA()
    participant_b = ParticipantB()
    contexts = []

    try:
        with coordinator.transaction() as context:
            contexts.extend([context, context])
            participant_a.apply(context)
            participant_b.apply(context)
        assert contexts[0] is contexts[1]
        assert _rows(probe_table) == [("a", "first"), ("b", "second")]
    finally:
        coordinator.close()


def test_participant_b_failure_rolls_back_participant_a(probe_table):
    coordinator = _coordinator(probe_table)
    try:
        with pytest.raises(RuntimeError, match="participant B"):
            with coordinator.transaction() as context:
                ParticipantA().apply(context)
                ParticipantB(fail=True).apply(context)
        assert _rows(probe_table) == []
    finally:
        coordinator.close()


def test_context_has_only_structured_participant_capability(probe_table):
    coordinator = _coordinator(probe_table)
    try:
        with coordinator.transaction() as context:
            assert context.is_active
            assert hasattr(context, "insert")
            assert not hasattr(context, "connection")
            assert not hasattr(context, "cursor")
            assert not hasattr(context, "execute")
            assert not hasattr(context, "commit")
            assert not hasattr(context, "rollback")
            assert not hasattr(context, "close")
            with pytest.raises(ValueError):
                context.insert("probe; COMMIT", {"value": "blocked"})
    finally:
        coordinator.close()


def test_context_uses_local_capability_without_global_registry(probe_table):
    coordinator = _coordinator(probe_table)
    try:
        with coordinator.transaction() as context:
            for name in (
                "_connection",
                "connection",
                "_cursor",
                "cursor",
                "execute",
                "commit",
                "rollback",
                "close",
            ):
                with pytest.raises(AttributeError):
                    getattr(context, name)

            with pytest.raises(AttributeError):
                context.__dict__

            assert context.__slots__ == ("_insert_operation", "_is_active_operation")
            assert not hasattr(transaction_context_module, "_CONTEXT_CONNECTIONS")
            assert "WeakKeyDictionary" not in vars(transaction_context_module)
    finally:
        coordinator.close()


def test_structured_identifiers_reject_sql_fragments(probe_table):
    coordinator = _coordinator(probe_table)
    try:
        with coordinator.transaction() as context:
            with pytest.raises(ValueError):
                context.insert("/* comment */ probe", {"value": "blocked"})
            with pytest.raises(ValueError):
                context.insert(PROBE_TABLE, {"marker; COMMIT": "blocked"})
    finally:
        coordinator.close()


def test_coordinator_closes_connection_after_commit(probe_table):
    opened = []

    def connect(url):
        connection = psycopg2.connect(url)
        opened.append(connection)
        return connection

    coordinator = _coordinator(probe_table, connect=connect)
    try:
        with coordinator.transaction() as context:
            ParticipantA().apply(context)
        assert opened[0].closed == 1
        assert coordinator._active_connection is None
    finally:
        coordinator.close()


def test_each_transaction_uses_a_new_connection(probe_table):
    opened = []

    def connect(url):
        connection = psycopg2.connect(url)
        opened.append(connection)
        return connection

    coordinator = _coordinator(probe_table, connect=connect)
    try:
        with coordinator.transaction():
            pass
        with coordinator.transaction():
            pass
        assert len(opened) == 2
        assert opened[0] is not opened[1]
        assert all(connection.closed == 1 for connection in opened)
    finally:
        coordinator.close()


def test_transaction_after_close_fails_closed(probe_table):
    coordinator = _coordinator(probe_table)
    coordinator.close()
    coordinator.close()
    with pytest.raises(PersistenceFoundationError):
        with coordinator.transaction():
            pass


def test_invalid_test_database_identity_fails_closed(probe_table):
    wrong_identity = DatabaseIdentity(
        allowed_hosts=EXPECTED_IDENTITY.allowed_hosts,
        port=EXPECTED_IDENTITY.port,
        database="not_handa_test",
        user=EXPECTED_IDENTITY.user,
    )
    with pytest.raises(PersistenceFoundationError):
        PersistenceCoordinator(probe_table, wrong_identity)


def test_database_url_is_not_used_as_test_fallback(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://handa_test:handa_test_only@127.0.0.1:55432/handa_test",
    )
    with pytest.raises(BaseException) as failure:
        _test_database_url()
    assert "TEST_DATABASE_URL" in str(failure.value)


class FakeCursor:
    rowcount = 1

    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def execute(self, statement, _params=()):
        if str(statement) == "BEGIN" and self.connection.fail_begin:
            raise OSError("begin unavailable")

    def close(self):
        pass

    def fetchone(self):
        return ("handa_test", "handa_test")


class FakeConnection:
    def __init__(self, *, fail_begin=False, fail_commit=False, fail_rollback=False, fail_close=False):
        self.autocommit = None
        self.fail_begin = fail_begin
        self.fail_commit = fail_commit
        self.fail_rollback = fail_rollback
        self.fail_close = fail_close
        self.rollback_calls = 0
        self.close_calls = 0
        self.closed = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        if self.fail_commit:
            raise OSError("commit unavailable")

    def rollback(self):
        self.rollback_calls += 1
        if self.fail_rollback:
            raise OSError("rollback unavailable")

    def close(self):
        self.close_calls += 1
        if self.fail_close:
            raise OSError("close unavailable")
        self.closed = 1


def _fake_coordinator(fake_connection):
    return _coordinator(
        "postgresql://handa_test:handa_test_only@127.0.0.1:55432/handa_test",
        connect=lambda _url: fake_connection,
    )


def test_begin_failure_never_executes_participant_and_discards_connection():
    connection = FakeConnection(fail_begin=True)
    coordinator = _fake_coordinator(connection)
    participant_called = []

    with pytest.raises(PersistenceFoundationError):
        with coordinator.transaction() as context:
            participant_called.append(True)
            ParticipantA().apply(context)

    assert participant_called == []
    assert connection.closed == 1
    assert connection.close_calls == 1


def test_commit_failure_rolls_back_discards_and_does_not_retry():
    connection = FakeConnection(fail_commit=True)
    coordinator = _fake_coordinator(connection)

    with pytest.raises(PersistenceFoundationError, match="commit failed"):
        with coordinator.transaction() as context:
            ParticipantA().apply(context)

    assert connection.rollback_calls == 1
    assert connection.closed == 1
    assert connection.close_calls == 1


def test_rollback_failure_preserves_participant_failure_and_discards():
    connection = FakeConnection(fail_rollback=True)
    coordinator = _fake_coordinator(connection)

    with pytest.raises(PersistenceFoundationError, match="rollback failed") as failure:
        with coordinator.transaction() as context:
            ParticipantB(fail=True).apply(context)

    assert isinstance(failure.value.__cause__, RuntimeError)
    assert "participant B failed" in str(failure.value.__cause__)
    assert connection.closed == 1
    assert connection.close_calls == 1


def test_close_failure_marks_coordinator_unusable_and_never_reuses_connection():
    connection = FakeConnection(fail_close=True)
    coordinator = _fake_coordinator(connection)

    with pytest.raises(PersistenceFoundationError, match="close failed"):
        with coordinator.transaction():
            pass

    assert coordinator._active_connection is None
    with pytest.raises(PersistenceFoundationError):
        with coordinator.transaction():
            pass


def test_connection_failure_is_not_retried(probe_table):
    attempts = []

    def connect(_url):
        attempts.append(1)
        raise OSError("connection unavailable")

    coordinator = _coordinator(probe_table, connect=connect)
    with pytest.raises(PersistenceFoundationError):
        coordinator.verify_ready()
    assert attempts == [1]


def test_inactive_context_rejects_participant_work(probe_table):
    coordinator = _coordinator(probe_table)
    context_holder = []
    try:
        with coordinator.transaction() as context:
            context_holder.append(context)
        with pytest.raises(TransactionContextError):
            context_holder[0].insert(PROBE_TABLE, {"participant": "a"})
    finally:
        coordinator.close()
