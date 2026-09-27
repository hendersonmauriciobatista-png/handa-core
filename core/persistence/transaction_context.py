"""Restricted structured operations for one coordinator-owned transaction."""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Optional

import psycopg2
from psycopg2 import sql


class TransactionContextError(RuntimeError):
    """Base error for the restricted participant capability."""

    code = "PERSISTENCE_FAILURE"


class InvalidCapabilityRequest(TransactionContextError):
    code = "INVALID_CAPABILITY_REQUEST"


class UniqueConflict(TransactionContextError):
    code = "UNIQUE_CONFLICT"


class VersionConflict(TransactionContextError):
    code = "VERSION_CONFLICT"


class ConstraintFailure(TransactionContextError):
    code = "CONSTRAINT_FAILURE"


class PersistenceFailure(TransactionContextError):
    code = "PERSISTENCE_FAILURE"


class ContextInactive(TransactionContextError):
    code = "CONTEXT_INACTIVE"


class PredicateOperator(str, Enum):
    EQ = "EQ"
    IN = "IN"
    IS_NULL = "IS_NULL"
    IS_NOT_NULL = "IS_NOT_NULL"


@dataclass(frozen=True)
class Predicate:
    column: str
    operator: PredicateOperator
    value: Any = None


@dataclass(frozen=True)
class ResourceSpec:
    schema: str
    table: str
    readable_columns: frozenset[str]
    writable_columns: frozenset[str]
    key_columns: frozenset[str]
    ordering_columns: tuple[str, ...]
    version_column: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "readable_columns", frozenset(self.readable_columns))
        object.__setattr__(self, "writable_columns", frozenset(self.writable_columns))
        object.__setattr__(self, "key_columns", frozenset(self.key_columns))
        object.__setattr__(self, "ordering_columns", tuple(self.ordering_columns))
        _validate_identifier(self.schema, "schema")
        _validate_identifier(self.table, "table")
        if not self.readable_columns:
            raise ValueError("readable_columns are required")
        if not self.key_columns:
            raise ValueError("key_columns are required")
        if not self.ordering_columns:
            raise ValueError("ordering_columns are required")
        all_columns = self.readable_columns | self.writable_columns | self.key_columns
        for column in all_columns:
            _validate_identifier(column, "column")
        for column in self.ordering_columns:
            _validate_identifier(column, "ordering column")
        if not self.writable_columns.issubset(self.readable_columns):
            raise ValueError("writable columns must be readable")
        if not self.key_columns.issubset(self.readable_columns):
            raise ValueError("key columns must be readable")
        if not set(self.ordering_columns).issubset(self.readable_columns):
            raise ValueError("ordering columns must be readable")
        if self.version_column is not None:
            _validate_identifier(self.version_column, "version column")
            if self.version_column not in self.readable_columns:
                raise ValueError("version column must be readable")
            if self.version_column not in self.writable_columns:
                raise ValueError("version column must be writable")


@dataclass(frozen=True)
class ResourceScope:
    resources: tuple[ResourceSpec, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "resources", tuple(self.resources))
        tables = [resource.table for resource in self.resources]
        if len(tables) != len(set(tables)):
            raise ValueError("resource table names must be unique within a scope")

    @classmethod
    def empty(cls) -> "ResourceScope":
        return cls(())

    def resolve(self, table: str) -> ResourceSpec:
        if not isinstance(table, str):
            raise InvalidCapabilityRequest("table must be a scoped identifier")
        for resource in self.resources:
            if resource.table == table:
                return resource
        raise InvalidCapabilityRequest("table is outside the authorized resource scope")


class ImmutableRow(Mapping[str, Any]):
    """Immutable value snapshot returned by structured persistence operations."""

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, Any]) -> None:
        self._values = MappingProxyType(
            {key: _freeze_value(value) for key, value in values.items()}
        )

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


@dataclass(frozen=True)
class ImmutablePage:
    rows: tuple[ImmutableRow, ...]
    next_cursor: Optional[str]


