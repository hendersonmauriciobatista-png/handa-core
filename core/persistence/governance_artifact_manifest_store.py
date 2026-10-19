"""Read-only runtime access to externally registered governance manifests."""

from __future__ import annotations

from typing import Any, Mapping, Optional

from core.execution.authority_digest import canonical_manifest_digest as _canonical_manifest_digest
from core.persistence.persistence_coordinator import PersistenceCoordinator
from core.persistence.transaction_context import ImmutablePage, ImmutableRow, Predicate, PredicateOperator, ResourceScope, ResourceSpec


LIVE_SCHEMA = "handa_live"
SECRET_FIELDS = frozenset(
    {
        "credential", "credentials", "api_key", "apikey", "token", "secret",
        "secret_value", "private_key", "database_url", "password",
    }
)
MANIFEST_TYPES = frozenset({"STRATEGY", "POLICY", "RISK", "CONFIGURATION", "FRESHNESS"})
MANIFEST_COLUMNS = (
    "artifact_id", "artifact_type", "artifact_version", "canonical_payload",
    "canonical_payload_digest", "valid_from", "valid_until", "producer_component",
    "schema_version", "contract_version", "created_at", "created_by", "approved_at",
    "approved_by", "approval_reason",
)
ROLE_TO_MANIFEST_TYPE = {name: name for name in MANIFEST_TYPES}


def _contains_secret(value: Any, path: str = "") -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().lower()
            if normalized in SECRET_FIELDS or any(secret in normalized for secret in SECRET_FIELDS):
                return True
            if _contains_secret(item, f"{path}.{key}"):
                return True
    if isinstance(value, (list, tuple)):
        return any(_contains_secret(item, path) for item in value)
    return False


def canonical_manifest_digest(payload: Mapping[str, Any]) -> str:
    if _contains_secret(payload):
        raise ValueError("manifest payload contains secret material")
    return _canonical_manifest_digest(payload)


def manifest_content_identity(role: str, row: Mapping[str, Any]) -> dict[str, Any]:
    """Return the immutable content identity for one expected manifest role."""

    expected_type = ROLE_TO_MANIFEST_TYPE.get(str(role).strip().upper())
    if expected_type is None:
        raise ValueError("unknown manifest role")
    artifact_id = str(row.get("artifact_id", "")).strip()
    artifact_type = str(row.get("artifact_type", "")).strip().upper()
    payload = row.get("canonical_payload")
    if not artifact_id or artifact_type != expected_type or not isinstance(payload, Mapping):
        raise ValueError("manifest role or payload is invalid")
    digest = canonical_manifest_digest(payload)
    if digest != str(row.get("canonical_payload_digest", "")).strip():
        raise ValueError("manifest canonical digest mismatch")
    for field in ("artifact_version", "schema_version", "contract_version"):
        if not str(row.get(field, "")).strip():
            raise ValueError("manifest content identity is incomplete")
    return {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "artifact_version": str(row["artifact_version"]),
        "canonical_payload": dict(payload),
        "canonical_payload_digest": digest,
        "schema_version": str(row["schema_version"]),
        "contract_version": str(row["contract_version"]),
    }


def validate_manifest_bindings(bindings: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Validate all five role bindings without granting a write capability."""

    if set(bindings or {}) != set(MANIFEST_TYPES):
        raise ValueError("all governed manifest roles are required")
    normalized: dict[str, dict[str, Any]] = {}
    identifiers: set[str] = set()
    for role in MANIFEST_TYPES:
        identity = manifest_content_identity(role, bindings[role])
        if identity["artifact_id"] in identifiers:
            raise ValueError("manifest artifact id is reused across roles")
        identifiers.add(identity["artifact_id"])
        normalized[role] = identity
    return normalized


def governance_artifact_manifest_resource_scope() -> ResourceScope:
    return ResourceScope(
        (
            ResourceSpec(
                schema=LIVE_SCHEMA,
                table="governance_artifact_manifest",
                readable_columns=frozenset(MANIFEST_COLUMNS),
                writable_columns=frozenset(),
                key_columns=frozenset({"artifact_id"}),
                ordering_columns=("artifact_type", "artifact_id"),
            ),
        )
    )


class GovernanceArtifactManifestStore:
    """Runtime store intentionally exposing no registration or mutation API."""

    def __init__(self, coordinator: PersistenceCoordinator):
        self._coordinator = coordinator

    def get_manifest(self, artifact_id: str) -> Optional[ImmutableRow]:
        with self._coordinator.transaction() as context:
            return context.read_by_key(
                "governance_artifact_manifest",
                {"artifact_id": artifact_id},
                MANIFEST_COLUMNS,
            )

    def list_manifests(
        self, artifact_type: Optional[str] = None, *, limit: int = 100, cursor: Optional[str] = None
    ) -> ImmutablePage:
        predicates = ()
        if artifact_type is not None:
            if artifact_type not in MANIFEST_TYPES:
                raise ValueError("artifact_type is not a governed manifest type")
            predicates = (Predicate("artifact_type", PredicateOperator.EQ, artifact_type),)
        with self._coordinator.transaction() as context:
            return context.enumerate(
                "governance_artifact_manifest", predicates, MANIFEST_COLUMNS, limit, cursor
            )
