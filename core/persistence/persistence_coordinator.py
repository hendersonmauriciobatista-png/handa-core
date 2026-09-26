"""Coordinator-owned PostgreSQL transaction lifecycle."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Optional
from urllib.parse import urlparse

import psycopg2

from core.persistence.transaction_context import (
    TransactionContext,
    insert_structured,
)


class PersistenceFoundationError(RuntimeError):
    """Raised when the transaction foundation cannot fail safely."""


@dataclass(frozen=True)
class DatabaseIdentity:
    allowed_hosts: frozenset[str]
    port: int
    database: str
    user: str

    def matches_url(self, database_url: str) -> bool:
        parsed = urlparse(database_url)
        return (
            parsed.scheme in {"postgres", "postgresql"}
            and parsed.hostname in self.allowed_hosts
            and parsed.port == self.port
            and parsed.path.lstrip("/") == self.database
            and parsed.username == self.user
        )

    def matches_server(self, database: str, user: str) -> bool:
        return database == self.database and user == self.user


class PersistenceCoordinator:
    """Owns one PostgreSQL connection for each transaction and nothing else."""

    def __init__(
        self,
        database_url: str,
        expected_identity: DatabaseIdentity,
        connect: Callable[..., Any] = psycopg2.connect,
    ) -> None:
        if not database_url:
            raise PersistenceFoundationError("database_url is required")
        if not expected_identity.matches_url(database_url):
            raise PersistenceFoundationError(
                "database URL does not identify the authorized database"
            )

        self._database_url = database_url
        self._expected_identity = expected_identity
        self._connect = connect
        self._closed = False
        self._active_connection: Optional[Any] = None

    def verify_ready(self) -> None:
        """Validate connectivity and database identity without retaining a connection."""
        self._ensure_open()
        connection = self._open_verified_connection()
        self._close_connection(connection)

    @contextmanager
    def transaction(self) -> Iterator[TransactionContext]:
        """Run one local atomic unit with one coordinator-owned connection."""
        self._ensure_open()
        connection = self._open_verified_connection()
        self._active_connection = connection
        active_state = {"active": True}

        def is_active() -> bool:
            return active_state["active"]

        def insert_operation(table: str, values: Any) -> int:
            if not active_state["active"]:
                raise RuntimeError("transaction context is inactive")
            return insert_structured(connection, table, values)

        context = TransactionContext(insert_operation, is_active)

        try:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("BEGIN")
            except Exception as exc:
                raise PersistenceFoundationError("transaction begin failed") from exc

            try:
                yield context
            except BaseException as participant_error:
                try:
                    self._rollback(connection)
                except PersistenceFoundationError as rollback_error:
                    raise rollback_error from participant_error
                raise
            else:
                self._commit(connection)
        finally:
            active_state["active"] = False
            self._active_connection = None
            self._close_connection(connection)

    def close(self) -> None:
        """Close the active connection without ever committing pending work."""
        if self._closed:
            return

        self._closed = True
        connection = self._active_connection
        if connection is None:
            return

        try:
            self._rollback(connection)
        finally:
            self._active_connection = None
            self._close_connection(connection)

    def _open_verified_connection(self) -> Any:
        connection = None
        try:
            connection = self._connect(self._database_url)
            connection.autocommit = False
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_user")
                database, user = cursor.fetchone()
            if not self._expected_identity.matches_server(database, user):
                raise PersistenceFoundationError(
                    "connected database identity does not match expectation"
                )
            return connection
        except PersistenceFoundationError:
            if connection is not None:
                self._close_connection(connection)
            raise
        except Exception as exc:
            if connection is not None:
                self._close_connection(connection)
            raise PersistenceFoundationError(
                "unable to establish verified PostgreSQL connection"
            ) from exc

    @staticmethod
    def _rollback(connection: Any) -> None:
        try:
            connection.rollback()
        except Exception as exc:
            raise PersistenceFoundationError("transaction rollback failed") from exc

    @staticmethod
    def _commit(connection: Any) -> None:
        try:
            connection.commit()
        except Exception as exc:
            try:
                connection.rollback()
            except Exception as rollback_exc:
                raise PersistenceFoundationError(
                    "transaction commit and rollback failed"
                ) from rollback_exc
            raise PersistenceFoundationError("transaction commit failed") from exc

    def _close_connection(self, connection: Any) -> None:
        try:
            connection.close()
        except Exception as exc:
            self._closed = True
            raise PersistenceFoundationError("database connection close failed") from exc

    def _ensure_open(self) -> None:
        if self._closed:
            raise PersistenceFoundationError("persistence coordinator is closed")
