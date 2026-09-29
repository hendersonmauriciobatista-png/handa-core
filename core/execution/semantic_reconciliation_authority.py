"""Pure semantic reconciliation classification boundary.

This module classifies governed evidence only.  It does not acquire evidence,
persist decisions, or authorize operational effects.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


@dataclass(frozen=True)
class GovernedSemanticDecisionInput:
    decision_scope: str
    intent_id: str
    symbol: str
    order_id: str | None
    client_order_id: str | None
    propositions: Mapping[str, Any]
    evidence: tuple[Mapping[str, Any], ...]
    normalized_state: str | None = None

    def __post_init__(self):
        if self.decision_scope not in {"ORDER_OUTCOME", "QUANTITY_DEPENDENT"}:
            raise ValueError(f"unsupported semantic decision scope: {self.decision_scope!r}")

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any]
    ) -> "GovernedSemanticDecisionInput":
        return cls(
            decision_scope=value["decision_scope"],
            intent_id=value["intent_id"],
            symbol=value["symbol"],
            order_id=value.get("order_id"),
            client_order_id=value.get("client_order_id"),
            propositions=dict(value.get("propositions", {})),
            evidence=tuple(dict(item) for item in value.get("evidence", ())),
            normalized_state=value.get("normalized_state"),
        )


@dataclass(frozen=True)
class SemanticEvidenceLineage:
    evidence_ids: list[str]


@dataclass(frozen=True)
class SemanticReconciliationDecision:
    state: str
    propositions: Mapping[str, Any]
    lineage: SemanticEvidenceLineage
    side_effects: tuple[()] = ()
    operations: tuple[()] = ()

    def __post_init__(self):
        if not isinstance(self.state, str) or self.state not in {
            "RESOLVED",
            "PENDING",
            "BLOCKED",
        }:
            raise ValueError(f"unsupported semantic reconciliation state: {self.state!r}")


class SemanticReconciliationAuthority:
    """Deterministically classify a governed semantic decision input."""

    @staticmethod
    def evaluate(
        value: GovernedSemanticDecisionInput,
    ) -> SemanticReconciliationDecision:
        propositions = dict(value.propositions)
        evidence_ids = tuple(
            item["evidence_id"]
            for item in value.evidence
            if item.get("evidence_id") is not None
        )

        if SemanticReconciliationAuthority._has_identity_conflict(
            value, value.evidence
        ) or SemanticReconciliationAuthority._has_material_contradiction(
            propositions, value.evidence
        ):
            state = "BLOCKED"
        elif SemanticReconciliationAuthority._has_correlated_rejection(
            value, value.evidence
        ):
            propositions["no_effect_confirmed"] = True
            state = "RESOLVED"
        elif SemanticReconciliationAuthority._requires_unknown_resolution(
            value, propositions
        ):
            state = "PENDING"
        elif value.normalized_state == "NOT_REQUIRED" and not evidence_ids:
            # A normalizer label is not authority evidence by itself.
            state = "PENDING"
        else:
            state = "RESOLVED"

        return SemanticReconciliationDecision(
            state=state,
            propositions=propositions,
            lineage=SemanticEvidenceLineage(evidence_ids=list(evidence_ids)),
        )

    @staticmethod
    def _has_identity_conflict(
        value: GovernedSemanticDecisionInput,
        evidence: tuple[Mapping[str, Any], ...],
    ) -> bool:
        expected = {
            "intent_id": value.intent_id,
            "symbol": value.symbol,
            "order_id": value.order_id,
            "client_order_id": value.client_order_id,
        }
        for item in evidence:
            for field, expected_value in expected.items():
                observed_value = item.get(field)
                if (
                    observed_value is not None
                    and expected_value is not None
                    and observed_value != expected_value
                ):
                    return True
        return False

    @staticmethod
    def _has_correlated_rejection(
        value: GovernedSemanticDecisionInput,
        evidence: tuple[Mapping[str, Any], ...],
    ) -> bool:
        return any(
            item.get("status") == "REJECTED"
            and item.get("source") in {
                "exchange_order_query",
                "user_data_stream",
                "exchange_order_response",
            }
            and item.get("evidence_id") is not None
            and not SemanticReconciliationAuthority._has_identity_conflict(
                value, (item,)
            )
            for item in evidence
        )

    @staticmethod
    def _has_material_contradiction(
        propositions: Mapping[str, Any],
        evidence: tuple[Mapping[str, Any], ...],
    ) -> bool:
        if propositions.get("execution_occurred") == "CONTRADICTORY":
            return True

        statuses = {item.get("status") for item in evidence}
        has_positive_trade = any(
            item.get("source") == "trade"
            and item.get("trade_qty") not in (None, "0", 0, "0.0", "0.00")
            for item in evidence
        )
        has_positive_executed_qty = any(
            SemanticReconciliationAuthority._is_positive_quantity(
                item.get("executed_qty")
            )
            for item in evidence
        )
        has_zero_terminal = any(
            item.get("status") in {"CANCELED", "EXPIRED", "EXPIRED_IN_MATCH"}
            and item.get("executed_qty") in ("0", 0, "0.0", "0.00")
            for item in evidence
        )
        has_rejected = "REJECTED" in statuses
        return (
            has_rejected and (has_positive_trade or has_positive_executed_qty)
        ) or (has_positive_trade and has_zero_terminal)

    @staticmethod
    def _is_positive_quantity(value: Any) -> bool:
        if value is None:
            return False
        try:
            return Decimal(str(value)) > 0
        except (InvalidOperation, ValueError):
            return False

    @staticmethod
    def _requires_unknown_resolution(
        value: GovernedSemanticDecisionInput,
        propositions: Mapping[str, Any],
    ) -> bool:
        sources = {item.get("source") for item in value.evidence}
        if sources & {"timeout", "ambiguous_transport"}:
            return True

        if propositions.get("execution_occurred") == "UNKNOWN":
            return True

        if propositions.get("order_outcome_terminal") == "UNKNOWN":
            return True

        return (
            value.decision_scope == "QUANTITY_DEPENDENT"
            and propositions.get("execution_extent") == "UNKNOWN"
        )
