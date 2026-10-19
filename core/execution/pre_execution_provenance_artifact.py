"""Immutable candidate-specific provenance for the 2B8B pre-execution boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional

from core.execution.authority_digest import (
    canonical_decimal,
    canonical_semantic_digest,
    canonical_timestamp,
)
from core.market.governed_market_observation import (
    CAUSAL_DERIVED_CONSTITUENT,
    MARKET_OBSERVATION_CONSTITUENT,
    canonical_group_digest,
)


class BindingStatus(str, Enum):
    BOUND = "BOUND"
    UNBOUND = "UNBOUND"
    INCOMPLETE = "INCOMPLETE"


MANIFEST_TYPES = ("STRATEGY", "POLICY", "RISK", "CONFIGURATION", "FRESHNESS")
REQUIRED_SOURCE_GROUPS = ("PRICE_TECHNICAL", "SELECTION_RADAR", "MARKET_CONTEXT")
PROVENANCE_CONTRACT_VERSION = "handa-2b8b-pre-execution-provenance-v1"
TRUSTED_MARKET_TIME = "TRUSTED_MARKET_TIME"


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise TypeError("timestamp must be datetime")
    value = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _restore_temporal(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _restore_temporal(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_restore_temporal(item) for item in value]
    if isinstance(value, str):
        candidate = value.strip()
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return value
        return _utc(parsed)
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((_freeze(item) for item in value), key=repr))
    if isinstance(value, str):
        return str(value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _mapping(value: Optional[Mapping[str, Any]]) -> MappingProxyType:
    return _freeze(value or {})


def _manifest_refs(value: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    safe_fields = (
        "artifact_id", "artifact_type", "artifact_version",
        "canonical_payload_digest", "schema_version", "contract_version",
    )
    refs: dict[str, Any] = {}
    for name in MANIFEST_TYPES:
        if not value or value.get(name) is None:
            continue
        item = value[name]
        if isinstance(item, Mapping):
            refs[name] = {
                field: item[field]
                for field in safe_fields
                if field in item
            }
        else:
            refs[name] = str(item).strip()
    return refs


def _manifest_binding_identity(value: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    """Validate immutable manifest content without creating or mutating it."""

    if set(value) != set(MANIFEST_TYPES):
        return {}, False
    try:
        from core.persistence.governance_artifact_manifest_store import (
            canonical_manifest_digest,
        )

        identity: dict[str, Any] = {}
        identifiers: set[str] = set()
        for role in MANIFEST_TYPES:
            row = value[role]
            if not isinstance(row, Mapping):
                return {}, False
            artifact_id = str(row.get("artifact_id", "")).strip()
            artifact_type = str(row.get("artifact_type", "")).strip().upper()
            payload = row.get("canonical_payload")
            if not artifact_id or artifact_id in identifiers:
                return {}, False
            if artifact_type != role or not isinstance(payload, Mapping):
                return {}, False
            if canonical_manifest_digest(payload) != str(
                row.get("canonical_payload_digest", "")
            ).strip():
                return {}, False
            if not all(
                str(row.get(field, "")).strip()
                for field in ("artifact_version", "schema_version", "contract_version")
            ):
                return {}, False
            identifiers.add(artifact_id)
            identity[role] = dict(row)
        return identity, True
    except (TypeError, ValueError, KeyError):
        return {}, False


def _digest_metadata(
    source_group_digests: Mapping[str, Any],
    source_group_closure_statuses: Optional[Mapping[str, Any]],
    source_group_server_times: Optional[Mapping[str, Any]],
    source_group_constituent_digests: Optional[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    statuses = dict(source_group_closure_statuses or {})
    server_times = dict(source_group_server_times or {})
    constituent_digests = dict(source_group_constituent_digests or {})
    for group, digest in (source_group_digests or {}).items():
        if group not in statuses and getattr(digest, "close_status", None):
            statuses[group] = getattr(digest, "close_status")
        if group not in server_times and hasattr(digest, "server_time_at"):
            server_times[group] = getattr(digest, "server_time_at")
        if group not in constituent_digests:
            constituent_digests[group] = (str(digest),)
    return statuses, server_times, constituent_digests


def provenance_artifact_id(identity: Mapping[str, Any]) -> str:
    return f"provenance-{canonical_semantic_digest(dict(identity))}"


@dataclass(frozen=True)
class PreExecutionProvenanceArtifact:
    candidate_id: str
    symbol: str
    side: str
    source_group_timestamps: Mapping[str, Any]
    source_group_digests: Mapping[str, str]
    source_group_intervals: Mapping[str, Any]
    requested_quote_amount: Decimal
    binding_status: BindingStatus
    canonical_semantic_digest: str
    source_group_closure_statuses: Mapping[str, Any] = None
    source_group_server_times: Mapping[str, Any] = None
    source_group_constituent_digests: Mapping[str, Any] = None
    candidate_evidence_identity: str = ""
    ticker_value: Optional[Decimal] = None
    ticker_application_receipt_at: Optional[datetime] = None
    decision_produced_at: Optional[datetime] = None
    dynamic_policy_evidence: Mapping[str, Any] = None
    dynamic_risk_evidence: Mapping[str, Any] = None
    source_group_identities: Mapping[str, Any] = None
    source_group_constituents: Mapping[str, Any] = None
    source_group_missing_evidence: Mapping[str, Any] = None
    source_group_trust: Mapping[str, Any] = None
    decision_dynamic_evidence: Mapping[str, Any] = None
    static_manifest_references: Mapping[str, Any] = None
    static_manifest_identity: Mapping[str, Any] = None
    recorded_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not str(self.symbol).strip() or self.side != "BUY":
            raise ValueError("a BUY candidate symbol is required")
        if not isinstance(self.binding_status, BindingStatus):
            object.__setattr__(self, "binding_status", BindingStatus(self.binding_status))
        amount = Decimal(str(self.requested_quote_amount))
        if amount <= 0:
            raise ValueError("requested_quote_amount must be positive")
        object.__setattr__(self, "symbol", str(self.symbol).strip().upper())
        object.__setattr__(self, "requested_quote_amount", amount)
        object.__setattr__(self, "source_group_timestamps", _mapping(self.source_group_timestamps))
        object.__setattr__(self, "source_group_digests", _mapping(self.source_group_digests))
        object.__setattr__(self, "source_group_intervals", _mapping(self.source_group_intervals))
        object.__setattr__(self, "source_group_closure_statuses", _mapping(self.source_group_closure_statuses))
        object.__setattr__(self, "source_group_server_times", _mapping(self.source_group_server_times))
        object.__setattr__(self, "source_group_constituent_digests", _mapping(self.source_group_constituent_digests))
        object.__setattr__(self, "source_group_identities", _mapping(self.source_group_identities))
        object.__setattr__(self, "source_group_constituents", _mapping(self.source_group_constituents))
        object.__setattr__(self, "source_group_missing_evidence", _mapping(self.source_group_missing_evidence))
        object.__setattr__(self, "source_group_trust", _mapping(self.source_group_trust))
        object.__setattr__(self, "decision_dynamic_evidence", _mapping(self.decision_dynamic_evidence))
        object.__setattr__(self, "dynamic_policy_evidence", _mapping(self.dynamic_policy_evidence))
        object.__setattr__(self, "dynamic_risk_evidence", _mapping(self.dynamic_risk_evidence))
        object.__setattr__(self, "static_manifest_references", _mapping(self.static_manifest_references))
        object.__setattr__(self, "static_manifest_identity", _mapping(self.static_manifest_identity))
        if self.ticker_value is not None:
            object.__setattr__(self, "ticker_value", Decimal(str(self.ticker_value)))
        object.__setattr__(self, "ticker_application_receipt_at", _utc(self.ticker_application_receipt_at))
        object.__setattr__(self, "decision_produced_at", _utc(self.decision_produced_at))
        object.__setattr__(self, "recorded_at", _utc(self.recorded_at))
        if not self.canonical_semantic_digest:
            identity = self.semantic_identity()
            object.__setattr__(self, "canonical_semantic_digest", canonical_semantic_digest(identity))
        expected_id = f"provenance-{self.canonical_semantic_digest}"
        if self.candidate_id != expected_id:
            raise ValueError("candidate_id must be derived from canonical semantic identity")

    def semantic_identity(self) -> dict[str, Any]:
        return {
            "contract_version": PROVENANCE_CONTRACT_VERSION,
            "candidate_evidence_identity": self.candidate_evidence_identity,
            "symbol": self.symbol,
            "side": self.side,
            "source_group_timestamps": dict(self.source_group_timestamps),
            "source_group_digests": dict(self.source_group_digests),
            "source_group_intervals": dict(self.source_group_intervals),
            "source_group_closure_statuses": dict(self.source_group_closure_statuses),
            "source_group_server_times": dict(self.source_group_server_times),
            "source_group_constituent_digests": dict(self.source_group_constituent_digests),
            "source_group_identities": dict(self.source_group_identities),
            "source_group_constituents": dict(self.source_group_constituents),
            "source_group_missing_evidence": dict(self.source_group_missing_evidence),
            "source_group_trust": dict(self.source_group_trust),
            "ticker_value": canonical_decimal(self.ticker_value) if self.ticker_value is not None else None,
            "ticker_application_receipt_at": self.ticker_application_receipt_at,
            "decision_produced_at": self.decision_produced_at,
            "requested_quote_amount": canonical_decimal(self.requested_quote_amount),
            "dynamic_policy_evidence": _thaw(self.dynamic_policy_evidence),
            "dynamic_risk_evidence": _thaw(self.dynamic_risk_evidence),
            "decision_dynamic_evidence": _thaw(self.decision_dynamic_evidence),
            "static_manifest_references": dict(self.static_manifest_references),
            "static_manifest_identity": dict(self.static_manifest_identity),
            "binding_status": self.binding_status.value,
        }

    def as_record(self) -> dict[str, Any]:
        def manifest_id(role: str) -> Optional[str]:
            reference = self.static_manifest_references.get(role)
            if isinstance(reference, Mapping):
                reference = reference.get("artifact_id")
            return reference

        return {
            "provenance_artifact_id": self.candidate_id,
            "candidate_evidence_identity": self.candidate_evidence_identity,
            "symbol": self.symbol,
            "side": self.side,
            "source_group_timestamps": _thaw(self.source_group_timestamps),
            "source_group_digests": _thaw(self.source_group_digests),
            "source_group_intervals": _thaw(self.source_group_intervals),
            "source_group_closure_statuses": _thaw(self.source_group_closure_statuses),
            "source_group_server_times": _thaw(self.source_group_server_times),
            "source_group_constituent_digests": _thaw(self.source_group_constituent_digests),
            "source_group_identities": _thaw(self.source_group_identities),
            "source_group_constituents": _thaw(self.source_group_constituents),
            "source_group_missing_evidence": _thaw(self.source_group_missing_evidence),
            "source_group_trust": _thaw(self.source_group_trust),
            "ticker_value": self.ticker_value,
            "ticker_application_receipt_at": self.ticker_application_receipt_at,
            "decision_produced_at": self.decision_produced_at,
            "requested_quote_amount": self.requested_quote_amount,
            "dynamic_policy_evidence": _thaw(self.dynamic_policy_evidence),
            "dynamic_risk_evidence": _thaw(self.dynamic_risk_evidence),
            "decision_dynamic_evidence": _thaw(self.decision_dynamic_evidence),
            "strategy_manifest_id": manifest_id("STRATEGY"),
            "policy_manifest_id": manifest_id("POLICY"),
            "risk_manifest_id": manifest_id("RISK"),
            "configuration_manifest_id": manifest_id("CONFIGURATION"),
            "freshness_manifest_id": manifest_id("FRESHNESS"),
            "static_manifest_identity": _thaw(self.static_manifest_identity),
            "binding_status": self.binding_status.value,
            "canonical_semantic_digest": self.canonical_semantic_digest,
            "recorded_at": self.recorded_at,
        }

    def with_static_manifest_references(
        self, references: Optional[Mapping[str, Any]]
    ) -> "PreExecutionProvenanceArtifact":
        normalized_references = {
            role: (
                value.get("artifact_id")
                if isinstance(value, Mapping)
                else value
            )
            for role, value in (references or {}).items()
        }
        manifest_identity, manifest_identity_valid = _manifest_binding_identity(
            references or {}
        )
        return build_provenance_artifact(
            symbol=self.symbol,
            side=self.side,
            candidate_evidence_identity=self.candidate_evidence_identity,
            source_group_timestamps=_thaw(self.source_group_timestamps),
            source_group_digests=_thaw(self.source_group_digests),
            source_group_intervals=_thaw(self.source_group_intervals),
            source_group_closure_statuses=_thaw(self.source_group_closure_statuses),
            source_group_server_times=_thaw(self.source_group_server_times),
            source_group_constituent_digests=_thaw(self.source_group_constituent_digests),
            source_group_identities=_thaw(self.source_group_identities),
            source_group_constituents=_thaw(self.source_group_constituents),
            source_group_missing_evidence=_thaw(self.source_group_missing_evidence),
            source_group_trust=_thaw(self.source_group_trust),
            ticker_value=self.ticker_value,
            ticker_application_receipt_at=self.ticker_application_receipt_at,
            decision_produced_at=self.decision_produced_at,
            requested_quote_amount=self.requested_quote_amount,
            dynamic_policy_evidence=_thaw(self.dynamic_policy_evidence),
            dynamic_risk_evidence=_thaw(self.dynamic_risk_evidence),
            decision_dynamic_evidence=_thaw(self.decision_dynamic_evidence),
            static_manifest_references=normalized_references,
            static_manifest_identity=(
                manifest_identity
                if manifest_identity_valid
                else _thaw(self.static_manifest_identity)
            ),
            recorded_at=self.recorded_at,
        )

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "PreExecutionProvenanceArtifact":
        artifact = build_provenance_artifact(
            symbol=record["symbol"],
            side=record["side"],
            candidate_evidence_identity=record.get("candidate_evidence_identity", ""),
            source_group_timestamps=_restore_temporal(
                record.get("source_group_timestamps", {})
            ),
            source_group_digests=record.get("source_group_digests", {}),
            source_group_intervals=_restore_temporal(
                record.get("source_group_intervals", {})
            ),
            source_group_closure_statuses=record.get("source_group_closure_statuses", {}),
            source_group_server_times=_restore_temporal(
                record.get("source_group_server_times", {})
            ),
            source_group_constituent_digests=record.get(
                "source_group_constituent_digests", {}
            ),
            source_group_identities=record.get("source_group_identities", {}),
            source_group_constituents=_restore_temporal(
                record.get("source_group_constituents", {})
            ),
            source_group_missing_evidence=record.get("source_group_missing_evidence", {}),
            source_group_trust=record.get("source_group_trust", {}),
            ticker_value=record.get("ticker_value"),
            ticker_application_receipt_at=record.get("ticker_application_receipt_at"),
            decision_produced_at=record.get("decision_produced_at"),
            requested_quote_amount=record["requested_quote_amount"],
            dynamic_policy_evidence=record.get("dynamic_policy_evidence", {}),
            dynamic_risk_evidence=record.get("dynamic_risk_evidence", {}),
            decision_dynamic_evidence=record.get("decision_dynamic_evidence", {}),
            static_manifest_references={
                name: record.get(f"{name.lower()}_manifest_id")
                for name in MANIFEST_TYPES
                if record.get(f"{name.lower()}_manifest_id")
            },
            recorded_at=record.get("recorded_at"),
            static_manifest_identity=record.get("static_manifest_identity", {}),
        )
        if record.get("provenance_artifact_id") not in (None, artifact.candidate_id):
            raise ValueError("persisted provenance artifact identity mismatch")
        if record.get("canonical_semantic_digest") not in (
            None,
            artifact.canonical_semantic_digest,
        ):
            raise ValueError("persisted provenance semantic digest mismatch")
        return artifact


def _binding_status(
    manifests: Mapping[str, Any], incomplete: bool, manifest_valid: bool
) -> BindingStatus:
    if incomplete:
        return BindingStatus.INCOMPLETE
    if manifest_valid and all(manifests.get(name) for name in MANIFEST_TYPES):
        return BindingStatus.BOUND
    return BindingStatus.UNBOUND


def _has_trustworthy_price_closure(
    timestamps: Mapping[str, Any],
    statuses: Mapping[str, Any],
    server_times: Mapping[str, Any],
    constituent_digests: Mapping[str, Any],
) -> bool:
    close_time = timestamps.get("PRICE_TECHNICAL")
    if statuses.get("PRICE_TECHNICAL") != "CLOSED":
        return False
    if not isinstance(close_time, datetime):
        return False
    verified = server_times.get("PRICE_TECHNICAL")
    if isinstance(verified, (list, tuple)):
        verified_times = tuple(verified)
    else:
        verified_times = (verified,)
    if not verified_times or not all(isinstance(value, datetime) for value in verified_times):
        return False
    if not any(value > close_time for value in verified_times):
        return False
    constituents = constituent_digests.get("PRICE_TECHNICAL")
    if isinstance(constituents, str):
        return bool(constituents.strip())
    return bool(constituents)


def _dynamic_group_is_complete(
    group: str,
    *,
    digests: Mapping[str, Any],
    intervals: Mapping[str, Any],
    identities: Mapping[str, Any],
    constituents: Mapping[str, Any],
    missing_evidence: Mapping[str, Any],
    trust: Mapping[str, Any],
    constituent_digests: Mapping[str, Any],
) -> bool:
    """Validate one group's semantic evidence, not merely its presence."""

    group_identity = identities.get(group)
    records = constituents.get(group)
    if not str(group_identity or "").strip() or not isinstance(records, (list, tuple)):
        return False
    if not records or group not in missing_evidence or group not in trust:
        return False
    if any(not isinstance(record, Mapping) for record in records):
        return False

    semantic_digests = tuple(
        str(record.get("semantic_digest", "")).strip() for record in records
    )
    if any(not digest for digest in semantic_digests):
        return False
    declared_digests = constituent_digests.get(group)
    if isinstance(declared_digests, str):
        declared_digests = (declared_digests,)
    if not declared_digests or set(map(str, declared_digests)) != set(semantic_digests):
        return False

    trust_class = str(trust.get(group) or "").strip().upper()
    if trust_class not in {"TRUSTED", TRUSTED_MARKET_TIME, "CAUSAL_ONLY"}:
        return False
    if missing_evidence.get(group):
        return False

    market_time_records = tuple(
        record
        for record in records
        if record.get("constituent_kind") != CAUSAL_DERIVED_CONSTITUENT
    )
    # Unknown kinds remain market-time-required; only the explicit causal-only
    # classification is exempt from the trusted market-time requirement.
    if any(
        record.get("constituent_kind") == MARKET_OBSERVATION_CONSTITUENT
        and record.get("trustworthy_market_time") is not True
        for record in market_time_records
    ):
        return False
    trustworthy_records = tuple(
        record
        for record in market_time_records
        if record.get("trustworthy_market_time") is True
    )
    if trust_class in {"TRUSTED", TRUSTED_MARKET_TIME} and len(
        trustworthy_records
    ) != len(market_time_records):
        return False
    market_oldest = market_newest = None
    if trustworthy_records:
        interval = intervals.get(group)
        if not isinstance(interval, Mapping):
            return False
        market_oldest = interval.get("oldest")
        market_newest = interval.get("newest")
        if market_oldest is None or market_newest is None:
            return False
    elif any(record.get("market_dependent") is True for record in records):
        return False

    try:
        expected_digest = canonical_group_digest(
            group_type=group,
            group_identity=str(group_identity),
            constituents=records,
            market_oldest=market_oldest,
            market_newest=market_newest,
            missing_evidence=missing_evidence.get(group, ()),
            trust_class=trust_class,
        )
    except (TypeError, ValueError):
        return False
    return str(digests.get(group) or "").strip() == expected_digest


