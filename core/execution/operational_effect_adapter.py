"""Frozen public contract for the future operational effect adapter.

This module defines data boundaries only.  It deliberately does not import
exchange, slot, accounting, ledger, or position-effect implementations and
does not perform reconciliation or operational effects.
"""

from __future__ import annotations

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


class OperationalEffectAdapter:
    """Future orchestration boundary; operational behavior is not implemented."""

    def apply(self, request: OperationalEffectRequest) -> OperationalEffectResult:
        del request
        raise NotImplementedError(
            "operational effect application is not implemented"
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
    "LogicalEffectIdentity",
    "OperationalEffectAdapter",
    "OperationalEffectRequest",
    "OperationalEffectResult",
    "OperationalEffectStatus",
    "PositionBinding",
]
