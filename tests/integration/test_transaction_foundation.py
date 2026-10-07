import os
from dataclasses import FrozenInstanceError
from urllib.parse import urlparse

import psycopg2
import pytest
import core.persistence.transaction_context as transaction_context_module

from core.persistence.persistence_coordinator import (
    DatabaseIdentity,
    PersistenceCoordinator,
    PersistenceFoundationError,
)
from core.persistence.transaction_context import (
    ContextInactive,
    ImmutableRow,
    InvalidCapabilityRequest,
    Predicate,
    PredicateOperator,
    ResourceScope,
    ResourceSpec,
    TransactionContextError,
    UniqueConflict,
    VersionConflict,
)


EXPECTED_IDENTITY = DatabaseIdentity(
    allowed_hosts=frozenset({"127.0.0.1", "localhost"}),
    port=55432,
    database="handa_test",
    user="handa_test",
)
PROBE_TABLE = "handa_3a1_transaction_probe"
VERSION_TABLE = "handa_3a1_version_probe"
TEST_SCOPE = ResourceScope(
    (
        ResourceSpec(
            schema="public",
            table=PROBE_TABLE,
            readable_columns=frozenset({"participant", "marker", "readonly_marker"}),
            writable_columns=frozenset({"participant", "marker"}),
            key_columns=frozenset({"participant"}),
            ordering_columns=("participant",),
        ),
        ResourceSpec(
            schema="public",
            table=VERSION_TABLE,
            readable_columns=frozenset({"id", "marker", "version", "nullable_marker"}),
            writable_columns=frozenset({"id", "marker", "version", "nullable_marker"}),
            key_columns=frozenset({"id"}),
            ordering_columns=("id",),
            version_column="version",
        ),
    )
)


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
    return PersistenceCoordinator(
        database_url,
        EXPECTED_IDENTITY,
        connect=connect,
        resource_scope=TEST_SCOPE,
    )


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
                "(participant TEXT PRIMARY KEY, marker TEXT NOT NULL, "
                "readonly_marker TEXT NOT NULL DEFAULT 'fixed')"
            )
            cursor.execute(
                f"CREATE TABLE {VERSION_TABLE} "
                "(id INTEGER PRIMARY KEY, marker TEXT NOT NULL, "
                "version INTEGER NOT NULL, nullable_marker TEXT)"
            )
        connection.commit()
        yield database_url
    finally:
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {PROBE_TABLE}")
                cursor.execute(f"DROP TABLE IF EXISTS {VERSION_TABLE}")
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
            with pytest.raises(InvalidCapabilityRequest):
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

            assert context.__slots__ == (
                "_insert_operation",
                "_insert_returning_operation",
                "_read_by_key_operation",
                "_enumerate_operation",
                "_update_if_version_operation",
                "_allocate_next_sequence_operation",
                "_is_active_operation",
            )
            assert not hasattr(transaction_context_module, "_CONTEXT_CONNECTIONS")
            assert "WeakKeyDictionary" not in vars(transaction_context_module)
    finally:
        coordinator.close()


def test_structured_identifiers_reject_sql_fragments(probe_table):
    coordinator = _coordinator(probe_table)
    try:
        with coordinator.transaction() as context:
            with pytest.raises(InvalidCapabilityRequest):
                context.insert("/* comment */ probe", {"value": "blocked"})
            with pytest.raises(InvalidCapabilityRequest):
                context.insert(PROBE_TABLE, {"marker; COMMIT": "blocked"})
    finally:
        coordinator.close()


def test_resource_scope_rejects_unauthorized_resources_and_columns(probe_table):
    coordinator = _coordinator(probe_table)
    try:
        with coordinator.transaction() as context:
            with pytest.raises(InvalidCapabilityRequest):
                context.insert("not_authorized", {"value": "blocked"})
            with pytest.raises(InvalidCapabilityRequest):
                context.insert(PROBE_TABLE, {"readonly_marker": "blocked"})
            with pytest.raises(InvalidCapabilityRequest):
                context.read_by_key(
                    PROBE_TABLE,
                    {"unknown_key": "blocked"},
                    ("participant",),
                )
    finally:
        coordinator.close()


def test_resource_scope_is_immutable():
    scope = ResourceScope(list(TEST_SCOPE.resources))
    assert isinstance(scope.resources, tuple)
    assert isinstance(scope.resources[0].readable_columns, frozenset)
    with pytest.raises(FrozenInstanceError):
        scope.resources = ()


def test_value_injection_remains_data(probe_table):
    payload = "value'); DROP TABLE handa_3a1_transaction_probe; --"
    coordinator = _coordinator(probe_table)
    try:
        with coordinator.transaction() as context:
            context.insert(PROBE_TABLE, {"participant": "payload", "marker": payload})
        assert ("payload", payload) in _rows(probe_table)
        assert _rows(probe_table) == [("payload", payload)]
    finally:
        coordinator.close()