def build_provenance_artifact(
    *,
    symbol: str,
    side: str = "BUY",
    candidate_evidence_identity: str = "",
    source_group_timestamps: Optional[Mapping[str, Any]] = None,
    source_group_digests: Optional[Mapping[str, str]] = None,
    source_group_intervals: Optional[Mapping[str, Any]] = None,
    source_group_closure_statuses: Optional[Mapping[str, Any]] = None,
    source_group_server_times: Optional[Mapping[str, Any]] = None,
    source_group_constituent_digests: Optional[Mapping[str, Any]] = None,
    source_group_identities: Optional[Mapping[str, Any]] = None,
    source_group_constituents: Optional[Mapping[str, Any]] = None,
    source_group_missing_evidence: Optional[Mapping[str, Any]] = None,
    source_group_trust: Optional[Mapping[str, Any]] = None,
    ticker_value: Optional[Any] = None,
    ticker_application_receipt_at: Optional[datetime] = None,
    decision_produced_at: Optional[datetime] = None,
    requested_quote_amount: Any = Decimal("0"),
    dynamic_policy_evidence: Optional[Mapping[str, Any]] = None,
    dynamic_risk_evidence: Optional[Mapping[str, Any]] = None,
    decision_dynamic_evidence: Optional[Mapping[str, Any]] = None,
    static_manifest_references: Optional[Mapping[str, Any]] = None,
    static_manifest_identity: Optional[Mapping[str, Any]] = None,
    recorded_at: Optional[datetime] = None,
) -> PreExecutionProvenanceArtifact:
    groups = dict(source_group_timestamps or {})
    digests = dict(source_group_digests or {})
    intervals = dict(source_group_intervals or {})
    identities = dict(source_group_identities or {})
    constituents = dict(source_group_constituents or {})
    missing_evidence = dict(source_group_missing_evidence or {})
    trust = dict(source_group_trust or {})
    statuses, server_times, constituent_digests = _digest_metadata(
        digests,
        source_group_closure_statuses,
        source_group_server_times,
        source_group_constituent_digests,
    )
    incomplete = (
        any(
            group not in groups
            or groups.get(group) is None
            or not digests.get(group)
            for group in REQUIRED_SOURCE_GROUPS
        )
        or any(
            not _dynamic_group_is_complete(
                group,
                digests=digests,
                intervals=intervals,
                identities=identities,
                constituents=constituents,
                missing_evidence=missing_evidence,
                trust=trust,
                constituent_digests=constituent_digests,
            )
            for group in REQUIRED_SOURCE_GROUPS
        )
        or any(
            status in {"CLOSED_UNPROVEN", "OPEN", "PROVENANCE_INCOMPLETE"}
            for status in statuses.values()
        )
        or not _has_trustworthy_price_closure(
            groups, statuses, server_times, constituent_digests
        )
    )
    raw_manifests = dict(static_manifest_references or {})
    manifests = _manifest_refs(raw_manifests)
    manifest_identity, manifests_valid = _manifest_binding_identity(raw_manifests)
    if static_manifest_identity:
        persisted_identity, persisted_valid = _manifest_binding_identity(
            static_manifest_identity
        )
        if persisted_valid:
            manifest_identity = persisted_identity
            manifests_valid = True
    binding_status = _binding_status(manifests, incomplete, manifests_valid)
    identity = {
        "contract_version": PROVENANCE_CONTRACT_VERSION,
        "candidate_evidence_identity": candidate_evidence_identity,
        "symbol": str(symbol).strip().upper(),
        "side": side,
        "source_group_timestamps": groups,
        "source_group_digests": digests,
        "source_group_intervals": intervals,
        "source_group_closure_statuses": statuses,
        "source_group_server_times": server_times,
        "source_group_constituent_digests": constituent_digests,
        "source_group_identities": identities,
        "source_group_constituents": constituents,
        "source_group_missing_evidence": missing_evidence,
        "source_group_trust": trust,
        "ticker_value": str(ticker_value) if ticker_value is not None else None,
        "ticker_application_receipt_at": ticker_application_receipt_at,
        "decision_produced_at": decision_produced_at,
        "requested_quote_amount": canonical_decimal(Decimal(str(requested_quote_amount))),
        "dynamic_policy_evidence": dict(dynamic_policy_evidence or {}),
        "dynamic_risk_evidence": dict(dynamic_risk_evidence or {}),
        "decision_dynamic_evidence": dict(decision_dynamic_evidence or {}),
        "static_manifest_references": manifests,
        "static_manifest_identity": manifest_identity,
        "binding_status": binding_status.value,
    }
    digest = canonical_semantic_digest(identity)
    return PreExecutionProvenanceArtifact(
        candidate_id=f"provenance-{digest}",
        symbol=symbol,
        side=side,
        source_group_timestamps=groups,
        source_group_digests=digests,
        source_group_intervals=intervals,
        source_group_closure_statuses=statuses,
        source_group_server_times=server_times,
        source_group_constituent_digests=constituent_digests,
        source_group_identities=identities,
        source_group_constituents=constituents,
        source_group_missing_evidence=missing_evidence,
        source_group_trust=trust,
        requested_quote_amount=Decimal(str(requested_quote_amount)),
        binding_status=binding_status,
        canonical_semantic_digest=digest,
        candidate_evidence_identity=candidate_evidence_identity,
        ticker_value=ticker_value,
        ticker_application_receipt_at=ticker_application_receipt_at,
        decision_produced_at=decision_produced_at,
        dynamic_policy_evidence=dynamic_policy_evidence or {},
        dynamic_risk_evidence=dynamic_risk_evidence or {},
        decision_dynamic_evidence=decision_dynamic_evidence or {},
        static_manifest_references=manifests,
        static_manifest_identity=manifest_identity,
        recorded_at=recorded_at,
    )