class TransactionContext:
    """Restricted structured view of one local transaction."""

    __slots__ = (
        "_insert_operation",
        "_insert_returning_operation",
        "_read_by_key_operation",
        "_enumerate_operation",
        "_update_if_version_operation",
        "_is_active_operation",
    )

    def __init__(
        self,
        insert_operation: Callable[[str, Mapping[str, Any]], int],
        is_active_operation: Callable[[], bool],
        *,
        insert_returning_operation: Callable[..., ImmutableRow],
        read_by_key_operation: Callable[..., Optional[ImmutableRow]],
        enumerate_operation: Callable[..., ImmutablePage],
        update_if_version_operation: Callable[..., ImmutableRow],
    ) -> None:
        self._insert_operation = insert_operation
        self._insert_returning_operation = insert_returning_operation
        self._read_by_key_operation = read_by_key_operation
        self._enumerate_operation = enumerate_operation
        self._update_if_version_operation = update_if_version_operation
        self._is_active_operation = is_active_operation

    @property
    def is_active(self) -> bool:
        return self._is_active_operation()

    def insert(self, table: str, values: Mapping[str, Any]) -> int:
        self._ensure_active()
        return self._insert_operation(table, values)

    def insert_returning(
        self,
        table: str,
        values: Mapping[str, Any],
        returning_columns: Sequence[str],
    ) -> ImmutableRow:
        self._ensure_active()
        return self._insert_returning_operation(table, values, returning_columns)

    def read_by_key(
        self,
        table: str,
        key_values: Mapping[str, Any],
        columns: Sequence[str],
    ) -> Optional[ImmutableRow]:
        self._ensure_active()
        return self._read_by_key_operation(table, key_values, columns)

    def enumerate(
        self,
        table: str,
        predicates: Sequence[Predicate],
        columns: Sequence[str],
        limit: int,
        cursor: Optional[str] = None,
    ) -> ImmutablePage:
        self._ensure_active()
        return self._enumerate_operation(
            table, predicates, columns, limit, cursor
        )

    def update_if_version(
        self,
        table: str,
        key_values: Mapping[str, Any],
        expected_version: int,
        changes: Mapping[str, Any],
        returning_columns: Sequence[str],
    ) -> ImmutableRow:
        self._ensure_active()
        return self._update_if_version_operation(
            table,
            key_values,
            expected_version,
            changes,
            returning_columns,
        )

    def _ensure_active(self) -> None:
        if not self.is_active:
            raise ContextInactive("transaction context is inactive")


def _build_transaction_operations(connection: Any, scope: ResourceScope) -> dict[str, Callable[..., Any]]:
    """Build coordinator-bound structured operations for one connection."""

    return {
        "insert": lambda table, values: _insert_structured(
            connection, scope, table, values
        ),
        "insert_returning": lambda table, values, returning_columns: _insert_returning(
            connection, scope, table, values, returning_columns
        ),
        "read_by_key": lambda table, key_values, columns: _read_by_key(
            connection, scope, table, key_values, columns
        ),
        "enumerate": lambda table, predicates, columns, limit, cursor=None: _enumerate_rows(
            connection, scope, table, predicates, columns, limit, cursor
        ),
        "update_if_version": lambda table, key_values, expected_version, changes, returning_columns: _update_if_version(
            connection,
            scope,
            table,
            key_values,
            expected_version,
            changes,
            returning_columns,
        ),
    }


def _insert_structured(connection: Any, scope: ResourceScope, table: str, values: Mapping[str, Any]) -> int:
    resource = _validate_insert(scope, table, values)
    statement, parameters = _insert_statement(resource, values)
    with _cursor(connection) as cursor:
        _execute(cursor, statement, parameters)
        return cursor.rowcount


def _insert_returning(connection: Any, scope: ResourceScope, table: str, values: Mapping[str, Any], returning_columns: Sequence[str]) -> ImmutableRow:
    resource = _validate_insert(scope, table, values)
    columns = _validate_columns(resource, returning_columns)
    statement, parameters = _insert_statement(resource, values, columns)
    with _cursor(connection) as cursor:
        _execute(cursor, statement, parameters)
        row = cursor.fetchone()
    if row is None:
        raise PersistenceFailure("insert did not return a row")
    return ImmutableRow(dict(zip(columns, row)))


def _read_by_key(connection: Any, scope: ResourceScope, table: str, key_values: Mapping[str, Any], columns: Sequence[str]) -> Optional[ImmutableRow]:
    resource = scope.resolve(table)
    selected = _validate_columns(resource, columns)
    keys = _validate_key_values(resource, key_values)
    where_sql, parameters = _equality_predicates(keys)
    statement = sql.SQL("SELECT {} FROM {} WHERE {} LIMIT 1").format(
        _identifiers(selected), _resource_identifier(resource), where_sql
    )
    with _cursor(connection) as cursor:
        _execute(cursor, statement, parameters)
        row = cursor.fetchone()
    return None if row is None else ImmutableRow(dict(zip(selected, row)))


