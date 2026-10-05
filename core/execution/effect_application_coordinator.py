"""Transactional orchestration for one already-authorized effect application.

This module coordinates existing authorities. It does not decide whether an
effect is allowed, create identities, mutate positions directly, reconstruct
history, or interact with an external venue.
"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Optional

from core.execution.operational_effect_adapter import (
    EffectType,
    LogicalBindingLookupDisposition,
    LogicalEffectBinding,
    PositionBinding,
)
from core.persistence.applied_effect_replay import (
    AppliedEffectReplayRecord,
    reconstruct_applied_effect,
)
from core.persistence.effect_application_ledger import (
    EffectApplicationLedger,
    EffectApplicationLedgerError,
)
from core.position.position_effect_authority import (
    PositionEffectAuthority,
    PositionEffectResult,
)


@dataclass(frozen=True, slots=True)
class EffectApplicationCoordinatorResult:
    """Bounded result for terminal states that cannot be applied here."""

    effect_request_id: str
    classification: str
    application_attempt_id: Optional[str] = None


class EffectApplicationCoordinatorError(RuntimeError):
    """Raised when coordination must fail closed."""


class EffectApplicationCoordinator:
    """Coordinate ledger and position authorities inside one transaction."""

    def __init__(
        self,
        *,
        ledger: EffectApplicationLedger,
        position_authority: PositionEffectAuthority,
        replay: Callable[..., AppliedEffectReplayRecord] = reconstruct_applied_effect,
    ) -> None:
        self._ledger = ledger
        self._position_authority = position_authority
        self._replay = replay

    def apply(
        self,
        *,
        logical_binding: LogicalEffectBinding,
        application_attempt_id: str,
        claimant_id: str,
        position_id: Optional[str],
        receipt: Mapping[str, Any],
        applied_quantity: Any,
        intended_quantity: Any = None,
        external_order_id: Optional[str] = None,
        symbol: str = "",
        evidence_ids: Iterable[str] = (),
        position_binding: Optional[PositionBinding] = None,
        position_creation_id: Optional[str] = None,
    ) -> PositionEffectResult | AppliedEffectReplayRecord | EffectApplicationCoordinatorResult:
        """Apply or replay one canonical logical effect.

        The caller supplies both the candidate request identity embedded in
        ``logical_binding`` and the application attempt identity. All writes
        for a new application use the ledger-owned transaction scope.
        """

        self._validate_input(logical_binding, application_attempt_id)
        resolved_position_id = self._resolve_position_id(
            logical_binding.effect_type,
            position_id=position_id,
            position_binding=position_binding,
            position_creation_id=position_creation_id,
        )

        with self._ledger.transaction_scope() as cursor:
            lookup = self._ledger.lookup_logical_binding(
                logical_identity=logical_binding.logical_identity,
                effect_type=logical_binding.effect_type,
                authority_decision_id=logical_binding.authority_decision_id,
                reconciliation_context_id=logical_binding.reconciliation_context_id,
                decision_sequence=logical_binding.decision_sequence,
                authority_contract_version=logical_binding.authority_contract_version,
                cursor=cursor,
            )
            if lookup.disposition is LogicalBindingLookupDisposition.FOUND_CONFLICTING_BINDING:
                raise EffectApplicationCoordinatorError(
                    "CONFLICTING_BINDING: canonical logical binding disagrees"
                )

            if lookup.disposition is LogicalBindingLookupDisposition.NOT_FOUND:
                write = self._ledger.bind_logical_effect(
                    logical_identity=logical_binding.logical_identity,
                    effect_request_id=logical_binding.effect_request_id,
                    effect_type=logical_binding.effect_type,
                    authority_decision_id=logical_binding.authority_decision_id,
                    reconciliation_context_id=logical_binding.reconciliation_context_id,
                    decision_sequence=logical_binding.decision_sequence,
                    authority_contract_version=logical_binding.authority_contract_version,
                    cursor=cursor,
                )
                if write.binding is None:
                    raise EffectApplicationCoordinatorError(
                        "CONFLICTING_BINDING: canonical binding was not returned"
                    )
                canonical_binding = write.binding
            else:
                canonical_binding = lookup.binding

            if canonical_binding is None:
                raise EffectApplicationCoordinatorError(
                    "CONFLICTING_BINDING: canonical binding is absent"
                )

            state, current_attempt_id = self._current_state(
                cursor, canonical_binding.effect_request_id
            )
            if state == "APPLIED":
                return self._replay(
                    logical_binding=canonical_binding,
                    cursor=cursor,
                )
            if state == "APPLYING":
                return EffectApplicationCoordinatorResult(
                    effect_request_id=canonical_binding.effect_request_id,
                    classification="RECOVERY_REQUIRED",
                    application_attempt_id=current_attempt_id,
                )
            if state == "OUTCOME_UNKNOWN":
                return EffectApplicationCoordinatorResult(
                    effect_request_id=canonical_binding.effect_request_id,
                    classification="RECOVERY_REQUIRED",
                    application_attempt_id=current_attempt_id,
                )
            if state == "FAILED_WITHOUT_EFFECT":
                return EffectApplicationCoordinatorResult(
                    effect_request_id=canonical_binding.effect_request_id,
                    classification="FAILED_WITHOUT_EFFECT",
                    application_attempt_id=current_attempt_id,
                )
            if state != "AUTHORIZED":
                raise EffectApplicationCoordinatorError(
                    f"unsupported application state: {state}"
                )

            self._ledger.claim_application(
                canonical_binding.effect_request_id,
                application_attempt_id=application_attempt_id,
                claimant_id=claimant_id,
                cursor=cursor,
            )
            position_result = self._apply_position_effect(
                canonical_binding,
                position_id=resolved_position_id,
                receipt=receipt,
                applied_quantity=applied_quantity,
                intended_quantity=intended_quantity,
                external_order_id=external_order_id,
                symbol=symbol,
                cursor=cursor,
            )
            self._ledger.mark_applied(
                canonical_binding.effect_request_id,
                application_attempt_id=application_attempt_id,
                receipt=self._ledger_receipt(
                    receipt,
                    canonical_binding.effect_request_id,
                ),
                evidence_ids=tuple(evidence_ids),
                cursor=cursor,
            )
            return position_result

    @staticmethod
    def _validate_input(
        logical_binding: LogicalEffectBinding,
        application_attempt_id: str,
    ) -> None:
        if not isinstance(logical_binding, LogicalEffectBinding):
            raise EffectApplicationCoordinatorError(
                "logical binding is required"
            )
        if not application_attempt_id:
            raise EffectApplicationCoordinatorError(
                "application_attempt_id is caller-supplied and required"
            )

    @staticmethod
    def _resolve_position_id(
        effect_type: EffectType,
        *,
        position_id: Optional[str],
        position_binding: Optional[PositionBinding],
        position_creation_id: Optional[str],
    ) -> Optional[str]:
        if position_binding is not None:
            if position_id is not None or position_creation_id is not None:
                raise EffectApplicationCoordinatorError(
                    "position binding must be supplied through one boundary"
                )
            position_id = position_binding.position_id
            position_creation_id = position_binding.position_creation_id

        if effect_type is EffectType.OPEN:
            if position_creation_id is None or position_id is not None:
                raise EffectApplicationCoordinatorError(
                    "OPEN requires position_creation_id as canonical position_id"
                )
            return position_creation_id

        if position_id is None or position_creation_id is not None:
            raise EffectApplicationCoordinatorError(
                "REDUCE/CLOSE require position_id and no position_creation_id"
            )
        return position_id

    @staticmethod
    def _current_state(cursor: Any, effect_request_id: str) -> tuple[str, Optional[str]]:
        cursor.execute(
            """
            SELECT current_state, current_attempt_id
            FROM handa_live.effect_request
            WHERE effect_request_id=%s
            FOR UPDATE
            """,
            (effect_request_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise EffectApplicationLedgerError("effect request does not exist")
        return row[0], row[1]

    def _apply_position_effect(
        self,
        binding: LogicalEffectBinding,
        *,
        position_id: Optional[str],
        receipt: Mapping[str, Any],
        applied_quantity: Any,
        intended_quantity: Any,
        external_order_id: Optional[str],
        symbol: str,
        cursor: Any,
    ) -> PositionEffectResult:
        authority = self._position_authority
        lineage = {
            "reconciliation_context_id": binding.reconciliation_context_id,
            "semantic_decision_id": binding.authority_decision_id,
            "decision_sequence": binding.decision_sequence,
            "authority_contract_version": binding.authority_contract_version,
        }
        if binding.effect_type is EffectType.OPEN:
            return authority.apply_open(
                position_id=position_id,
                intended_quantity=intended_quantity,
                receipt=receipt,
                intent_id=binding.logical_identity.intent_id,
                symbol=symbol,
                effect_request_id=binding.effect_request_id,
                external_order_id=external_order_id,
                cursor=cursor,
                **lineage,
            )
        if binding.effect_type is EffectType.REDUCE:
            return authority.apply_reduction(
                position_id=position_id,
                applied_quantity=applied_quantity,
                receipt=receipt,
                effect_request_id=binding.effect_request_id,
                cursor=cursor,
                **lineage,
            )
        if binding.effect_type is EffectType.CLOSE:
            return authority.apply_close(
                position_id=position_id,
                receipt=receipt,
                effect_request_id=binding.effect_request_id,
                cursor=cursor,
                **lineage,
            )
        raise EffectApplicationCoordinatorError(
            f"unsupported effect type: {binding.effect_type}"
        )

    @staticmethod
    def _ledger_receipt(
        receipt: Mapping[str, Any], effect_request_id: str
    ) -> Mapping[str, Any]:
        if {"schema_version", "producer_id", "payload"} <= set(receipt):
            return receipt
        receipt_id = receipt.get("receipt_id")
        if not receipt_id:
            raise EffectApplicationCoordinatorError(
                "receipt_id is required for durable application"
            )
        return {
            "receipt_id": str(receipt_id),
            "schema_version": "position-effect-v1",
            "producer_id": "position-effect-authority",
            "payload": {
                "effect_request_id": effect_request_id,
                "position_receipt": dict(receipt),
            },
        }


__all__ = [
    "EffectApplicationCoordinator",
    "EffectApplicationCoordinatorError",
    "EffectApplicationCoordinatorResult",
]