def test_structured_reads_support_only_approved_predicates(probe_table):
    coordinator = _coordinator(probe_table)
    try:
        with coordinator.transaction() as context:
            for row in (
                {"id": 1, "marker": "one", "version": 0, "nullable_marker": None},
                {"id": 2, "marker": "two", "version": 0, "nullable_marker": "present"},
                {"id": 3, "marker": "three", "version": 0, "nullable_marker": None},
            ):
                context.insert(VERSION_TABLE, row)

            assert context.read_by_key(VERSION_TABLE, {"id": 99}, ("id",)) is None
            eq_page = context.enumerate(
                VERSION_TABLE,
                (Predicate("marker", PredicateOperator.EQ, "two"),),
                ("id", "marker"),
                10,
            )
            assert [row["id"] for row in eq_page.rows] == [2]

            in_page = context.enumerate(
                VERSION_TABLE,
                (Predicate("id", PredicateOperator.IN, (1, 3)),),
                ("id",),
                10,
            )
            assert [row["id"] for row in in_page.rows] == [1, 3]

            null_page = context.enumerate(
                VERSION_TABLE,
                (Predicate("nullable_marker", PredicateOperator.IS_NULL),),
                ("id",),
                10,
            )
            assert [row["id"] for row in null_page.rows] == [1, 3]

            not_null_page = context.enumerate(
                VERSION_TABLE,
                (Predicate("nullable_marker", PredicateOperator.IS_NOT_NULL),),
                ("id",),
                10,
            )
            assert [row["id"] for row in not_null_page.rows] == [2]

            with pytest.raises(InvalidCapabilityRequest):
                context.enumerate(
                    VERSION_TABLE,
                    (Predicate("id", "=", 1),),
                    ("id",),
                    10,
                )
            with pytest.raises(InvalidCapabilityRequest):
                context.enumerate(
                    VERSION_TABLE,
                    (Predicate("id || 'x'", PredicateOperator.EQ, 1),),
                    ("id",),
                    10,
                )
    finally:
        coordinator.close()


@pytest.mark.parametrize("limit", [0, -1, 101, True, False, None])
def test_enumeration_limit_is_bounded(probe_table, limit):
    coordinator = _coordinator(probe_table)
    try:
        with coordinator.transaction() as context:
            with pytest.raises(InvalidCapabilityRequest):
                context.enumerate(VERSION_TABLE, (), ("id",), limit)
    finally:
        coordinator.close()


def test_pagination_is_deterministic_and_cursor_bound(probe_table):
    coordinator = _coordinator(probe_table)
    try:
        with coordinator.transaction() as context:
            for row_id in (1, 2, 3):
                context.insert(
                    VERSION_TABLE,
                    {
                        "id": row_id,
                        "marker": str(row_id),
                        "version": 0,
                        "nullable_marker": None,
                    },
                )
            first = context.enumerate(VERSION_TABLE, (), ("id",), 2)
            assert [row["id"] for row in first.rows] == [1, 2]
            assert first.next_cursor
            second = context.enumerate(
                VERSION_TABLE, (), ("id",), 2, cursor=first.next_cursor
            )
            assert [row["id"] for row in second.rows] == [3]
            assert second.next_cursor is None
            with pytest.raises(InvalidCapabilityRequest):
                context.enumerate(
                    VERSION_TABLE,
                    (Predicate("id", PredicateOperator.EQ, 1),),
                    ("id",),
                    2,
                    cursor=first.next_cursor,
                )

            filtered_first = context.enumerate(
                VERSION_TABLE,
                (Predicate("id", PredicateOperator.IN, (1, 2, 3)),),
                ("id",),
                2,
            )
            assert [row["id"] for row in filtered_first.rows] == [1, 2]
            assert filtered_first.next_cursor
            filtered_second = context.enumerate(
                VERSION_TABLE,
                (Predicate("id", PredicateOperator.IN, (1, 2, 3)),),
                ("id",),
                2,
                cursor=filtered_first.next_cursor,
            )
            assert [row["id"] for row in filtered_second.rows] == [3]
            with pytest.raises(InvalidCapabilityRequest):
                context.enumerate(
                    VERSION_TABLE,
                    (Predicate("id", PredicateOperator.IN, (1, 2)),),
                    ("id",),
                    2,
                    cursor=filtered_first.next_cursor,
                )
    finally:
        coordinator.close()


def test_insert_returning_and_results_are_immutable(probe_table):
    coordinator = _coordinator(probe_table)
    try:
        with coordinator.transaction() as context:
            returned = context.insert_returning(
                VERSION_TABLE,
                {"id": 1, "marker": "one", "version": 0, "nullable_marker": None},
                ("id", "marker", "version"),
            )
            assert isinstance(returned, ImmutableRow)
            assert returned["version"] == 0
            with pytest.raises(TypeError):
                returned["marker"] = "changed"
            page = context.enumerate(VERSION_TABLE, (), ("id",), 10)
            with pytest.raises(AttributeError):
                page.rows.append(returned)
    finally:
        coordinator.close()


