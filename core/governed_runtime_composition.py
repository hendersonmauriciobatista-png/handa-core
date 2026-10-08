"""Governed, read-only composition of the H&A headless runtime.

This module is intentionally limited to read-only boot evidence and never
grants execution authority.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Optional

import psycopg2

from core.persistence.authority_envelope_store import (
    AuthorityEnvelopeStore,
    authority_envelope_resource_scope,
)
from core.persistence.operational_authority_state_store import (
    OperationalAuthorityStateStore,
    operational_authority_state_resource_scope,
)
from core.persistence.persistence_coordinator import (
    DatabaseIdentity,
    PersistenceCoordinator,
    PersistenceFoundationError,
)
from core.persistence.transaction_context import ImmutableRow, ResourceScope


OBSERVE_ONLY = "OBSERVE_ONLY"
GOVERNED_INFRASTRUCTURE_READY = "GOVERNED_INFRASTRUCTURE_READY"
FINAL_SCHEMA_SIGNATURE_VALID = "FINAL_SCHEMA_SIGNATURE_VALID"
FINAL_SCHEMA_SIGNATURE_INVALID = "FINAL_SCHEMA_SIGNATURE_INVALID"
AUTHORITY_STATE_OBSERVE_ONLY = "AUTHORITY_STATE_OBSERVE_ONLY"
ACTIVE_ENVELOPE_MISSING = "ACTIVE_ENVELOPE_MISSING"
ACTIVE_ENVELOPE_INVALID = "ACTIVE_ENVELOPE_INVALID"
EXECUTION_AUTHORITY_NOT_GRANTED = "NOT_GRANTED"

_MIGRATION_NAMES = tuple(
    f.name
    for f in sorted(
        (Path(__file__).resolve().parent / "persistence" / "migrations").glob("*.sql")
    )
    if f.name[:3].isdigit() and 1 <= int(f.name[:3]) <= 12
)
_TABLE_PATTERN = re.compile(
    r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+handa_live\.([a-z_][a-z0-9_]*)\s*\((.*?)\);",
    re.IGNORECASE | re.DOTALL,
)
_COLUMN_PATTERN = re.compile(
    r"^\s{4}([a-z_][a-z0-9_]*)\s+(?=(?:TEXT|BIGINT|BIGSERIAL|NUMERIC|BOOLEAN|TIMESTAMPTZ|JSONB|INTEGER|TEXT\[))",
    re.IGNORECASE,
)
_ALTER_TABLE_PATTERN = re.compile(
    r"ALTER\s+TABLE\s+handa_live\.([a-z_][a-z0-9_]*)\s+(.*?);",
    re.IGNORECASE | re.DOTALL,
)
_ADD_COLUMN_PATTERN = re.compile(
    r"\bADD\s+COLUMN\s+([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)


def _migration_sources() -> tuple[Path, ...]:
    root = Path(__file__).resolve().parent / "persistence" / "migrations"
    return tuple(root / name for name in _MIGRATION_NAMES)


def _expected_schema_catalog() -> tuple[frozenset[str], frozenset[tuple[str, str]]]:
    tables: set[str] = set()
    columns: set[tuple[str, str]] = set()

    for path in _migration_sources():
        source = path.read_text(encoding="utf-8")
        for match in _TABLE_PATTERN.finditer(source):
            table = match.group(1)
            tables.add(table)
            for line in match.group(2).splitlines():
                column = _COLUMN_PATTERN.match(line)
                if column:
                    columns.add((table, column.group(1)))
        for table, statement in _ALTER_TABLE_PATTERN.findall(source):
            columns.update((table, column) for column in _ADD_COLUMN_PATTERN.findall(statement))

    return frozenset(tables), frozenset(columns)


EXPECTED_SCHEMA_TABLES, EXPECTED_SCHEMA_COLUMNS = _expected_schema_catalog()
EXPECTED_SCHEMA_CONSTRAINTS = frozenset(
    {
        "order_intent_may_have_been_certainty_ck",
        "order_intent_terminal_reconciliation_ck",
    }
)


def _schema_digest(
    tables: set[str] | frozenset[str],
    columns: set[tuple[str, str]] | frozenset[tuple[str, str]],
    constraints: set[str] | frozenset[str] = frozenset(),
) -> str:
    entries = [
        *(f"table:{table}" for table in sorted(tables)),
        *(f"column:{table}.{column}" for table, column in sorted(columns)),
        *(f"constraint:{constraint}" for constraint in sorted(constraints)),
    ]
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()


EXPECTED_SCHEMA_DIGEST = _schema_digest(
    EXPECTED_SCHEMA_TABLES,
    EXPECTED_SCHEMA_COLUMNS,
    EXPECTED_SCHEMA_CONSTRAINTS,
)


@dataclass(frozen=True)
class SchemaSignature:
    """Immutable structural result for the final 001–012 catalog shape."""

    digest: str
    valid: bool
    missing_tables: tuple[str, ...] = ()
    missing_columns: tuple[tuple[str, str], ...] = ()
    missing_constraints: tuple[str, ...] = ()
    extra_tables: tuple[str, ...] = ()
    extra_columns: tuple[tuple[str, str], ...] = ()


def verify_final_schema_signature(connection: Any) -> SchemaSignature:
    """Verify the live catalog shape without claiming migration history."""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'handa_live' AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        tables = {row[0] for row in cursor.fetchall()}

        cursor.execute(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'handa_live'
            ORDER BY table_name, ordinal_position
            """
        )
        columns = {(row[0], row[1]) for row in cursor.fetchall()}

        cursor.execute(
            """
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE constraint_schema = 'handa_live'
              AND constraint_name = ANY(%s::text[])
            ORDER BY constraint_name
            """,
            (list(sorted(EXPECTED_SCHEMA_CONSTRAINTS)),),
        )
        constraints = {row[0] for row in cursor.fetchall()}

    missing_tables = tuple(sorted(EXPECTED_SCHEMA_TABLES - tables))
    missing_columns = tuple(sorted(EXPECTED_SCHEMA_COLUMNS - columns))
    missing_constraints = tuple(sorted(EXPECTED_SCHEMA_CONSTRAINTS - constraints))
    extra_tables = tuple(sorted(tables - EXPECTED_SCHEMA_TABLES))
    extra_columns = tuple(sorted(columns - EXPECTED_SCHEMA_COLUMNS))
    digest = _schema_digest(
        tables,
        columns,
        constraints & EXPECTED_SCHEMA_CONSTRAINTS,
    )
    valid = not (
        missing_tables
        or missing_columns
        or missing_constraints
        or extra_tables
        or extra_columns
    ) and digest == EXPECTED_SCHEMA_DIGEST
    return SchemaSignature(
        digest=digest,
        valid=valid,
        missing_tables=missing_tables,
        missing_columns=missing_columns,
        missing_constraints=missing_constraints,
        extra_tables=extra_tables,
        extra_columns=extra_columns,
    )


