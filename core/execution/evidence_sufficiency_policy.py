"""Pure, informational evaluation of persisted execution evidence.

This module deliberately has no persistence, exchange, reconciliation, or
position-management dependencies.  It evaluates only the evidence supplied
by its caller and never treats normalized status or absence as proof of an
external effect.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Optional


class _ImmutableList(list):
    """List-shaped immutable result value for compatibility with callers."""

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("evidence result lineage is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __iadd__ = _immutable
    __imul__ = _immutable
    append = _immutable
    clear = _immutable
    extend = _immutable
    insert = _immutable
    pop = _immutable
    remove = _immutable
    reverse = _immutable
    sort = _immutable


@dataclass(frozen=True)
class EvidenceSufficiencyResult:
    proposition: str
    classification: str
    intent_id: str
    supporting_evidence_refs: _ImmutableList
    supporting_normalized_revision_ids: _ImmutableList
    contradiction_refs: _ImmutableList
    reason_code: str


class EvidenceSufficiencyPolicy:
    """Evaluate evidence sufficiency without taking operational action."""

    _PROPOSITIONS = frozenset(
        {
            "ANY_EXECUTION",
            "FULL_EXECUTION",
            "PARTIAL_EXECUTION",
            "NO_EXTERNAL_EFFECT",
            "IDENTITY_MATCH",
            "IDENTITY_CONTRADICTION",
        }
    )
    _CLASSIFICATIONS = frozenset({"SUFFICIENT", "INSUFFICIENT", "CONTRADICTORY"})

    @staticmethod
    def evaluate(
        *,
        proposition: str,
        intent: Mapping[str, Any],
        external_observations: Iterable[Mapping[str, Any]] = (),
        trade_effects: Iterable[Mapping[str, Any]] = (),
        normalized_evidence: Iterable[Mapping[str, Any]] = (),
    ) -> EvidenceSufficiencyResult:
        if proposition not in EvidenceSufficiencyPolicy._PROPOSITIONS:
            raise ValueError(f"unsupported proposition: {proposition}")

        intent_id = str(intent.get("intent_id", ""))
        requested_client_id = intent.get("client_order_id")
        observations = tuple(external_observations)
        trades = tuple(trade_effects)
        revisions = tuple(normalized_evidence)

        observations = tuple(
            item for item in observations if item.get("intent_id") == intent_id
        )
        trades = tuple(item for item in trades if item.get("intent_id") == intent_id)

        observation_refs = [str(item["evidence_ref"]) for item in observations]
        trade_refs = [str(item["trade_effect_ref"]) for item in trades]
        revision_ids = [str(item["revision_id"]) for item in revisions if "revision_id" in item]

        identity_mismatches = [
            str(item["evidence_ref"])
            for item in observations
            if requested_client_id is not None
            and item.get("client_order_id_observed") is not None
            and item.get("client_order_id_observed") != requested_client_id
        ]

        if proposition == "IDENTITY_CONTRADICTION":
            if identity_mismatches:
                return EvidenceSufficiencyPolicy._result(
                    proposition,
                    "SUFFICIENT",
                    intent_id,
                    contradiction_refs=identity_mismatches,
                    reason_code="IDENTITY_CONTRADICTION",
                )
            return EvidenceSufficiencyPolicy._result(
                proposition,
                "INSUFFICIENT",
                intent_id,
                considered_refs=observation_refs,
                considered_revisions=revision_ids,
                reason_code="IDENTITY_CONTRADICTION_NOT_ESTABLISHED",
            )

        if proposition == "IDENTITY_MATCH":
            matching_refs = [
                str(item["evidence_ref"])
                for item in observations
                if item.get("client_order_id_observed") is not None
                and item.get("client_order_id_observed") == requested_client_id
            ]
            if matching_refs and not identity_mismatches:
                return EvidenceSufficiencyPolicy._result(
                    proposition,
                    "SUFFICIENT",
                    intent_id,
                    supporting_refs=matching_refs,
                    reason_code="IDENTITY_MATCH_CONFIRMED",
                )
            return EvidenceSufficiencyPolicy._result(
                proposition,
                "INSUFFICIENT",
                intent_id,
                considered_refs=observation_refs,
                considered_revisions=revision_ids,
                reason_code=(
                    "IDENTITY_CONTRADICTION_PRESENT"
                    if identity_mismatches
                    else "IDENTITY_NOT_OBSERVED"
                ),
            )

        if identity_mismatches:
            return EvidenceSufficiencyPolicy._result(
                proposition,
                "CONTRADICTORY",
                intent_id,
                contradiction_refs=identity_mismatches,
                reason_code="IDENTITY_CONTRADICTION",
            )

        positive_trade_refs = [
            str(item["trade_effect_ref"])
            for item in trades
            if EvidenceSufficiencyPolicy._positive_decimal(item.get("trade_qty"))
        ]
        positive_quantity_refs = [
            str(item["evidence_ref"])
            for item in observations
            if EvidenceSufficiencyPolicy._positive_decimal(item.get("executed_qty"))
        ]
        positive_status_refs = [
            str(item["evidence_ref"])
            for item in observations
            if item.get("external_order_status") in {"PARTIALLY_FILLED", "FILLED"}
        ]

        if proposition == "PARTIAL_EXECUTION":
            if positive_status_refs and any(
                item.get("external_order_status") == "PARTIALLY_FILLED"
                for item in observations
            ):
                return EvidenceSufficiencyPolicy._result(
                    proposition,
                    "SUFFICIENT",
                    intent_id,
                    supporting_refs=positive_status_refs,
                    reason_code="EXTERNAL_PARTIALLY_FILLED",
                )
            return EvidenceSufficiencyPolicy._result(
                proposition,
                "INSUFFICIENT",
                intent_id,
                considered_refs=observation_refs + trade_refs,
                considered_revisions=revision_ids,
                reason_code="PARTIAL_EXTENT_UNPROVEN",
            )

        if proposition == "FULL_EXECUTION":
            return EvidenceSufficiencyPolicy._result(
                proposition,
                "INSUFFICIENT",
                intent_id,
                considered_refs=observation_refs + trade_refs,
                considered_revisions=revision_ids,
                reason_code="FULLNESS_UNPROVEN",
            )

        if proposition == "NO_EXTERNAL_EFFECT":
            return EvidenceSufficiencyPolicy._result(
                proposition,
                "INSUFFICIENT",
                intent_id,
                considered_refs=observation_refs + trade_refs,
                considered_revisions=revision_ids,
                reason_code="NO_POSITIVE_NO_EFFECT_PROOF_RULE",
            )

        non_positive_trade_refs = [
            str(item["trade_effect_ref"])
            for item in trades
            if not EvidenceSufficiencyPolicy._positive_decimal(item.get("trade_qty"))
        ]
        if non_positive_trade_refs and (positive_quantity_refs or positive_status_refs):
            external_refs = positive_quantity_refs + positive_status_refs
            contradiction_refs = list(dict.fromkeys(external_refs + non_positive_trade_refs))
            return EvidenceSufficiencyPolicy._result(
                proposition,
                "CONTRADICTORY",
                intent_id,
                contradiction_refs=contradiction_refs,
                reason_code="CONTRADICTORY_EXECUTION_EVIDENCE",
            )

        supporting_refs = list(
            dict.fromkeys(positive_trade_refs + positive_quantity_refs + positive_status_refs)
        )
        if supporting_refs:
            return EvidenceSufficiencyPolicy._result(
                proposition,
                "SUFFICIENT",
                intent_id,
                supporting_refs=supporting_refs,
                reason_code=(
                    "TRADE_EXECUTION_CONFIRMED"
                    if positive_trade_refs
                    else "EXTERNAL_EXECUTION_CONFIRMED"
                ),
            )

        return EvidenceSufficiencyPolicy._result(
            proposition,
            "INSUFFICIENT",
            intent_id,
            considered_refs=observation_refs + trade_refs,
            considered_revisions=revision_ids,
            reason_code="NO_POSITIVE_EXECUTION_EVIDENCE",
        )

    @staticmethod
    def _positive_decimal(value: Optional[Any]) -> bool:
        if value is None:
            return False
        try:
            return Decimal(str(value)) > Decimal("0")
        except (InvalidOperation, TypeError, ValueError):
            return False

    @staticmethod
    def _result(
        proposition: str,
        classification: str,
        intent_id: str,
        *,
        supporting_refs: Iterable[str] = (),
        supporting_revisions: Iterable[str] = (),
        contradiction_refs: Iterable[str] = (),
        considered_refs: Iterable[str] = (),
        considered_revisions: Iterable[str] = (),
        reason_code: str,
    ) -> EvidenceSufficiencyResult:
        if classification not in EvidenceSufficiencyPolicy._CLASSIFICATIONS:
            raise ValueError(f"unsupported classification: {classification}")
        # Considered lineage is retained in the same result channels only when
        # no positive/contradictory lineage exists; it is never used as proof.
        refs = list(supporting_refs) or ([] if contradiction_refs else list(considered_refs))
        revisions = list(supporting_revisions) or list(considered_revisions)
        return EvidenceSufficiencyResult(
            proposition=proposition,
            classification=classification,
            intent_id=intent_id,
            supporting_evidence_refs=_ImmutableList(refs),
            supporting_normalized_revision_ids=_ImmutableList(revisions),
            contradiction_refs=_ImmutableList(contradiction_refs),
            reason_code=reason_code,
        )