def test_update_if_version_is_atomic_and_stale_version_fails(probe_table):
    coordinator = _coordinator(probe_table)
    try:
        with coordinator.transaction() as context:
            context.insert(
                VERSION_TABLE,
                {"id": 1, "marker": "one", "version": 0, "nullable_marker": None},
            )
            updated = context.update_if_version(
                VERSION_TABLE,
                {"id": 1},
                0,
                {"marker": "updated"},
                ("id", "marker", "version"),
            )
            assert dict(updated) == {"id": 1, "marker": "updated", "version": 1}
            with pytest.raises(VersionConflict):
                context.update_if_version(
                    VERSION_TABLE,
                    {"id": 1},
                    0,
                    {"marker": "stale"},
                    ("id", "marker", "version"),
                )
    finally:
        coordinator.close()


def test_unique_conflict_is_explicit_and_not_upsert(probe_table):
    coordinator = _coordinator(probe_table)
    try:
        with pytest.raises(UniqueConflict):
            with coordinator.transaction() as context:
                context.insert(PROBE_TABLE, {"participant": "same", "marker": "first"})
                context.insert(PROBE_TABLE, {"participant": "same", "marker": "second"})
        assert _rows(probe_table) == []
    finally:
        coordinator.close()


def test_constraint_failure_is_not_success(probe_table):
    coordinator = _coordinator(probe_table)
    try:
        with pytest.raises(TransactionContextError) as failure:
            with coordinator.transaction() as context:
                context.insert(PROBE_TABLE, {"participant": "invalid", "marker": None})
        assert failure.value.code == "CONSTRAINT_FAILURE"
        assert _rows(probe_table) == []
    finally:
        coordinator.close()


def test_sequence_allocator_supports_distinct_target_and_lock_owner_columns(probe_table):
    target_table = "handa_3a1_sequence_target"
    lock_table = "handa_3a1_sequence_lock"
    connection = psycopg2.connect(probe_table)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE TABLE {target_table} (request_owner TEXT NOT NULL, sequence BIGINT NOT NULL)"
            )
            cursor.execute(
                f"CREATE TABLE {lock_table} (attempt_id TEXT PRIMARY KEY)"
            )
            cursor.execute(
                f"INSERT INTO {lock_table} (attempt_id) VALUES ('attempt-1')"
            )
        connection.commit()

        scope = ResourceScope(
            (
                ResourceSpec(
                    schema="public",
                    table=target_table,
                    readable_columns=frozenset({"request_owner", "sequence"}),
                    writable_columns=frozenset({"request_owner", "sequence"}),
                    key_columns=frozenset({"request_owner"}),
                    ordering_columns=("request_owner", "sequence"),
                ),
                ResourceSpec(
                    schema="public",
                    table=lock_table,
                    readable_columns=frozenset({"attempt_id"}),
                    writable_columns=frozenset(),
                    key_columns=frozenset({"attempt_id"}),
                    ordering_columns=("attempt_id",),
                ),
            )
        )
        coordinator = PersistenceCoordinator(
            probe_table, EXPECTED_IDENTITY, resource_scope=scope
        )
        try:
            with coordinator.transaction() as context:
                first = context.allocate_next_sequence(
                    target_table,
                    "request_owner",
                    "attempt-1",
                    "sequence",
                    lock_table,
                    lock_owner_column="attempt_id",
                )
                assert first == 1
                context.insert(
                    target_table,
                    {"request_owner": "attempt-1", "sequence": first},
                )
                second = context.allocate_next_sequence(
                    target_table,
                    "request_owner",
                    "attempt-1",
                    "sequence",
                    lock_table,
                    lock_owner_column="attempt_id",
                )
                assert second == 2
        finally:
            coordinator.close()

        with pytest.raises(InvalidCapabilityRequest):
            coordinator = PersistenceCoordinator(
                probe_table, EXPECTED_IDENTITY, resource_scope=scope
            )
            try:
                with coordinator.transaction() as context:
                    context.allocate_next_sequence(
                        target_table,
                        "request_owner",
                        "missing-attempt",
                        "sequence",
                        lock_table,
                        lock_owner_column="attempt_id",
                    )
            finally:
                coordinator.close()
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {target_table}")
            cursor.execute(f"DROP TABLE IF EXISTS {lock_table}")
        connection.commit()
        connection.close()


def test_all_structured_operations_reject_inactive_context(probe_table):
    coordinator = _coordinator(probe_table)
    holder = []
    try:
        with coordinator.transaction() as context:
            holder.append(context)
        context = holder[0]
        with pytest.raises(ContextInactive):
            context.insert_returning(PROBE_TABLE, {"participant": "x", "marker": "x"}, ("participant",))
        with pytest.raises(ContextInactive):
            context.read_by_key(PROBE_TABLE, {"participant": "x"}, ("participant",))
        with pytest.raises(ContextInactive):
            context.enumerate(PROBE_TABLE, (), ("participant",), 1)
        with pytest.raises(ContextInactive):
            context.update_if_version(PROBE_TABLE, {"participant": "x"}, 0, {"marker": "x"}, ("participant",))
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
