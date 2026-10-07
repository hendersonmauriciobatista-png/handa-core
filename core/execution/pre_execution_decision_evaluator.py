"""Fail-safe evaluator for durable pre-execution governance decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from core.execution.authority_digest import (
    attempt_semantic_digest,
    evaluation_request_digest,
    intent_semantic_digest,
    sha256_digest,
)
from core.execution.pre_execution_candidate_evidence import (
    DECISION_ENGINE_EVIDENCE_PROFILE_VERSION,
    PreExecutionCandidateEvidence,
)
from core.persistence.pre_execution_evaluation_store import (
    PreExecutionEvaluationPersistence,
)


class EvaluationDisposition(str, Enum):
    RECORDED_ALLOW = "RECORDED_ALLOW"
    RECORDED_BLOCK = "RECORDED_BLOCK"
    ALREADY_RECORDED = "ALREADY_RECORDED"
    CONFLICT = "CONFLICT"
    CANNOT_EVALUATE = "CANNOT_EVALUATE"


@dataclass(frozen=True)
class EvaluationResult:
    disposition: EvaluationDisposition
    pre_execution_decision_id: str | None = None
    decision_sequence: int | None = None
    decision_outcome: str | None = None
    reason: str = ""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: object) -> str:
    return str(value or "").strip()


def _cannot(reason: str) -> EvaluationResult:
    return EvaluationResult(EvaluationDisposition.CANNOT_EVALUATE, reason=reason)


class PreExecutionDecisionEvaluator:
    """Evaluate durable governance without issuing authority or execution access."""

    def __init__(self, persistence: PreExecutionEvaluationPersistence):
        self._persistence = persistence

    def evaluate(
        self,
        *,
        evaluation_request_id: str,
        intent_id: str,
        submission_attempt_id: str,
        evidence: PreExecutionCandidateEvidence,
    ) -> EvaluationResult:
        if not _text(evaluation_request_id):
            return _cannot("MALFORMED_EVALUATION_REQUEST_ID")
        if not _text(intent_id) or not _text(submission_attempt_id):
            return _cannot("MALFORMED_EVALUATION_LINEAGE")
        if not isinstance(evidence, PreExecutionCandidateEvidence):
            return _cannot("MALFORMED_EVIDENCE")
        if evidence.source_contract_version != DECISION_ENGINE_EVIDENCE_PROFILE_VERSION:
            return _cannot("UNSUPPORTED_EVIDENCE_PROFILE")

        request_digest = evaluation_request_digest(
            intent_id=intent_id,
            submission_attempt_id=submission_attempt_id,
            upstream_evidence_digest_value=evidence.evidence_digest,
        )

        try:
            with self._persistence.transaction() as context:
                state = self._persistence.get_state(context)
                if state is None:
                    return _cannot("STATE_MISSING")

                active_envelope_id = state["active_authority_envelope_id"]
                if not active_envelope_id:
                    return _cannot("ACTIVE_ENVELOPE_ABSENT")

                envelope = self._persistence.get_envelope(context, active_envelope_id)
                if envelope is None:
                    return _cannot("ACTIVE_ENVELOPE_MISSING")

                intent = self._persistence.get_intent(context, intent_id)
                if intent is None:
                    return _cannot("INTENT_MISSING")

                # The allocator obtains the attempt row lock before returning.
                # The numeric MAX()+1 value is not consumed unless an insert
                # commits; request identity is rechecked immediately after the lock.
                next_sequence = self._persistence.allocate_sequence(
                    context, submission_attempt_id
                )
                attempt = self._persistence.get_attempt(context, submission_attempt_id)
                if attempt is None:
                    return _cannot("ATTEMPT_MISSING_AFTER_LOCK")
                if attempt["intent_id"] != intent_id:
                    return _cannot("ATTEMPT_INTENT_LINEAGE_INVALID_AFTER_LOCK")

                existing = self._persistence.find_request(context, evaluation_request_id)
                if existing is not None:
                    if (
                        existing["submission_attempt_id"] == submission_attempt_id
                        and existing["evaluation_request_digest"] == request_digest
                    ):
                        return EvaluationResult(
                            EvaluationDisposition.ALREADY_RECORDED,
                            pre_execution_decision_id=existing["pre_execution_decision_id"],
                            decision_sequence=existing["decision_sequence"],
                            decision_outcome=existing["decision_outcome"],
                            reason="EVALUATION_REQUEST_ALREADY_RECORDED",
                        )
                    return EvaluationResult(
                        EvaluationDisposition.CONFLICT,
                        reason="EVALUATION_REQUEST_ID_CONFLICT",
                    )

                intent_digest = intent_semantic_digest(intent)
                attempt_digest = attempt_semantic_digest(attempt)
                evaluated_at = _now()
                input_digest = sha256_digest(
                    {
                        "state": {
                            "operational_mode": state["operational_mode"],
                            "active_authority_envelope_id": active_envelope_id,
                            "global_safety_epoch": state["global_safety_epoch"],
                            "runtime_generation": state["runtime_generation"],
                        },
                        "envelope": {
                            "authority_envelope_id": envelope["authority_envelope_id"],
                            "envelope_version": envelope["envelope_version"],
                            "runtime_mode": envelope["runtime_mode"],
                            "venue": envelope["venue"],
                            "account_scope": envelope["account_scope"],
                            "allowed_sides": envelope["allowed_sides"],
                            "decision_contract_version": envelope["decision_contract_version"],
                            "policy_version": envelope["policy_version"],
                            "risk_policy_version": envelope["risk_policy_version"],
                            "strategy_version": envelope["strategy_version"],
                            "valid_from": envelope["valid_from"],
                            "valid_until": envelope["valid_until"],
                        },
                        "intent_semantic_digest": intent_digest,
                        "submission_attempt_semantic_digest": attempt_digest,
                        "upstream_evidence_digest": evidence.evidence_digest,
                    }
                )

                block_reason = self._block_reason(
                    state=state,
                    envelope=envelope,
                    intent=intent,
                    attempt=attempt,
                    evidence=evidence,
                    evaluated_at=evaluated_at,
                )
                if block_reason is None:
                    # Production ALLOW is intentionally unreachable until a
                    # governed freshness delta and independent upstream
                    # strategy/policy/risk provenance exist.
                    return _cannot("FRESHNESS_POLICY_UNAVAILABLE")

                values = self._block_values(
                    evaluation_request_id=evaluation_request_id,
                    evaluation_request_digest_value=request_digest,
                    state=state,
                    envelope=envelope,
                    intent=intent,
                    attempt=attempt,
                    evidence=evidence,
                    intent_digest=intent_digest,
                    attempt_digest=attempt_digest,
                    input_digest=input_digest,
                    evaluated_at=evaluated_at,
                    decision_sequence=next_sequence,
                    reason=block_reason,
                )
                semantics_digest = sha256_digest(
                    {
                        "decision_outcome": values["decision_outcome"],
                        "decision_reason": values["decision_reason"],
                        "intent_id": values["intent_id"],
                        "submission_attempt_id": values["submission_attempt_id"],
                        "authority_envelope_id": values["authority_envelope_id"],
                        "decision_sequence": values["decision_sequence"],
                        "intent_semantic_digest": intent_digest,
                        "submission_attempt_semantic_digest": attempt_digest,
                        "input_snapshot_digest": input_digest,
                        "evaluated_at": evaluated_at,
                        "valid_until": evaluated_at,
                    }
                )
                values["decision_semantics_digest"] = semantics_digest
                row = self._persistence._insert_block(context, values)
                return EvaluationResult(
                    EvaluationDisposition.RECORDED_BLOCK,
                    pre_execution_decision_id=row["pre_execution_decision_id"],
                    decision_sequence=row["decision_sequence"],
                    decision_outcome=row["decision_outcome"],
                    reason=block_reason,
                )
        except Exception:
            return _cannot("TECHNICAL_PERSISTENCE_FAILURE")

    @staticmethod
    def _block_reason(*, state, envelope, intent, attempt, evidence, evaluated_at) -> str | None:
        if state["operational_mode"] not in {"OBSERVE_ONLY", "OPERATIONAL_ENABLED"}:
            return None
        if state["operational_mode"] != envelope["runtime_mode"]:
            return "RUNTIME_MODE_MISMATCH"
        if evaluated_at < envelope["valid_from"] or evaluated_at >= envelope["valid_until"]:
            return "AUTHORITY_ENVELOPE_EXPIRED_OR_NOT_YET_VALID"
        if evidence.side != "BUY" or intent["side"] != "BUY":
            return "SIDE_NOT_PERMITTED"
        if evidence.side not in set(envelope["allowed_sides"] or ()):
            return "SIDE_NOT_PERMITTED"
        if intent["venue"] != envelope["venue"] or attempt["venue"] != envelope["venue"]:
            return "VENUE_MISMATCH"
        if (
            intent["account_scope"] != envelope["account_scope"]
            or attempt["account_scope"] != envelope["account_scope"]
        ):
            return "ACCOUNT_SCOPE_MISMATCH"
        if evidence.symbol != intent["symbol"]:
            return "EVIDENCE_SYMBOL_MISMATCH"
        if attempt["submission_lifecycle_state"] != "SUBMISSION_ATTEMPTED":
            return "ATTEMPT_LIFECYCLE_INELIGIBLE"
        if state["operational_mode"] == "OBSERVE_ONLY":
            return "OBSERVE_ONLY"
        return None

    @staticmethod
    def _block_values(
        *,
        evaluation_request_id,
        evaluation_request_digest_value,
        state,
        envelope,
        intent,
        attempt,
        evidence,
        intent_digest,
        attempt_digest,
        input_digest,
        evaluated_at,
        decision_sequence,
        reason,
    ) -> dict:
        return {
            "pre_execution_decision_id": f"preexec-{uuid4().hex}",
            "intent_id": intent["intent_id"],
            "submission_attempt_id": attempt["attempt_id"],
            "authority_envelope_id": envelope["authority_envelope_id"],
            "decision_sequence": decision_sequence,
            "decision_outcome": "BLOCK",
            "decision_reason": reason,
            "intent_semantic_digest": intent_digest,
            "submission_attempt_semantic_digest": attempt_digest,
            "decision_contract_version": envelope["decision_contract_version"],
            "decision_engine_version": DECISION_ENGINE_EVIDENCE_PROFILE_VERSION,
            "policy_version": envelope["policy_version"],
            "risk_policy_version": envelope["risk_policy_version"],
            "strategy_version": envelope["strategy_version"],
            "input_snapshot_digest": input_digest,
            "decision_semantics_digest": "pending",
            "global_safety_epoch": state["global_safety_epoch"],
            "runtime_generation": state["runtime_generation"],
            "runtime_mode": state["operational_mode"],
            "venue": intent["venue"],
            "account_scope": intent["account_scope"],
            "evaluated_at": evaluated_at,
            "valid_until": evaluated_at,
            "evaluation_request_id": evaluation_request_id,
            "evaluation_request_digest": evaluation_request_digest_value,
        }