def _combined_read_only_scope() -> ResourceScope:
    return ResourceScope(
        (
            *operational_authority_state_resource_scope().resources,
            *authority_envelope_resource_scope().resources,
        )
    )


@dataclass(frozen=True)
class RuntimeCompositionConfig:
    """Explicit boot inputs; database identity is independent of DATABASE_URL."""

    database_url: Optional[str]
    database_identity: Optional[DatabaseIdentity]
    connect: Callable[..., Any] = psycopg2.connect

    @classmethod
    def from_environment(cls, environ: Optional[Mapping[str, str]] = None) -> "RuntimeCompositionConfig":
        values = os.environ if environ is None else environ
        url = values.get("DATABASE_URL")
        hosts_value = (
            values.get("HANDA_GOVERNED_DB_ALLOWED_HOSTS")
        )
        port_value = values.get("HANDA_GOVERNED_DB_PORT")
        database = values.get("HANDA_GOVERNED_DB_NAME")
        user = values.get("HANDA_GOVERNED_DB_USER")

        identity = None
        if hosts_value and port_value and database and user:
            try:
                hosts = frozenset(
                    host.strip() for host in hosts_value.split(",") if host.strip()
                )
                identity = DatabaseIdentity(
                    allowed_hosts=hosts,
                    port=int(port_value),
                    database=database.strip(),
                    user=user.strip(),
                )
            except (TypeError, ValueError):
                identity = None

        return cls(
            database_url=url.strip() if isinstance(url, str) and url.strip() else None,
            database_identity=identity,
        )


@dataclass(frozen=True)
class AuthoritySnapshot:
    """Stable read-only S1 → envelope → S2 authority evidence."""

    state_s1: ImmutableRow
    active_envelope: Optional[ImmutableRow]
    state_s2: ImmutableRow


@dataclass(frozen=True)
class BootResult:
    """Immutable boot decision; ready never means execution is authorized."""

    posture: str
    reason: str
    operational_effects_blocked: bool = True
    execution_authority: str = EXECUTION_AUTHORITY_NOT_GRANTED
    schema_signature_status: str = FINAL_SCHEMA_SIGNATURE_INVALID
    schema_signature: Optional[str] = None
    authority_snapshot: Optional[AuthoritySnapshot] = None
    details: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "operational_effects_blocked", True)
        object.__setattr__(self, "execution_authority", EXECUTION_AUTHORITY_NOT_GRANTED)
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))


