"""Restricted participant operations for one coordinator-owned transaction."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Callable

from psycopg2 import sql


class TransactionContextError(RuntimeError):
    """Raised when a transaction context is not usable."""


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class TransactionContext:
    """Participant-only structured view of one local transaction.

    Participants can write structured values, but cannot submit SQL or access
    the PostgreSQL connection, cursor, or transaction lifecycle.
    """

    __slots__ = ("_insert_operation", "_is_active_operation")

    def __init__(
        self,
        insert_operation: Callable[[str, Mapping[str, Any]], int],
        is_active_operation: Callable[[], bool],
    ) -> None:
        self._insert_operation = insert_operation
        self._is_active_operation = is_active_operation

    @property
    def is_active(self) -> bool:
        return self._is_active_operation()

    def insert(self, table: str, values: Mapping[str, Any]) -> int:
        """Insert structured values without accepting participant SQL."""
        if not self.is_active:
            raise TransactionContextError("transaction context is inactive")
        return self._insert_operation(table, values)


def insert_structured(
    connection: Any,
    table: str,
    values: Mapping[str, Any],
) -> int:
    """Execute one structured insert using a coordinator-owned connection."""
    _validate_identifier(table, "table")
    if not values:
        raise ValueError("insert values are required")

    columns = tuple(values.keys())
    for column in columns:
        _validate_identifier(column, "column")

    statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )

    with connection.cursor() as cursor:
        cursor.execute(statement, tuple(values[column] for column in columns))
        return cursor.rowcount

def _validate_identifier(value: str, kind: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"invalid {kind} identifier")
