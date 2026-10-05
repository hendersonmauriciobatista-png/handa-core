"""Frozen public contract for the future operational effect adapter.

This module defines data boundaries only.  It deliberately does not import
exchange, slot, accounting, ledger, or position-effect implementations and
does not perform reconciliation or operational effects.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.execution.execution_fact import ExecutionFact
    from core.execution.semantic_reconciliation_authority import (
        SemanticReconciliationDecision,
    )


class EffectType(str, Enum):
    """Explicit effect selection supplied by an external governed authority."""

    OPEN = "OPEN"
    REDUCE = "REDUCE"
    CLOSE = "CLOSE"


class OperationalEffectStatus(str, Enum):
    """Bounded outcomes exposed by the future adapter."""

    EFFECT_APPLIED = "EFFECT_APPLIED"
    FAILED_WITHOUT_EFFECT = "FAILED_WITHOUT_EFFECT"
    CONTAINED = "CONTAINED"
    PENDING = "PENDING"
    BLOCKED = "BLOCKED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


@dataclass(frozen=True, slots=True)
class EffectEligibility:
    """An already-made governed effect-selection decision."""

    effect_type: EffectType
    authority_decision_id: str
    reconciliation_context_id: str
    decision_sequence: int
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LogicalEffectIdentity:
    """Stable logical identity, distinct from observation and application IDs."""

    intent_id: str
    logical_effect_id: str


@dataclass(frozen=True, slots=True)
class PositionBinding:
    """Authoritative position binding supplied to the future adapter."""

    position_id: Optional[str] = None
    position_creation_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class OperationalApplicationBinding:
    """Caller-supplied durable application envelope for an effect."""

    effect_request_id: str
    application_attempt_id: str
    authority_contract_version: str
    claimant_id: str
    receipt: Mapping[str, Any]
    intended_quantity: Optional[Any] = None

    def __post_init__(self) -> None:
        for name in (
            "effect_request_id",
            "application_attempt_id",
            "authority_contract_version",
            "claimant_id",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(self.receipt, Mapping):
            raise TypeError("receipt must be a mapping")


@dataclass(frozen=True, slots=True)
class LogicalEffectBinding:
    """Immutable caller-supplied binding for one governed logical effect."""

    logical_identity: LogicalEffectIdentity
    effect_request_id: str
    effect_type: EffectType
    authority_decision_id: str
    reconciliation_context_id: str
    decision_sequence: int
    authority_contract_version: str


class LogicalBindingLookupDisposition(str, Enum):
    """Closed semantic vocabulary for read-only logical binding lookup."""

    NOT_FOUND = "NOT_FOUND"
    FOUND_VALID_BINDING = "FOUND_VALID_BINDING"
    FOUND_CONFLICTING_BINDING = "FOUND_CONFLICTING_BINDING"


class LogicalBindingWriteDisposition(str, Enum):
    """Closed semantic vocabulary for future logical binding writes."""

    CREATED_CANONICAL_BINDING = "CREATED_CANONICAL_BINDING"
    EXISTING_VALID_BINDING = "EXISTING_VALID_BINDING"
    CONFLICTING_BINDING = "CONFLICTING_BINDING"


@dataclass(frozen=True, slots=True)
class LogicalBindingLookupResult:
    """Immutable lookup evidence without lookup or persistence behavior."""

    disposition: LogicalBindingLookupDisposition
    binding: Optional[LogicalEffectBinding] = None

    def __post_init__(self) -> None:
        disposition = LogicalBindingLookupDisposition(self.disposition)
        if disposition is LogicalBindingLookupDisposition.NOT_FOUND:
            if self.binding is not None:
                raise ValueError("NOT_FOUND cannot carry a logical binding")
            return
        if self.binding is None:
            raise ValueError("found logical binding disposition requires binding")


@dataclass(frozen=True, slots=True)
class LogicalBindingWriteResult:
    """Immutable canonical-binding write evidence without write behavior."""

    disposition: LogicalBindingWriteDisposition
    binding: LogicalEffectBinding

    def __post_init__(self) -> None:
        LogicalBindingWriteDisposition(self.disposition)
        if self.binding is None:
            raise ValueError("logical binding write disposition requires binding")


@dataclass(frozen=True, slots=True)
class OperationalEffectRequest:
    """Immutable future adapter input; contains no effect authority itself."""

    execution_fact: "ExecutionFact"
    semantic_decision: "SemanticReconciliationDecision"
    reconciliation_context_id: str
    authority_decision_id: str
    decision_sequence: int
    evidence_ids: tuple[str, ...]
    effect_eligibility: EffectEligibility
    logical_effect_identity: LogicalEffectIdentity
    position_binding: PositionBinding
    application_binding: Optional[OperationalApplicationBinding] = None

    def __post_init__(self) -> None:
        eligibility = self.effect_eligibility
        if self.authority_decision_id != eligibility.authority_decision_id:
            raise ValueError("authority_decision_id cross-binding mismatch")
        if self.reconciliation_context_id != eligibility.reconciliation_context_id:
            raise ValueError("reconciliation_context_id cross-binding mismatch")
        if self.decision_sequence != eligibility.decision_sequence:
            raise ValueError("decision_sequence cross-binding mismatch")


@dataclass(frozen=True, slots=True)
class OperationalEffectResult:
    """Immutable bounded result without external, accounting, or slot authority."""

    status: OperationalEffectStatus
    effect_request_id: Optional[str] = None
    position_effect_result: Optional[Any] = None
    reconciliation_context_id: Optional[str] = None
    authority_decision_id: Optional[str] = None
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            self.status is OperationalEffectStatus.EFFECT_APPLIED
            and self.effect_request_id is None
        ):
            raise ValueError("EFFECT_APPLIED requires effect_request_id")
        if self.status is OperationalEffectStatus.FAILED_WITHOUT_EFFECT:
            if self.effect_request_id is None:
                raise ValueError(
                    "FAILED_WITHOUT_EFFECT requires effect_request_id"
                )
            if self.position_effect_result is not None:
                raise ValueError(
                    "FAILED_WITHOUT_EFFECT cannot contain position_effect_result"
                )


class OperationalEffectAdapter:
    """Bridge applicable governed requests to an injected coordinator."""

    def __init__(self, coordinator: Any = None) -> None:
        self._coordinator = coordinator

    def apply(self, request: OperationalEffectRequest) -> OperationalEffectResult:
        if request.semantic_decision.state in {"PENDING", "BLOCKED"}:
            return OperationalEffectResult(
                status=OperationalEffectStatus(request.semantic_decision.state),
                reconciliation_context_id=request.reconciliation_context_id,
                authority_decision_id=request.authority_decision_id,
                evidence_ids=tuple(request.evidence_ids),
            )
        if not hasattr(request.execution_fact, "execution_extent_identity") and not hasattr(
            request.execution_fact, "extent_certainty"
        ):
            raise NotImplementedError(
                "operational effect application is not implemented"
            )
        if not self._has_applicable_extent(request.execution_fact):
            return OperationalEffectResult(
                status=OperationalEffectStatus.OUTCOME_UNKNOWN,
                reconciliation_context_id=request.reconciliation_context_id,
                authority_decision_id=request.authority_decision_id,
                evidence_ids=tuple(request.evidence_ids),
            )
        application = request.application_binding
        if application is None:
            return self._contained(request)
        if not self._receipt_matches_fact(request.execution_fact, application.receipt):
            return self._contained(request)
        if self._coordinator is None:
            raise NotImplementedError(
                "operational effect application coordinator is not configured"
            )

        binding = LogicalEffectBinding(
            logical_identity=request.logical_effect_identity,
            effect_request_id=application.effect_request_id,
            effect_type=request.effect_eligibility.effect_type,
            authority_decision_id=request.authority_decision_id,
            reconciliation_context_id=request.reconciliation_context_id,
            decision_sequence=request.decision_sequence,
            authority_contract_version=application.authority_contract_version,
        )
        position_id = (
            request.position_binding.position_id
            if request.effect_eligibility.effect_type is not EffectType.OPEN
            else None
        )
        try:
            outcome = self._coordinator.apply(
                logical_binding=binding,
                application_attempt_id=application.application_attempt_id,
                claimant_id=application.claimant_id,
                position_id=position_id,
                position_binding=request.position_binding,
                receipt=application.receipt,
                applied_quantity=request.execution_fact.executed_base_qty,
                intended_quantity=application.intended_quantity,
                external_order_id=request.execution_fact.external_order_id,
                symbol=request.execution_fact.symbol,
                evidence_ids=tuple(request.evidence_ids),
            )
        except Exception:
            return self._contained(request)
        return self._translate_coordinator_result(request, application, outcome)

    @staticmethod
    def _has_applicable_extent(execution_fact: Any) -> bool:
        extent = getattr(execution_fact, "execution_extent_identity", None)
        certainty = getattr(execution_fact, "extent_certainty", None)
        semantics = getattr(execution_fact, "quantity_semantics", None)
        if not isinstance(extent, str) or not extent.strip():
            return False
        if getattr(certainty, "value", certainty) == "UNKNOWN":
            return False
        return getattr(semantics, "value", semantics) == "NON_OVERLAPPING_EXTENT"

    @staticmethod
    def _receipt_matches_fact(execution_fact: Any, receipt: Mapping[str, Any]) -> bool:
        extent = receipt.get("execution_extent_identity")
        if not isinstance(extent, str) or not extent.strip():
            return False
        if extent != execution_fact.execution_extent_identity:
            return False
        external_order_id = getattr(execution_fact, "external_order_id", None)
        if receipt.get("order_id") is not None and external_order_id is not None:
            if str(receipt["order_id"]) != str(external_order_id):
                return False
        if receipt.get("executed_base_qty") is not None:
            if str(receipt["executed_base_qty"]) != str(
                execution_fact.executed_base_qty
            ):
                return False
        return True

    @staticmethod
    def _contained(request: OperationalEffectRequest) -> OperationalEffectResult:
        return OperationalEffectResult(
            status=OperationalEffectStatus.CONTAINED,
            reconciliation_context_id=request.reconciliation_context_id,
            authority_decision_id=request.authority_decision_id,
            evidence_ids=tuple(request.evidence_ids),
        )

    @classmethod
    def _translate_coordinator_result(
        cls,
        request: OperationalEffectRequest,
        application: OperationalApplicationBinding,
        outcome: Any,
    ) -> OperationalEffectResult:
        classification = getattr(outcome, "classification", None)
        classification = getattr(classification, "value", classification)
        if classification == "FAILED_WITHOUT_EFFECT":
            return OperationalEffectResult(
                status=OperationalEffectStatus.FAILED_WITHOUT_EFFECT,
                effect_request_id=application.effect_request_id,
                reconciliation_context_id=request.reconciliation_context_id,
                authority_decision_id=request.authority_decision_id,
                evidence_ids=tuple(request.evidence_ids),
            )
        if classification == "RECOVERY_REQUIRED":
            return cls._contained(request)

        position_result = getattr(outcome, "position_effect_result", None)
        if position_result is None and all(
            hasattr(outcome, field)
            for field in ("effect_request_id", "effect_type", "execution_extent_identity")
        ):
            position_result = outcome
        if position_result is None:
            return cls._contained(request)
        return OperationalEffectResult(
            status=OperationalEffectStatus.EFFECT_APPLIED,
            effect_request_id=application.effect_request_id,
            position_effect_result=position_result,
            reconciliation_context_id=request.reconciliation_context_id,
            authority_decision_id=request.authority_decision_id,
            evidence_ids=tuple(request.evidence_ids),
        )


# Frozen invariants:
# - RESOLVED is not execution authorization.
# - Missing eligibility or execution extent blocks application.
# - UNKNOWN never becomes an effect.
# - Future effect_request_id binding must be stable for one logical effect.
# - REDUCE/CLOSE require authoritative position_id.
# - OPEN requires stable position_creation_id.
# - Partial execution never implies CLOSE.


__all__ = [
    "EffectEligibility",
    "EffectType",
    "OperationalApplicationBinding",
    "LogicalEffectBinding",
    "LogicalEffectIdentity",
    "LogicalBindingLookupDisposition",
    "LogicalBindingLookupResult",
    "LogicalBindingWriteDisposition",
    "LogicalBindingWriteResult",
    "OperationalEffectAdapter",
    "OperationalEffectRequest",
    "OperationalEffectResult",
    "OperationalEffectStatus",
    "PositionBinding",
]