def _valid_identity(identity: Optional[DatabaseIdentity]) -> bool:
    return bool(
        isinstance(identity, DatabaseIdentity)
        and identity.allowed_hosts
        and all(isinstance(host, str) and host.strip() for host in identity.allowed_hosts)
        and isinstance(identity.port, int)
        and not isinstance(identity.port, bool)
        and 1 <= identity.port <= 65535
        and isinstance(identity.database, str)
        and bool(identity.database.strip())
        and isinstance(identity.user, str)
        and bool(identity.user.strip())
    )


def _as_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _state_is_consistent(state: ImmutableRow) -> bool:
    if state["state_id"] is not True:
        return False
    if state["operational_mode"] not in {OBSERVE_ONLY, "OPERATIONAL_ENABLED"}:
        return False
    for field_name in ("global_safety_epoch", "runtime_generation", "current_version"):
        value = state[field_name]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return False
    return bool(state["changed_by"] and state["change_reason"])


def _envelope_is_current(
    envelope: ImmutableRow,
    state: ImmutableRow,
    now: datetime,
) -> bool:
    if envelope["authority_envelope_id"] != state["active_authority_envelope_id"]:
        return False
    if envelope["runtime_mode"] != "OPERATIONAL_ENABLED":
        return False
    valid_from = _as_utc(envelope["valid_from"])
    valid_until = _as_utc(envelope["valid_until"])
    if valid_from is None or valid_until is None or not valid_from <= now < valid_until:
        return False
    if not envelope["venue"] or not envelope["account_scope"]:
        return False
    for field_name in (
        "strategy_version",
        "decision_contract_version",
        "policy_version",
        "risk_policy_version",
    ):
        value = envelope[field_name]
        if not isinstance(value, str) or not value.strip():
            return False
    if not envelope["authority_contract_version"] or not envelope["configuration_digest"]:
        return False
    allowed_sides = tuple(envelope["allowed_sides"] or ())
    return bool(allowed_sides) and set(allowed_sides).issubset({"BUY", "SELL"})


