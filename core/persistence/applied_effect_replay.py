"""Read-only reconstruction of durable APPLIED position effects."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from core.execution.operational_effect_adapter import LogicalEffectBinding
from core.position.position_effect_authority import PositionEffectResult


class AppliedEffectReplayError(RuntimeError):
    """Stable fail-closed classifications for APPLIED reconstruction."""

    def __init__(self, classification: str, detail: str = "") -> None:
        self.classification = classification
        message = classification if not detail else f"{classification}: {detail}"
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class AppliedEffectReplayRecord:
    """Immutable evidence reconstructed from durable read-only sources."""

    effect_request_id: str
    applied_effect_id: str
    application_attempt_id: str
    position_effect_result: PositionEffectResult
    authority_decision_id: str
    reconciliation_context_id: str
    decision_sequence: int
    authority_contract_version: str
    evidence_ids: tuple[str, ...] = ()


def reconstruct_applied_effect(
    *, logical_binding: LogicalEffectBinding, cursor: Any
) -> AppliedEffectReplayRecord:
    """Reconstruct one coherent APPLIED effect without performing any write."""

    _require_binding(logical_binding)
    request = _load_request_and_binding(cursor, logical_binding)
    if request["current_state"] != "APPLIED":
        raise AppliedEffectReplayError(
            "NOT_APPLICABLE", "effect request is not APPLIED"
        )

    applied = _load_applied_effect(cursor, logical_binding.effect_request_id)
    _validate_attempt(cursor, request, applied)
    recovery_applied = _validate_application_lineage(
        cursor,
        logical_binding.effect_request_id,
        applied["application_attempt_id"],
    )

    position_event = _load_position_event(
        cursor, logical_binding.effect_request_id
    )
    if position_event is None:
        if recovery_applied:
            raise AppliedEffectReplayError(
                "APPLIED_POSITION_RESULT_NOT_RECONSTRUCTABLE",
                "recovery reached APPLIED without position-effect history",
            )
        raise AppliedEffectReplayError(
            "DURABLE_APPLIED_RESULT_MISSING",
            "position-effect history is required for reconstruction",
        )

    _validate_position_lineage(
        cursor,
        logical_binding,
        request,
        applied,
        position_event,
    )
    position_receipt = _load_position_receipt(cursor, position_event["receipt_id"])
    _validate_execution_extent(position_event, position_receipt)
    position_result = _reconstruct_position_result(position_event)

    return AppliedEffectReplayRecord(
        effect_request_id=logical_binding.effect_request_id,
        applied_effect_id=applied["applied_effect_id"],
        application_attempt_id=applied["application_attempt_id"],
        position_effect_result=position_result,
        authority_decision_id=request["authority_decision_id"],
        reconciliation_context_id=request["reconciliation_context_id"],
        decision_sequence=request["decision_sequence"],
        authority_contract_version=request["authority_contract_version"],
        evidence_ids=tuple(applied["evidence_ids"] or ()),
    )


def _require_binding(binding: LogicalEffectBinding) -> None:
    if not isinstance(binding, LogicalEffectBinding):
        raise AppliedEffectReplayError(
            "NOT_APPLICABLE", "canonical LogicalEffectBinding is required"
        )


def _load_request_and_binding(cursor: Any, binding: LogicalEffectBinding) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT er.effect_request_id, er.intent_id, er.logical_effect_id,
               er.effect_type, er.reconciliation_context_id,
               er.current_state, er.current_attempt_id,
               ab.authority_decision_id, ab.intent_id,
               ab.reconciliation_context_id, ab.decision_sequence,
               ab.authority_contract_version
        FROM handa_live.effect_request er
        LEFT JOIN handa_live.authority_binding ab
          ON ab.effect_request_id = er.effect_request_id
        WHERE er.effect_request_id=%s
        """,
        (binding.effect_request_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise AppliedEffectReplayError(
            "NOT_APPLICABLE", "canonical effect request does not exist"
        )
    request = dict(
        zip(
            (
                "effect_request_id",
                "intent_id",
                "logical_effect_id",
                "effect_type",
                "reconciliation_context_id",
                "current_state",
                "current_attempt_id",
                "authority_decision_id",
                "authority_binding_intent_id",
                "authority_binding_context_id",
                "decision_sequence",
                "authority_contract_version",
            ),
            row,
        )
    )
    expected = {
        "effect_request_id": binding.effect_request_id,
        "intent_id": binding.logical_identity.intent_id,
        "logical_effect_id": binding.logical_identity.logical_effect_id,
        "effect_type": binding.effect_type.value,
        "reconciliation_context_id": binding.reconciliation_context_id,
        "authority_decision_id": binding.authority_decision_id,
        "authority_binding_intent_id": binding.logical_identity.intent_id,
        "authority_binding_context_id": binding.reconciliation_context_id,
        "decision_sequence": binding.decision_sequence,
        "authority_contract_version": binding.authority_contract_version,
    }
    if any(request[key] != value for key, value in expected.items()):
        raise AppliedEffectReplayError(
            "DURABLE_DATA_CONTRADICTION",
            "canonical request and authority binding disagree",
        )
    return request


def _load_applied_effect(cursor: Any, effect_request_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT applied_effect_id, application_attempt_id, evidence_ids
        FROM handa_live.applied_effect
        WHERE effect_request_id=%s
        """,
        (effect_request_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise AppliedEffectReplayError(
            "DURABLE_APPLIED_RESULT_MISSING",
            "durable APPLIED evidence is missing",
        )
    return {
        "applied_effect_id": row[0],
        "application_attempt_id": row[1],
        "evidence_ids": row[2],
    }


def _validate_attempt(
    cursor: Any, request: dict[str, Any], applied: dict[str, Any]
) -> None:
    attempt_id = applied["application_attempt_id"]
    if request["current_attempt_id"] != attempt_id:
        raise AppliedEffectReplayError(
            "DURABLE_DATA_CONTRADICTION",
            "current request attempt disagrees with applied evidence",
        )
    cursor.execute(
        """
        SELECT application_attempt_id, effect_request_id, attempt_state
        FROM handa_live.application_attempt
        WHERE application_attempt_id=%s AND effect_request_id=%s
        """,
        (attempt_id, request["effect_request_id"]),
    )
    row = cursor.fetchone()
    if row is None or row[2] != "APPLIED":
        raise AppliedEffectReplayError(
            "DURABLE_DATA_CONTRADICTION",
            "application attempt lineage is not APPLIED",
        )


def _validate_application_lineage(
    cursor: Any, effect_request_id: str, attempt_id: str
) -> bool:
    cursor.execute(
        """
        SELECT previous_state, next_state, event_kind, application_attempt_id
        FROM handa_live.lifecycle_event
        WHERE effect_request_id=%s
        ORDER BY event_sequence
        """,
        (effect_request_id,),
    )
    lifecycle_events = tuple(cursor.fetchall())
    cursor.execute(
        """
        SELECT previous_state, resulting_state, application_attempt_id
        FROM handa_live.recovery_event
        WHERE effect_request_id=%s
        ORDER BY recovery_event_id
        """,
        (effect_request_id,),
    )
    recovery_events = tuple(cursor.fetchall())

    recovery_applied = False
    for previous, resulting, recovery_attempt in recovery_events:
        if (
            previous == "OUTCOME_UNKNOWN"
            and resulting == "APPLIED"
            and recovery_attempt == attempt_id
        ):
            recovery_applied = True
        else:
            raise AppliedEffectReplayError(
                "DURABLE_DATA_CONTRADICTION",
                "recovery lineage disagrees with applied attempt",
            )

    normal_applied = any(
        next_state == "APPLIED"
        and event_kind == "APPLIED"
        and event_attempt == attempt_id
        for _, next_state, event_kind, event_attempt in lifecycle_events
    )
    recovery_lifecycle = any(
        previous == "OUTCOME_UNKNOWN"
        and next_state == "APPLIED"
        and event_kind == "RECOVERY"
        and event_attempt == attempt_id
        for previous, next_state, event_kind, event_attempt in lifecycle_events
    )
    if recovery_applied and not recovery_lifecycle:
        raise AppliedEffectReplayError(
            "DURABLE_DATA_CONTRADICTION",
            "recovery event is missing its lifecycle lineage",
        )
    if not normal_applied and not recovery_applied:
        raise AppliedEffectReplayError(
            "DURABLE_DATA_CONTRADICTION",
            "APPLIED state has no matching application lineage",
        )
    return recovery_applied


def _load_position_event(cursor: Any, effect_request_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT position_id, intent_id, effect_type, effect_request_id,
               application_attempt_id, external_order_identity,
               execution_extent_identity, receipt_id, previous_quantity,
               applied_quantity, resulting_quantity, reconciliation_context_id,
               semantic_decision_id, decision_sequence,
               authority_contract_version
        FROM handa_live.position_effect_event
        WHERE effect_request_id=%s
        """,
        (effect_request_id,),
    )
    rows = cursor.fetchall()
    if len(rows) > 1:
        raise AppliedEffectReplayError(
            "DURABLE_DATA_CONTRADICTION",
            "multiple historical position effects share one request",
        )
    if not rows:
        return None
    row = rows[0]
    return dict(
        zip(
            (
                "position_id",
                "intent_id",
                "effect_type",
                "effect_request_id",
                "application_attempt_id",
                "external_order_identity",
                "execution_extent_identity",
                "receipt_id",
                "previous_quantity",
                "applied_quantity",
                "resulting_quantity",
                "reconciliation_context_id",
                "semantic_decision_id",
                "decision_sequence",
                "authority_contract_version",
            ),
            row,
        )
    )


def _validate_position_lineage(
    cursor: Any,
    binding: LogicalEffectBinding,
    request: dict[str, Any],
    applied: dict[str, Any],
    event: dict[str, Any],
) -> None:
    expected = {
        "intent_id": binding.logical_identity.intent_id,
        "effect_type": binding.effect_type.value,
        "effect_request_id": binding.effect_request_id,
        "application_attempt_id": applied["application_attempt_id"],
        "reconciliation_context_id": binding.reconciliation_context_id,
        "semantic_decision_id": binding.authority_decision_id,
        "decision_sequence": binding.decision_sequence,
        "authority_contract_version": binding.authority_contract_version,
    }
    if any(event[key] != value for key, value in expected.items()):
        raise AppliedEffectReplayError(
            "DURABLE_DATA_CONTRADICTION",
            "position-effect history disagrees with canonical lineage",
        )
    if request["intent_id"] != event["intent_id"]:
        raise AppliedEffectReplayError(
            "DURABLE_DATA_CONTRADICTION",
            "position-effect intent disagrees with request identity",
        )
    effect_type = event["effect_type"]
    previous = Decimal(event["previous_quantity"])
    applied_quantity = Decimal(event["applied_quantity"])
    resulting = Decimal(event["resulting_quantity"])
    valid = (
        effect_type == "OPEN"
        and previous == 0
        and resulting == applied_quantity
    ) or (
        effect_type == "REDUCE"
        and applied_quantity < previous
        and resulting == previous - applied_quantity
        and resulting > 0
    ) or (
        effect_type == "CLOSE"
        and applied_quantity == previous
        and resulting == 0
    )
    if not valid:
        raise AppliedEffectReplayError(
            "DURABLE_DATA_CONTRADICTION",
            "position-effect quantities are internally inconsistent",
        )


def _load_position_receipt(cursor: Any, receipt_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT receipt_id, external_order_identity,
               execution_extent_identity, executed_base_quantity
        FROM handa_live.position_receipt
        WHERE receipt_id=%s
        """,
        (receipt_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise AppliedEffectReplayError(
            "DURABLE_APPLIED_RESULT_MISSING",
            "position receipt evidence is missing",
        )
    return {
        "receipt_id": row[0],
        "external_order_identity": row[1],
        "execution_extent_identity": row[2],
        "executed_base_quantity": row[3],
    }


def _validate_execution_extent(event: dict[str, Any], receipt: dict[str, Any]) -> None:
    if (
        event["receipt_id"] != receipt["receipt_id"]
        or event["external_order_identity"] != receipt["external_order_identity"]
        or event["execution_extent_identity"]
        != receipt["execution_extent_identity"]
        or Decimal(event["applied_quantity"])
        != Decimal(receipt["executed_base_quantity"])
    ):
        raise AppliedEffectReplayError(
            "DURABLE_DATA_CONTRADICTION",
            "position receipt disagrees with historical execution extent",
        )


def _reconstruct_position_result(event: dict[str, Any]) -> PositionEffectResult:
    state = "CLOSED" if event["effect_type"] == "CLOSE" else "ACTIVE"
    return PositionEffectResult(
        position_id=event["position_id"],
        effect_type=event["effect_type"],
        previous_quantity=Decimal(event["previous_quantity"]),
        applied_quantity=Decimal(event["applied_quantity"]),
        resulting_quantity=Decimal(event["resulting_quantity"]),
        state=state,
        effect_request_id=event["effect_request_id"],
        execution_extent_identity=event["execution_extent_identity"],
    )


__all__ = [
    "AppliedEffectReplayError",
    "AppliedEffectReplayRecord",
    "reconstruct_applied_effect",
]
