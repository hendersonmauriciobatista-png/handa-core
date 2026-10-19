"""Narrow runtime wiring for durable pre-execution governance evidence."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Optional

from core.decision.decision_engine import BuySignal, MarketSnapshot
from core.execution.authority_digest import evaluation_request_digest, sha256_digest
from core.execution.live_order_models import LiveOrderIntent, OrderSide
from core.execution.pre_execution_candidate_evidence import (
    PreExecutionCandidateEvidence,
)
from core.execution.pre_execution_provenance_artifact import (
    PreExecutionProvenanceArtifact,
    build_provenance_artifact,
)
from core.execution.pre_execution_decision_evaluator import (
    PreExecutionDecisionEvaluator,
)
from core.governed_runtime_composition import (
    BootResult,
    GOVERNED_INFRASTRUCTURE_READY,
    OBSERVE_ONLY,
    RuntimeCompositionConfig,
)
from core.persistence.live_order_store import (
    LiveOrderStore,
    pre_execution_lineage_resource_scope,
)
from core.persistence.persistence_coordinator import PersistenceCoordinator
from core.persistence.governance_artifact_manifest_store import (
    GovernanceArtifactManifestStore,
    governance_artifact_manifest_resource_scope,
    validate_manifest_bindings,
)
from core.persistence.pre_execution_evaluation_store import (
    PreExecutionEvaluationPersistence,
    pre_execution_evaluation_resource_scope,
)
from core.persistence.pre_execution_provenance_store import (
    PreExecutionProvenanceStore,
    pre_execution_provenance_resource_scope,
)
from core.persistence.transaction_context import (
    InvalidCapabilityRequest,
    ResourceScope,
    UniqueConflict,
    VersionConflict,
)


OBSERVE_ONLY_NOT_EVALUATED = "OBSERVE_ONLY_NOT_EVALUATED"
TECHNICAL_FAILURE = "TECHNICAL_FAILURE"
LINEAGE_CONFLICT = "LINEAGE_CONFLICT"
INTENT_POLICY_CONTEXT_COMPAT = "handa-2b7-pre-execution-v1"
LINEAGE_CONTRACT_CONTEXT = "handa-2b8b-pre-execution-provenance-v1"
POLICY_CONTEXT = INTENT_POLICY_CONTEXT_COMPAT


@dataclass(frozen=True)
class PreExecutionRuntimeProposal:
    """Immutable candidate carrier created before slot analysis begins."""

    evidence: PreExecutionCandidateEvidence
    requested_quote_amount: Decimal
    slot_id: Optional[str] = None
    provenance_artifact: Optional[PreExecutionProvenanceArtifact] = None

    def __post_init__(self) -> None:
        if not isinstance(self.evidence, PreExecutionCandidateEvidence):
            raise TypeError("evidence must be PreExecutionCandidateEvidence")
        if not isinstance(self.requested_quote_amount, Decimal):
            raise TypeError("requested_quote_amount must be Decimal")
        if self.requested_quote_amount <= Decimal("0"):
            raise ValueError("requested_quote_amount must be greater than zero")
        if self.slot_id is not None and not str(self.slot_id).strip():
            raise ValueError("slot_id must be non-empty when provided")
        if self.evidence.side != "BUY":
            raise ValueError("pre-execution runtime proposals are BUY-only")
        if self.provenance_artifact is not None and not isinstance(
            self.provenance_artifact, PreExecutionProvenanceArtifact
        ):
            raise TypeError("provenance_artifact must be immutable provenance")

    @classmethod
    def from_buy_signal(
        cls, snapshot: MarketSnapshot, signal: BuySignal
    ) -> "PreExecutionRuntimeProposal":
        evidence = PreExecutionCandidateEvidence.from_buy_signal(snapshot, signal)
        requested_quote_amount = Decimal(str(signal.allocated_usdc))
        provenance = dict(evidence.provenance or {})
        artifact = build_provenance_artifact(
            symbol=evidence.symbol,
            side=evidence.side,
            candidate_evidence_identity=evidence.evidence_digest,
            source_group_timestamps=provenance.get("source_group_timestamps", {}),
            source_group_digests=provenance.get("source_group_digests", {}),
            source_group_intervals=provenance.get("source_group_intervals", {}),
            source_group_closure_statuses=provenance.get(
                "source_group_closure_statuses", {}
            ),
            source_group_server_times=provenance.get(
                "source_group_server_times", {}
            ),
            source_group_constituent_digests=provenance.get(
                "source_group_constituent_digests", {}
            ),
            source_group_identities=provenance.get("source_group_identities", {}),
            source_group_constituents=provenance.get("source_group_constituents", {}),
            source_group_missing_evidence=provenance.get(
                "source_group_missing_evidence", {}
            ),
            source_group_trust=provenance.get("source_group_trust", {}),
            ticker_value=provenance.get("ticker_value"),
            ticker_application_receipt_at=provenance.get(
                "ticker_application_receipt_at"
            ),
            decision_produced_at=evidence.produced_at,
            requested_quote_amount=requested_quote_amount,
            dynamic_policy_evidence=provenance.get("dynamic_policy_evidence", {}),
            dynamic_risk_evidence=provenance.get("dynamic_risk_evidence", {}),
            decision_dynamic_evidence=provenance.get("decision_dynamic_evidence", {}),
            # Static binding is supplied only by the active authority envelope
            # at the pre-execution boundary, never by the candidate snapshot.
        )
        return cls(
            evidence=evidence,
            requested_quote_amount=requested_quote_amount,
            provenance_artifact=artifact,
        )

    def bind_slot(self, slot_id: str) -> "PreExecutionRuntimeProposal":
        return PreExecutionRuntimeProposal(
            evidence=self.evidence,
            requested_quote_amount=self.requested_quote_amount,
            slot_id=str(slot_id),
            provenance_artifact=self.provenance_artifact,
        )


@dataclass(frozen=True)
class PreExecutionRuntimeIdentity:
    intent_id: str
    client_order_id: str
    attempt_id: str
    attempt_sequence: int
    evaluation_request_id: str
    evaluation_request_digest: str


@dataclass(frozen=True)
class PreExecutionRuntimeResult:
    disposition: str
    reason: str = ""
    intent_id: Optional[str] = None
    submission_attempt_id: Optional[str] = None
    evaluation_request_id: Optional[str] = None
    pre_execution_decision_id: Optional[str] = None
    decision_outcome: Optional[str] = None
    provenance_artifact_id: Optional[str] = None
    submission_authority: str = "NONE"
    execution_authority: str = "NONE"


class PreExecutionRuntimeCoordinator:
    """Own lineage/evaluator capabilities while never owning execution."""

    def __init__(
        self,
        config: RuntimeCompositionConfig,
        boot_result: BootResult,
        *,
        persistence_coordinator_factory: Callable[..., Any] = PersistenceCoordinator,
        evaluator_factory: Callable[[PreExecutionEvaluationPersistence], Any] = (
            PreExecutionDecisionEvaluator
        ),
    ) -> None:
        self._lineage_coordinator = None
        self._evaluation_coordinator = None
        self._provenance_coordinator = None
        self._lineage_store = None
        self._evaluator = None
        self._provenance_store = None
        self._manifest_store = None
        self._initialization_error: Optional[str] = None
        self._closed = False
        self._boot_result = boot_result

        if boot_result.posture != GOVERNED_INFRASTRUCTURE_READY:
            return

        try:
            if not config.database_url or config.database_identity is None:
                raise ValueError("governed runtime persistence configuration is missing")
            self._lineage_coordinator = persistence_coordinator_factory(
                config.database_url,
                config.database_identity,
                connect=config.connect,
                resource_scope=pre_execution_lineage_resource_scope(),
            )
            self._evaluation_coordinator = persistence_coordinator_factory(
                config.database_url,
                config.database_identity,
                connect=config.connect,
                resource_scope=pre_execution_evaluation_resource_scope(),
            )
            self._provenance_coordinator = persistence_coordinator_factory(
                config.database_url,
                config.database_identity,
                connect=config.connect,
                resource_scope=ResourceScope(
                    (
                        *pre_execution_provenance_resource_scope().resources,
                        *governance_artifact_manifest_resource_scope().resources,
                    )
                ),
            )
            self._lineage_coordinator.verify_ready()
            self._evaluation_coordinator.verify_ready()
            self._provenance_coordinator.verify_ready()
            self._lineage_store = LiveOrderStore(self._lineage_coordinator)
            self._evaluator = evaluator_factory(
                PreExecutionEvaluationPersistence(self._evaluation_coordinator)
            )
            self._provenance_store = PreExecutionProvenanceStore(
                self._provenance_coordinator
            )
            self._manifest_store = GovernanceArtifactManifestStore(
                self._provenance_coordinator
            )
        except Exception as exc:
            self._initialization_error = str(exc) or "PERSISTENCE_INITIALIZATION_FAILED"
            self.close()

    @staticmethod
    def derive_identity(
        proposal: PreExecutionRuntimeProposal,
        *,
        venue: str,
        account_scope: str,
        provenance_artifact: PreExecutionProvenanceArtifact,
    ) -> PreExecutionRuntimeIdentity:
        if proposal.slot_id is None:
            raise ValueError("pre-execution proposal must be bound to a slot")
        if not str(venue).strip() or not str(account_scope).strip():
            raise ValueError("venue and account_scope are required")
        if not isinstance(provenance_artifact, PreExecutionProvenanceArtifact):
            raise ValueError("bound provenance artifact is required")
        proposal_digest = sha256_digest(
            {
                "contract": LINEAGE_CONTRACT_CONTEXT,
                "candidate_id": proposal.evidence.candidate_id,
                "evidence_digest": proposal.evidence.evidence_digest,
                "symbol": proposal.evidence.symbol,
                "side": proposal.evidence.side,
                "requested_quote_amount": proposal.requested_quote_amount,
                "slot_id": proposal.slot_id,
                "venue": venue,
                "account_scope": account_scope,
                "provenance_semantic_digest": provenance_artifact.canonical_semantic_digest,
            }
        )
        intent_id = f"2b8b-intent-{proposal_digest}"
        client_order_id = f"2b8b-client-{proposal_digest}"
        attempt_sequence = 1
        attempt_id = f"2b8b-attempt-{sha256_digest({'intent_id': intent_id, 'attempt_sequence': attempt_sequence})}"
        request_digest = evaluation_request_digest(
            intent_id=intent_id,
            submission_attempt_id=attempt_id,
            upstream_evidence_digest_value=proposal.evidence.evidence_digest,
        )
        return PreExecutionRuntimeIdentity(
            intent_id=intent_id,
            client_order_id=client_order_id,
            attempt_id=attempt_id,
            attempt_sequence=attempt_sequence,
            evaluation_request_id=f"2b8b-eval-{request_digest}",
            evaluation_request_digest=request_digest,
        )

    def evaluate(
        self, proposal: Optional[PreExecutionRuntimeProposal]
    ) -> PreExecutionRuntimeResult:
        if self._boot_result.posture == OBSERVE_ONLY:
            return PreExecutionRuntimeResult(OBSERVE_ONLY_NOT_EVALUATED)
        if self._boot_result.posture != GOVERNED_INFRASTRUCTURE_READY:
            return PreExecutionRuntimeResult(
                TECHNICAL_FAILURE, reason="UNSUPPORTED_RUNTIME_POSTURE"
            )
        if self._initialization_error is not None:
            return PreExecutionRuntimeResult(
                TECHNICAL_FAILURE, reason="PERSISTENCE_INITIALIZATION_FAILED"
            )
        if not isinstance(proposal, PreExecutionRuntimeProposal):
            return PreExecutionRuntimeResult(TECHNICAL_FAILURE, reason="MALFORMED_PROPOSAL")

        try:
            envelope = self._boot_result.authority_snapshot.active_envelope
            if envelope is None:
                return PreExecutionRuntimeResult(
                    TECHNICAL_FAILURE, reason="ACTIVE_ENVELOPE_MISSING"
                )
            artifact = self.persist_provenance_artifact(proposal)
            identity = self.derive_identity(
                proposal,
                venue=envelope["venue"],
                account_scope=envelope["account_scope"],
                provenance_artifact=artifact,
            )
            intent = LiveOrderIntent(
                intent_id=identity.intent_id,
                client_order_id=identity.client_order_id,
                slot_id=str(proposal.slot_id),
                symbol=proposal.evidence.symbol,
                side=OrderSide.BUY,
                requested_quote_amount=proposal.requested_quote_amount,
                policy_context=INTENT_POLICY_CONTEXT_COMPAT,
            )
            lineage = self._lineage_store.ensure_pre_execution_lineage(
                intent=intent,
                venue=envelope["venue"],
                account_scope=envelope["account_scope"],
                attempt_id=identity.attempt_id,
                attempt_sequence=identity.attempt_sequence,
            )
            evaluated = self._evaluator.evaluate(
                evaluation_request_id=identity.evaluation_request_id,
                intent_id=lineage.intent["intent_id"],
                submission_attempt_id=lineage.attempt["attempt_id"],
                evidence=proposal.evidence,
            )
            return PreExecutionRuntimeResult(
                disposition=evaluated.disposition.value,
                reason=evaluated.reason,
                intent_id=identity.intent_id,
                submission_attempt_id=identity.attempt_id,
                evaluation_request_id=identity.evaluation_request_id,
                pre_execution_decision_id=evaluated.pre_execution_decision_id,
                decision_outcome=evaluated.decision_outcome,
                provenance_artifact_id=artifact.candidate_id if artifact else None,
            )
        except (InvalidCapabilityRequest, UniqueConflict, VersionConflict, ValueError) as exc:
            return PreExecutionRuntimeResult(
                LINEAGE_CONFLICT,
                reason=str(exc),
            )
        except Exception:
            return PreExecutionRuntimeResult(
                TECHNICAL_FAILURE,
                reason="PRE_EXECUTION_RUNTIME_FAILURE",
            )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for coordinator in (
            self._lineage_coordinator,
            self._evaluation_coordinator,
            self._provenance_coordinator,
        ):
            if coordinator is not None:
                try:
                    coordinator.close()
                except Exception:
                    pass
        self._lineage_coordinator = None
        self._evaluation_coordinator = None
        self._provenance_coordinator = None
        self._lineage_store = None
        self._evaluator = None
        self._provenance_store = None
        self._manifest_store = None

    def persist_provenance_artifact(
        self,
        proposal: Optional[PreExecutionRuntimeProposal],
        *,
        require_complete: bool = False,
    ) -> Optional[PreExecutionProvenanceArtifact]:
        """Persist provenance at the pre-analysis boundary in governed mode."""

        if self._boot_result.posture == OBSERVE_ONLY:
            return None
        if self._boot_result.posture != GOVERNED_INFRASTRUCTURE_READY:
            raise RuntimeError("unsupported runtime posture")
        if self._provenance_store is None or not isinstance(
            proposal, PreExecutionRuntimeProposal
        ):
            raise RuntimeError("provenance persistence is unavailable")
        artifact = proposal.provenance_artifact
        if artifact is None:
            raise RuntimeError("proposal provenance is missing")
        envelope = self._boot_result.authority_snapshot.active_envelope
        if envelope is None:
            raise RuntimeError("active authority envelope is missing")
        manifest_references = {
            name: envelope.get(f"{name.lower()}_manifest_id")
            for name in ("STRATEGY", "POLICY", "RISK", "CONFIGURATION", "FRESHNESS")
            if envelope.get(f"{name.lower()}_manifest_id")
        }
        normalized_manifests = None
        manifest_store = self._manifest_store
        if manifest_store is not None and len(manifest_references) == 5:
            try:
                rows = {
                    role: manifest_store.get_manifest(manifest_id)
                    for role, manifest_id in manifest_references.items()
                }
                if all(row is not None for row in rows.values()):
                    normalized_manifests = validate_manifest_bindings(rows)
            except Exception:
                normalized_manifests = None
        artifact = artifact.with_static_manifest_references(
            normalized_manifests or manifest_references
        )
        if require_complete and artifact.binding_status.value == "INCOMPLETE":
            raise RuntimeError("required provenance is incomplete")
        transaction = getattr(self._provenance_coordinator, "transaction", None)
        if not callable(transaction):
            raise RuntimeError("provenance transaction capability is unavailable")
        persist = getattr(self._provenance_store, "persist", None)
        if not callable(persist):
            raise RuntimeError("provenance persistence capability is unavailable")
        persist(artifact)
        return artifact

    def observe_provenance(self, proposal: Optional[PreExecutionRuntimeProposal]) -> int:
        """Observe-only path deliberately performs no writes or evaluator calls."""

        if self._boot_result.posture == OBSERVE_ONLY:
            return 0
        return int(isinstance(proposal, PreExecutionRuntimeProposal))

