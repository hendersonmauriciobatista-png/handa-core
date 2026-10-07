"""Fail-safe issuer for one durable submission authorization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from core.execution.authority_digest import attempt_semantic_digest, intent_semantic_digest
from core.execution.pre_execution_candidate_evidence import (
    DECISION_ENGINE_EVIDENCE_PROFILE_VERSION,
)
from core.execution.submission_authority import submission_fingerprint
from core.persistence.submission_authorization_issuer_store import (
    SubmissionAuthorizationIssuerPersistence,
)


ISSUER_ID = "handa-submission-authorization-issuer"
SUPPORTED_AUTHORITY_CONTRACT_VERSION = "submission-authority-v1"
SUPPORTED_DECISION_EVIDENCE_PROFILE = "buy-signal-evidence-v1"


class IssuanceDisposition(str, Enum):
    ISSUED = "ISSUED"
    ALREADY_ISSUED = "ALREADY_ISSUED"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    CONFLICT = "CONFLICT"
    CANNOT_ISSUE = "CANNOT_ISSUE"


@dataclass(frozen=True)
class IssuanceResult:
    disposition: IssuanceDisposition
    submission_authorization_id: Optional[str] = None
    intent_id: Optional[str] = None
    submission_attempt_id: Optional[str] = None
    authority_reference_id: Optional[str] = None
    authorization_state: Optional[str] = None
    reason: str = ""


def _result(
    disposition: IssuanceDisposition,
    *,
    reason: str,
    authorization: Any = None,
) -> IssuanceResult:
    return IssuanceResult(
        disposition=disposition,
        submission_authorization_id=(
            authorization["submission_authorization_id"]
            if authorization is not None else None
        ),
        intent_id=authorization["intent_id"] if authorization is not None else None,
        submission_attempt_id=(
            authorization["submission_attempt_id"]
            if authorization is not None else None
        ),
        authority_reference_id=(
            authorization["authority_reference_id"]
            if authorization is not None else None
        ),
        authorization_state=(
            authorization["authorization_state"]
            if authorization is not None else None
        ),
        reason=reason,
    )


def _same(left: Any, right: Any) -> bool:
    return left == right


def _timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SubmissionAuthorizationIssuer:
    """Issue exactly one AUTHORIZED row from the latest current ALLOW."""

    def __init__(self, persistence: SubmissionAuthorizationIssuerPersistence):
        self._persistence = persistence

    def issue(self, *, intent_id: str, submission_attempt_id: str) -> IssuanceResult:
        if (
            not isinstance(intent_id, str) or not intent_id.strip()
            or not isinstance(submission_attempt_id, str)
            or not submission_attempt_id.strip()
        ):
            return _result(
                IssuanceDisposition.CANNOT_ISSUE,
                reason="INVALID_ISSUER_INPUT",
            )

        try:
            with self._persistence._transaction() as context:
                existing = self._persistence.find_authorization(
                    context, submission_attempt_id
                )
                if existing is not None:
                    return_result = self._historical_result(
                        context, existing, intent_id, submission_attempt_id
                    )
                else:
                    return_result = None
        except Exception:
            return _result(
                IssuanceDisposition.CANNOT_ISSUE,
                reason="TECHNICAL_PERSISTENCE_FAILURE",
            )
        if return_result is not None:
            return return_result

        try:
            with self._persistence._transaction() as context:
                state = self._persistence.get_state_for_update(context)
                if state is None:
                    return_result = _result(
                        IssuanceDisposition.CANNOT_ISSUE,
                        reason="AUTHORITY_STATE_MISSING",
                    )
                else:
                    attempt = self._persistence.get_attempt(
                        context, submission_attempt_id, for_update=True
                    )
                    intent = self._persistence.get_intent(
                        context, intent_id, for_update=True
                    )
                    if attempt is None or intent is None:
                        return_result = _result(
                            IssuanceDisposition.CANNOT_ISSUE,
                            reason="LINEAGE_RECORD_MISSING",
                        )
                    elif attempt["intent_id"] != intent_id:
                        return_result = _result(
                            IssuanceDisposition.CANNOT_ISSUE,
                            reason="ATTEMPT_INTENT_LINEAGE_MISMATCH",
                        )
                    else:
                        existing = self._persistence.find_authorization(
                            context, submission_attempt_id
                        )
                        if existing is not None:
                            return_result = self._historical_result(
                                context, existing, intent_id, submission_attempt_id
                            )
                        else:
                            return_result = self._issue_new(
                                context, state, intent, attempt
                            )
        except Exception:
            return _result(
                IssuanceDisposition.CANNOT_ISSUE,
                reason="TECHNICAL_PERSISTENCE_FAILURE",
            )
        return return_result

    def _historical_result(
        self, context, authorization, requested_intent_id: str, requested_attempt_id: str
    ) -> IssuanceResult:
        intent = self._persistence.get_intent(
            context, requested_intent_id
        )
        attempt = self._persistence.get_attempt(
            context, requested_attempt_id
        )
        if intent is None or attempt is None:
            return _result(
                IssuanceDisposition.CANNOT_ISSUE,
                reason="HISTORICAL_LINEAGE_MISSING",
            )
        decision = self._persistence.get_decision(
            context, authorization["authority_reference_id"]
        )
        if decision is None:
            return _result(
                IssuanceDisposition.CANNOT_ISSUE,
                reason="HISTORICAL_DECISION_MISSING",
            )
        envelope = self._persistence.get_envelope(
            context, decision["authority_envelope_id"]
        )
        if envelope is None:
            return _result(
                IssuanceDisposition.CANNOT_ISSUE,
                reason="HISTORICAL_ENVELOPE_MISSING",
            )
        if not self._historical_binding_is_canonical(
            authorization, intent, attempt, decision, envelope,
            requested_intent_id, requested_attempt_id,
        ):
            return _result(
                IssuanceDisposition.CONFLICT,
                reason="HISTORICAL_BINDING_CONFLICT",
                authorization=authorization,
            )
        if authorization["authorization_state"] not in {"AUTHORIZED", "CLAIMED"}:
            return _result(
                IssuanceDisposition.CONFLICT,
                reason="HISTORICAL_AUTHORIZATION_STATE_INVALID",
                authorization=authorization,
            )
        return _result(
            IssuanceDisposition.ALREADY_ISSUED,
            reason="CANONICAL_AUTHORIZATION_EXISTS",
            authorization=authorization,
        )

    @staticmethod
    def _historical_binding_is_canonical(
        authorization,
        intent,
        attempt,
        decision,
        envelope,
        requested_intent_id: str,
        requested_attempt_id: str,
    ) -> bool:
        if authorization["intent_id"] != requested_intent_id:
            return False
        if authorization["submission_attempt_id"] != requested_attempt_id:
            return False
        if attempt["attempt_id"] != requested_attempt_id:
            return False
        if attempt["intent_id"] != intent["intent_id"] or intent["intent_id"] != requested_intent_id:
            return False
        for column in ("venue", "account_scope", "client_order_id"):
            if authorization[column] != intent[column] or authorization[column] != attempt[column]:
                return False
        for column in (
            "symbol", "side", "requested_quote_amount", "requested_base_qty"
        ):
            if authorization[column] != intent[column]:
                return False
        if authorization["authorization_sequence"] != attempt["attempt_sequence"]:
            return False
        if authorization["issuer_id"] != ISSUER_ID:
            return False
        if authorization["authority_contract_version"] != SUPPORTED_AUTHORITY_CONTRACT_VERSION:
            return False
        try:
            expected_fingerprint = submission_fingerprint(
                intent_id=intent["intent_id"],
                submission_attempt_id=attempt["attempt_id"],
                client_order_id=intent["client_order_id"],
                venue=intent["venue"],
                account_scope=intent["account_scope"],
                symbol=intent["symbol"],
                side=intent["side"],
                requested_quote_amount=intent["requested_quote_amount"],
                requested_base_qty=intent["requested_base_qty"],
            )
        except (TypeError, ValueError):
            return False
        if authorization["submission_fingerprint"] != expected_fingerprint:
            return False
        if decision["intent_id"] != intent["intent_id"] or decision["submission_attempt_id"] != attempt["attempt_id"]:
            return False
        if decision["decision_outcome"] != "ALLOW":
            return False
        if authorization["authority_contract_version"] != envelope["authority_contract_version"]:
            return False
        created_at = _timestamp(authorization["created_at"])
        evaluated_at = _timestamp(decision["evaluated_at"])
        valid_until = _timestamp(decision["valid_until"])
        valid_from = _timestamp(envelope["valid_from"])
        envelope_until = _timestamp(envelope["valid_until"])
        if None in (created_at, evaluated_at, valid_until, valid_from, envelope_until):
            return False
        return (
            evaluated_at <= created_at < valid_until
            and valid_from <= created_at < envelope_until
        )

    def _issue_new(self, context, state, intent, attempt) -> IssuanceResult:
        active_envelope_id = state["active_authority_envelope_id"]
        if not active_envelope_id:
            return _result(
                IssuanceDisposition.CANNOT_ISSUE,
                reason="ACTIVE_AUTHORITY_ENVELOPE_MISSING",
            )
        envelope = self._persistence.get_envelope(context, active_envelope_id)
        if envelope is None:
            return _result(
                IssuanceDisposition.CANNOT_ISSUE,
                reason="ACTIVE_AUTHORITY_ENVELOPE_NOT_FOUND",
            )
        decision = self._persistence.latest_decision(context, attempt["attempt_id"])
        if decision is None:
            return _result(
                IssuanceDisposition.CANNOT_ISSUE,
                reason="LATEST_DECISION_MISSING",
            )
        if self._persistence.has_exchange_evidence(context, attempt["attempt_id"]):
            return _result(
                IssuanceDisposition.NOT_ELIGIBLE,
                reason="EXTERNAL_EVIDENCE_ALREADY_EXISTS",
            )
        now = datetime.now(timezone.utc)
        reason = self._currentness_failure(state, envelope, intent, attempt, decision, now)
        if reason is not None:
            disposition = (
                IssuanceDisposition.CANNOT_ISSUE
                if reason.startswith("CANNOT:")
                else IssuanceDisposition.NOT_ELIGIBLE
            )
            return _result(disposition, reason=reason.removeprefix("CANNOT:"))
        try:
            fingerprint = submission_fingerprint(
                intent_id=intent["intent_id"],
                submission_attempt_id=attempt["attempt_id"],
                client_order_id=intent["client_order_id"],
                venue=intent["venue"],
                account_scope=intent["account_scope"],
                symbol=intent["symbol"],
                side=intent["side"],
                requested_quote_amount=intent["requested_quote_amount"],
                requested_base_qty=intent["requested_base_qty"],
            )
            authorization = self._persistence._insert_authorized(
                context,
                submission_authorization_id=f"submission-auth-{uuid4().hex}",
                intent_id=intent["intent_id"],
                submission_attempt_id=attempt["attempt_id"],
                client_order_id=intent["client_order_id"],
                venue=intent["venue"],
                account_scope=intent["account_scope"],
                symbol=intent["symbol"],
                side=intent["side"],
                requested_quote_amount=intent["requested_quote_amount"],
                requested_base_qty=intent["requested_base_qty"],
                authority_reference_id=decision["pre_execution_decision_id"],
                issuer_id=ISSUER_ID,
                authority_contract_version=SUPPORTED_AUTHORITY_CONTRACT_VERSION,
                authorization_sequence=attempt["attempt_sequence"],
                submission_fingerprint=fingerprint,
            )
        except Exception:
            raise
        return _result(
            IssuanceDisposition.ISSUED,
            reason="AUTHORIZATION_ISSUED",
            authorization=authorization,
        )

    @staticmethod
    def _currentness_failure(state, envelope, intent, attempt, decision, now) -> Optional[str]:
        required = (
            state, envelope, intent, attempt, decision,
            state["operational_mode"], envelope["runtime_mode"],
            envelope["authority_contract_version"], intent["venue"],
            attempt["venue"], envelope["venue"], intent["account_scope"],
            attempt["account_scope"], envelope["account_scope"],
            intent["side"], envelope["allowed_sides"],
            intent["submission_lifecycle_state"], attempt["submission_lifecycle_state"],
            decision["decision_outcome"], decision["decision_engine_version"],
            decision["evaluated_at"], decision["valid_until"],
        )
        if any(value is None for value in required):
            return "CANNOT:REQUIRED_AUTHORITY_DATA_MISSING"
        if state["operational_mode"] != "OPERATIONAL_ENABLED":
            return "AUTHORITY_STATE_NOT_OPERATIONAL"
        if not envelope["valid_from"] <= now < envelope["valid_until"]:
            return "AUTHORITY_ENVELOPE_NOT_CURRENT"
        if state["operational_mode"] != envelope["runtime_mode"]:
            return "STATE_ENVELOPE_RUNTIME_MISMATCH"
        if envelope["authority_contract_version"] != SUPPORTED_AUTHORITY_CONTRACT_VERSION:
            return "UNSUPPORTED_AUTHORITY_CONTRACT"
        if not (
            intent["venue"] == attempt["venue"] == envelope["venue"]
            and intent["account_scope"] == attempt["account_scope"] == envelope["account_scope"]
            and intent["side"] in envelope["allowed_sides"]
        ):
            return "INTENT_ENVELOPE_SCOPE_MISMATCH"
        if intent["submission_lifecycle_state"] != "SUBMISSION_ATTEMPTED":
            return "INTENT_NOT_SUBMISSION_ATTEMPTED"
        if any(
            intent[column] is not None
            for column in ("execution_certainty", "reconciliation_state", "exchange_order_id")
        ):
            return "INTENT_EXTERNAL_HANDOFF"
        if attempt["submission_lifecycle_state"] != "SUBMISSION_ATTEMPTED":
            return "ATTEMPT_NOT_SUBMISSION_ATTEMPTED"
        if attempt["exchange_order_id"] is not None:
            return "ATTEMPT_EXTERNAL_HANDOFF"
        if any(
            attempt[column] is not None
            for column in ("transport_status", "transport_error", "observed_at", "exchange_event_time")
        ):
            return "ATTEMPT_EXTERNAL_HANDOFF"
        if decision["intent_id"] != intent["intent_id"] or decision["submission_attempt_id"] != attempt["attempt_id"]:
            return "CANNOT:DECISION_LINEAGE_MISMATCH"
        if decision["decision_outcome"] != "ALLOW":
            return "LATEST_DECISION_NOT_ALLOW"
        if decision["authority_envelope_id"] != state["active_authority_envelope_id"]:
            return "DECISION_ENVELOPE_MISMATCH"
        if decision["runtime_mode"] != state["operational_mode"]:
            return "DECISION_RUNTIME_MISMATCH"
        if decision["global_safety_epoch"] != state["global_safety_epoch"]:
            return "DECISION_EPOCH_MISMATCH"
        if decision["runtime_generation"] != state["runtime_generation"]:
            return "DECISION_RUNTIME_GENERATION_MISMATCH"
        if not (
            decision["venue"] == intent["venue"] == attempt["venue"]
            and decision["account_scope"] == intent["account_scope"] == attempt["account_scope"]
        ):
            return "DECISION_SCOPE_MISMATCH"
        if decision["decision_engine_version"] != SUPPORTED_DECISION_EVIDENCE_PROFILE:
            return "UNSUPPORTED_DECISION_EVIDENCE_PROFILE"
        if not (
            decision["decision_contract_version"] == envelope["decision_contract_version"]
            and decision["policy_version"] == envelope["policy_version"]
            and decision["risk_policy_version"] == envelope["risk_policy_version"]
            and decision["strategy_version"] == envelope["strategy_version"]
        ):
            return "DECISION_CONTRACT_MISMATCH"
        evaluated_at = _timestamp(decision["evaluated_at"])
        valid_until = _timestamp(decision["valid_until"])
        valid_from = _timestamp(envelope["valid_from"])
        envelope_until = _timestamp(envelope["valid_until"])
        if None in (evaluated_at, valid_until, valid_from, envelope_until):
            return "CANNOT:INVALID_AUTHORITY_TIMESTAMP"
        if not evaluated_at <= now < valid_until:
            return "DECISION_NOT_CURRENT"
        if not (evaluated_at >= valid_from and valid_until <= envelope_until):
            return "DECISION_OUTSIDE_ENVELOPE_VALIDITY"
        try:
            if intent_semantic_digest(intent) != decision["intent_semantic_digest"]:
                return "INTENT_SEMANTIC_DIGEST_MISMATCH"
            if attempt_semantic_digest(attempt) != decision["submission_attempt_semantic_digest"]:
                return "ATTEMPT_SEMANTIC_DIGEST_MISMATCH"
        except (KeyError, TypeError, ValueError):
            return "CANNOT:SEMANTIC_DIGEST_UNVERIFIABLE"
        return None


__all__ = [
    "ISSUER_ID",
    "SUPPORTED_AUTHORITY_CONTRACT_VERSION",
    "SUPPORTED_DECISION_EVIDENCE_PROFILE",
    "IssuanceDisposition",
    "IssuanceResult",
    "SubmissionAuthorizationIssuer",
]