class GovernedRuntimeComposition:
    """Owns the coordinator lifecycle and produces one immutable boot result."""

    def __init__(
        self,
        config: RuntimeCompositionConfig,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        schema_verifier: Callable[[Any], Any] = verify_final_schema_signature,
        state_store_factory: Callable[[PersistenceCoordinator], Any] = OperationalAuthorityStateStore,
        envelope_store_factory: Callable[[PersistenceCoordinator], Any] = AuthorityEnvelopeStore,
    ) -> None:
        self.config = config
        self._now = now
        self._schema_verifier = schema_verifier
        self._state_store_factory = state_store_factory
        self._envelope_store_factory = envelope_store_factory
        self._coordinator: Optional[PersistenceCoordinator] = None
        self._boot_result: Optional[BootResult] = None

    @classmethod
    def from_environment(cls, environ: Optional[Mapping[str, str]] = None) -> "GovernedRuntimeComposition":
        return cls(RuntimeCompositionConfig.from_environment(environ))

    def boot(self) -> BootResult:
        if self._boot_result is not None:
            return self._boot_result

        if not self.config.database_url:
            result = self._failure("DATABASE_URL_MISSING")
        elif self.config.database_identity is None:
            result = self._failure("DATABASE_IDENTITY_CONFIG_MISSING")
        elif not _valid_identity(self.config.database_identity):
            result = self._failure("DATABASE_IDENTITY_CONFIG_INVALID")
        else:
            result = self._boot_verified()

        self._boot_result = result
        return result

    def _boot_verified(self) -> BootResult:
        assert self.config.database_url is not None
        assert self.config.database_identity is not None
        try:
            self._coordinator = PersistenceCoordinator(
                self.config.database_url,
                self.config.database_identity,
                connect=self.config.connect,
                resource_scope=_combined_read_only_scope(),
            )
            self._coordinator.verify_ready()
        except PersistenceFoundationError as exc:
            reason = (
                "DATABASE_IDENTITY_MISMATCH"
                if "identity" in str(exc).lower() or "authorized database" in str(exc).lower()
                else "POSTGRES_CONNECTION_FAILED"
            )
            return self._failure(reason)
        except Exception:
            return self._failure("POSTGRES_CONNECTION_FAILED")

        schema_signature: Optional[SchemaSignature] = None
        schema_connection = None
        try:
            schema_connection = self.config.connect(self.config.database_url)
            with schema_connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_user")
                database, user = cursor.fetchone()
            if not self.config.database_identity.matches_server(database, user):
                return self._failure("DATABASE_IDENTITY_MISMATCH")
            schema_signature = self._schema_verifier(schema_connection)
        except Exception:
            return self._failure("FINAL_SCHEMA_SIGNATURE_INVALID")
        finally:
            if schema_connection is not None:
                try:
                    schema_connection.close()
                except Exception:
                    self.close()

        if isinstance(schema_signature, bool):
            schema_valid = schema_signature
            schema_digest = None
        else:
            schema_valid = bool(getattr(schema_signature, "valid", False))
            schema_digest = getattr(schema_signature, "digest", None)
        if not schema_valid:
            return self._failure(
                "FINAL_SCHEMA_SIGNATURE_INVALID",
                schema_signature=schema_digest,
            )

        state_store = self._state_store_factory(self._coordinator)
        envelope_store = self._envelope_store_factory(self._coordinator)
        try:
            state_s1 = state_store.get_current_state()
            if state_s1 is None:
                return self._failure("AUTHORITY_STATE_MISSING", schema_signature=schema_digest)
            if not _state_is_consistent(state_s1):
                return self._failure("AUTHORITY_STATE_INCONSISTENT", schema_signature=schema_digest)

            active_envelope = None
            active_id = state_s1["active_authority_envelope_id"]
            if active_id is not None:
                active_envelope = envelope_store.get_envelope(active_id)
                if active_envelope is None:
                    return self._failure(
                        ACTIVE_ENVELOPE_INVALID,
                        schema_signature=schema_digest,
                    )

            state_s2 = state_store.get_current_state()
            if state_s2 is None:
                return self._failure("AUTHORITY_STATE_MISSING", schema_signature=schema_digest)
            if state_s1 != state_s2:
                return self._failure(
                    "AUTHORITY_STATE_INCONSISTENT",
                    schema_signature=schema_digest,
                )
            if not _state_is_consistent(state_s2):
                return self._failure("AUTHORITY_STATE_INCONSISTENT", schema_signature=schema_digest)

            now = _as_utc(self._now()) or datetime.now(timezone.utc)
            if state_s1["operational_mode"] == "OPERATIONAL_ENABLED":
                if active_id is None:
                    return self._failure(
                        ACTIVE_ENVELOPE_MISSING,
                        schema_signature=schema_digest,
                    )
                if active_envelope is None or not _envelope_is_current(active_envelope, state_s1, now):
                    return self._failure(
                        ACTIVE_ENVELOPE_INVALID,
                        schema_signature=schema_digest,
                    )
            elif active_envelope is not None:
                return self._failure(
                    "AUTHORITY_STATE_INCONSISTENT",
                    schema_signature=schema_digest,
                )

            snapshot = AuthoritySnapshot(state_s1, active_envelope, state_s2)
            if state_s1["operational_mode"] == OBSERVE_ONLY:
                return BootResult(
                    posture=OBSERVE_ONLY,
                    reason=AUTHORITY_STATE_OBSERVE_ONLY,
                    schema_signature_status=FINAL_SCHEMA_SIGNATURE_VALID,
                    schema_signature=schema_digest,
                    authority_snapshot=snapshot,
                )
            return BootResult(
                posture=GOVERNED_INFRASTRUCTURE_READY,
                reason=FINAL_SCHEMA_SIGNATURE_VALID,
                schema_signature_status=FINAL_SCHEMA_SIGNATURE_VALID,
                schema_signature=schema_digest,
                authority_snapshot=snapshot,
            )
        except Exception:
            return self._failure("AUTHORITY_STATE_READ_FAILED", schema_signature=schema_digest)

    def _failure(self, reason: str, *, schema_signature: Optional[str] = None) -> BootResult:
        self.close()
        return BootResult(
            posture=OBSERVE_ONLY,
            reason=reason,
            schema_signature=schema_signature,
        )

    def close(self) -> None:
        if self._coordinator is not None:
            try:
                self._coordinator.close()
            finally:
                self._coordinator = None

    def __enter__(self) -> "GovernedRuntimeComposition":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def load_runtime_composition_config(
    environ: Optional[Mapping[str, str]] = None,
) -> RuntimeCompositionConfig:
    """Load explicit boot configuration; no DATABASE_URL fallback is allowed."""

    return RuntimeCompositionConfig.from_environment(environ)


def governed_runtime_boot(
    config: RuntimeCompositionConfig,
    **kwargs: Any,
) -> tuple[GovernedRuntimeComposition, BootResult]:
    """Convenience entrypoint returning the owner and its immutable boot result."""

    composition = GovernedRuntimeComposition(config, **kwargs)
    return composition, composition.boot()