def _enumerate_rows(connection: Any, scope: ResourceScope, table: str, predicates: Sequence[Predicate], columns: Sequence[str], limit: int, cursor: Optional[str] = None) -> ImmutablePage:
    resource = scope.resolve(table)
    _validate_limit(limit)
    selected = _validate_columns(resource, columns)
    normalized_predicates = _validate_predicates(resource, predicates)
    cursor_values = _decode_cursor(cursor, resource, normalized_predicates)
    selected_for_query = tuple(dict.fromkeys((*selected, *resource.ordering_columns)))

    where_parts, parameters = _predicate_sql(normalized_predicates)
    if cursor_values is not None:
        ordering = _identifiers(resource.ordering_columns)
        placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in cursor_values)
        where_parts.append(sql.SQL("({}) > ({})").format(ordering, placeholders))
        parameters.extend(cursor_values)
    where_clause = sql.SQL(" AND ").join(where_parts) if where_parts else sql.SQL("TRUE")
    ordering_clause = sql.SQL(", ").join(sql.Identifier(column) for column in resource.ordering_columns)
    statement = sql.SQL("SELECT {} FROM {} WHERE {} ORDER BY {} ASC LIMIT %s").format(
        _identifiers(selected_for_query), _resource_identifier(resource), where_clause, ordering_clause
    )
    parameters.append(limit + 1)
    with _cursor(connection) as db_cursor:
        _execute(db_cursor, statement, tuple(parameters))
        rows = db_cursor.fetchmany(limit + 1)

    has_more = len(rows) > limit
    visible_rows = rows[:limit]
    snapshots = tuple(ImmutableRow(dict(zip(selected_for_query, row))) for row in visible_rows)
    next_cursor = None
    if has_more and snapshots:
        last = snapshots[-1]
        next_cursor = _encode_cursor(
            resource,
            normalized_predicates,
            tuple(last[column] for column in resource.ordering_columns),
        )
    return ImmutablePage(
        rows=tuple(ImmutableRow({column: row[column] for column in selected}) for row in snapshots),
        next_cursor=next_cursor,
    )


def _update_if_version(connection: Any, scope: ResourceScope, table: str, key_values: Mapping[str, Any], expected_version: int, changes: Mapping[str, Any], returning_columns: Sequence[str]) -> ImmutableRow:
    resource = scope.resolve(table)
    if resource.version_column is None:
        raise InvalidCapabilityRequest("resource has no authorized version column")
    if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 0:
        raise InvalidCapabilityRequest("expected_version must be a non-negative integer")
    keys = _validate_key_values(resource, key_values)
    if not changes:
        raise InvalidCapabilityRequest("changes are required")
    for column in changes:
        _validate_identifier(column, "column")
        if column not in resource.writable_columns or column in resource.key_columns or column == resource.version_column:
            raise InvalidCapabilityRequest("change column is not writable")
    returning = _validate_columns(resource, returning_columns)
    assignments = [sql.SQL("{} = %s").format(sql.Identifier(column)) for column in changes]
    assignments.append(sql.SQL("{} = {} + 1").format(sql.Identifier(resource.version_column), sql.Identifier(resource.version_column)))
    where_sql, parameters = _equality_predicates(keys)
    where_sql = sql.SQL("{} AND {} = %s").format(where_sql, sql.Identifier(resource.version_column))
    parameters = tuple(changes[column] for column in changes) + parameters + (expected_version,)
    statement = sql.SQL("UPDATE {} SET {} WHERE {} RETURNING {}").format(
        _resource_identifier(resource), sql.SQL(", ").join(assignments), where_sql, _identifiers(returning)
    )
    with _cursor(connection) as cursor:
        _execute(cursor, statement, parameters)
        row = cursor.fetchone()
    if row is None:
        raise VersionConflict("expected version did not match")
    return ImmutableRow(dict(zip(returning, row)))


def _validate_insert(scope: ResourceScope, table: str, values: Mapping[str, Any]) -> ResourceSpec:
    resource = scope.resolve(table)
    if not isinstance(values, Mapping) or not values:
        raise InvalidCapabilityRequest("insert values are required")
    for column in values:
        if column not in resource.writable_columns:
            raise InvalidCapabilityRequest("column is not writable")
    return resource


def _validate_columns(resource: ResourceSpec, columns: Sequence[str]) -> tuple[str, ...]:
    if isinstance(columns, (str, bytes)) or not columns:
        raise InvalidCapabilityRequest("columns are required")
    result = tuple(columns)
    if len(set(result)) != len(result) or not set(result).issubset(resource.readable_columns):
        raise InvalidCapabilityRequest("columns are outside the resource scope")
    return result


