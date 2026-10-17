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
from core.persistence.pre_execution_evaluation_store import (
    PreExecutionEvaluationPersistence,
    pre_execution_evaluation_resource_scope,
)
from core.persistence.transaction_context import (
    InvalidCapabilityRequest,
    UniqueConflict,
    VersionConflict,
)


OBSERVE_ONLY_NOT_EVALUATED = "OBSERVE_ONLY_NOT_EVALUATED"
TECHNICAL_FAILURE = "TECHNICAL_FAILURE"
LINEAGE_CONFLICT = "LINEAGE_CONFLICT"
POLICY_CONTEXT = "handa-2b7-pre-execution-v1"


@dataclass(frozen=True)
class PreExecutionRuntimeProposal:
    """Immutable candidate carrier created before slot analysis begins."""

    evidence: PreExecutionCandidateEvidence
    requested_quote_amount: Decimal
    slot_id: Optional[str] = None

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

    @classmethod
    def from_buy_signal(
        cls, snapshot: MarketSnapshot, signal: BuySignal
    ) -> "PreExecutionRuntimeProposal":
        return cls(
            evidence=PreExecutionCandidateEvidence.from_buy_signal(snapshot, signal),
            requested_quote_amount=Decimal(str(signal.allocated_usdc)),
        )

    def bind_slot(self, slot_id: str) -> "PreExecutionRuntimeProposal":
        return PreExecutionRuntimeProposal(
            evidence=self.evidence,
            requested_quote_amount=self.requested_quote_amount,
            slot_id=str(slot_id),
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
        self._lineage_store = None
        self._evaluator = None
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
            self._lineage_coordinator.verify_ready()
            self._evaluation_coordinator.verify_ready()
            self._lineage_store = LiveOrderStore(self._lineage_coordinator)
            self._evaluator = evaluator_factory(
                PreExecutionEvaluationPersistence(self._evaluation_coordinator)
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
    ) -> PreExecutionRuntimeIdentity:
        if proposal.slot_id is None:
            raise ValueError("pre-execution proposal must be bound to a slot")
        if not str(venue).strip() or not str(account_scope).strip():
            raise ValueError("venue and account_scope are required")
        proposal_digest = sha256_digest(
            {
                "contract": POLICY_CONTEXT,
                "candidate_id": proposal.evidence.candidate_id,
                "evidence_digest": proposal.evidence.evidence_digest,
                "symbol": proposal.evidence.symbol,
                "side": proposal.evidence.side,
                "requested_quote_amount": proposal.requested_quote_amount,
                "slot_id": proposal.slot_id,
                "venue": venue,
                "account_scope": account_scope,
            }
        )
        intent_id = f"2b7-intent-{proposal_digest}"
        client_order_id = f"2b7-client-{proposal_digest}"
        attempt_sequence = 1
        attempt_id = f"2b7-attempt-{sha256_digest({'intent_id': intent_id, 'attempt_sequence': attempt_sequence})}"
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
            evaluation_request_id=f"2b7-eval-{request_digest}",
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
            identity = self.derive_identity(
                proposal,
                venue=envelope["venue"],
                account_scope=envelope["account_scope"],
            )
            intent = LiveOrderIntent(
                intent_id=identity.intent_id,
                client_order_id=identity.client_order_id,
                slot_id=str(proposal.slot_id),
                symbol=proposal.evidence.symbol,
                side=OrderSide.BUY,
                requested_quote_amount=proposal.requested_quote_amount,
                policy_context=POLICY_CONTEXT,
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
        for coordinator in (self._lineage_coordinator, self._evaluation_coordinator):
            if coordinator is not None:
                try:
                    coordinator.close()
                except Exception:
                    pass
        self._lineage_coordinator = None
        self._evaluation_coordinator = None
        self._lineage_store = None
        self._evaluator = None