def _validate_key_values(resource: ResourceSpec, key_values: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(key_values, Mapping) or set(key_values) != resource.key_columns:
        raise InvalidCapabilityRequest("authorized key values are required")
    return dict(key_values)


def _validate_predicates(resource: ResourceSpec, predicates: Sequence[Predicate]) -> tuple[Predicate, ...]:
    if isinstance(predicates, (str, bytes)):
        raise InvalidCapabilityRequest("predicates must be structured")
    result = tuple(predicates)
    for predicate in result:
        if not isinstance(predicate, Predicate) or predicate.column not in resource.readable_columns:
            raise InvalidCapabilityRequest("predicate is outside the resource scope")
        if not isinstance(predicate.operator, PredicateOperator):
            raise InvalidCapabilityRequest("predicate operator is not authorized")
        if predicate.operator is PredicateOperator.IN:
            if isinstance(predicate.value, (str, bytes)) or not isinstance(predicate.value, Sequence) or not predicate.value:
                raise InvalidCapabilityRequest("IN requires a non-empty sequence")
        elif predicate.operator in (PredicateOperator.IS_NULL, PredicateOperator.IS_NOT_NULL) and predicate.value is not None:
            raise InvalidCapabilityRequest("NULL predicates do not accept a value")
    return result


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise InvalidCapabilityRequest("limit must be between 1 and 100")


def _insert_statement(resource: ResourceSpec, values: Mapping[str, Any], returning: Sequence[str] = ()):
    columns = _validate_columns(resource, tuple(values))
    statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        _resource_identifier(resource), _identifiers(columns), sql.SQL(", ").join(sql.Placeholder() for _ in columns)
    )
    if returning:
        statement += sql.SQL(" RETURNING {} ").format(_identifiers(returning))
    return statement, tuple(values[column] for column in columns)


def _equality_predicates(values: Mapping[str, Any]):
    parts = [sql.SQL("{} = %s").format(sql.Identifier(column)) for column in values]
    return sql.SQL(" AND ").join(parts), tuple(values.values())


def _predicate_sql(predicates: Sequence[Predicate]):
    parts = []
    parameters: list[Any] = []
    for predicate in predicates:
        column = sql.Identifier(predicate.column)
        if predicate.operator is PredicateOperator.EQ:
            parts.append(sql.SQL("{} = %s").format(column))
            parameters.append(predicate.value)
        elif predicate.operator is PredicateOperator.IN:
            placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in predicate.value)
            parts.append(sql.SQL("{} IN ({})").format(column, placeholders))
            parameters.extend(predicate.value)
        elif predicate.operator is PredicateOperator.IS_NULL:
            parts.append(sql.SQL("{} IS NULL").format(column))
        else:
            parts.append(sql.SQL("{} IS NOT NULL").format(column))
    return parts, parameters


def _resource_identifier(resource: ResourceSpec):
    return sql.Identifier(resource.schema, resource.table)


def _identifiers(columns: Sequence[str]):
    return sql.SQL(", ").join(sql.Identifier(column) for column in columns)


@contextmanager
def _cursor(connection: Any):
    try:
        with connection.cursor() as cursor:
            yield cursor
    except psycopg2.errors.UniqueViolation:
        raise UniqueConflict("unique constraint conflict") from None
    except psycopg2.errors.IntegrityError:
        raise ConstraintFailure("database constraint failure") from None
    except psycopg2.Error:
        raise PersistenceFailure("database operation failed") from None


def _execute(cursor: Any, statement: Any, parameters: tuple[Any, ...] = ()) -> None:
    try:
        cursor.execute(statement, parameters)
    except psycopg2.errors.UniqueViolation:
        raise UniqueConflict("unique constraint conflict") from None
    except psycopg2.errors.IntegrityError:
        raise ConstraintFailure("database constraint failure") from None
    except psycopg2.Error:
        raise PersistenceFailure("database operation failed") from None


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_value(item) for item in value)
    return value


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return {"decimal": str(value)}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise InvalidCapabilityRequest("cursor values must be JSON-compatible scalars")


def _encode_cursor(resource: ResourceSpec, predicates: Sequence[Predicate], values: tuple[Any, ...]) -> str:
    payload = {
        "schema": resource.schema,
        "table": resource.table,
        "ordering": resource.ordering_columns,
        "predicates": [(predicate.column, predicate.operator.value, _json_value(predicate.value)) for predicate in predicates],
        "values": [_json_value(value) for value in values],
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(encoded).decode()


def _decode_cursor(cursor: Optional[str], resource: ResourceSpec, predicates: Sequence[Predicate]) -> Optional[tuple[Any, ...]]:
    if cursor is None:
        return None
    if not isinstance(cursor, str):
        raise InvalidCapabilityRequest("cursor must be opaque text")
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        expected = [(predicate.column, predicate.operator.value, _json_value(predicate.value)) for predicate in predicates]
        if payload.get("schema") != resource.schema or payload.get("table") != resource.table or tuple(payload.get("ordering", ())) != resource.ordering_columns or payload.get("predicates") != expected:
            raise ValueError
        values = tuple(_decode_json_value(value) for value in payload["values"])
        if len(values) != len(resource.ordering_columns):
            raise ValueError
        return values
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeError, binascii.Error):
        raise InvalidCapabilityRequest("cursor is invalid for this resource query") from None


def _decode_json_value(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"decimal"}:
        return Decimal(value["decimal"])
    return value


def _validate_identifier(value: str, kind: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"^[A-Za-z_][A-Za-z0-9_]*$", value):
        raise ValueError(f"invalid {kind} identifier")
