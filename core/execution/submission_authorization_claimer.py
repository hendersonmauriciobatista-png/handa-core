"""Fail-safe claim-time revalidation for one durable authorization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from core.execution.authority_digest import attempt_semantic_digest, intent_semantic_digest
from core.execution.submission_authority import (
    ClaimDisposition,
    ClaimResult,
    _issue_claimed_capability,
    submission_fingerprint,
)
from core.persistence.submission_claim_store import SubmissionClaimPersistence
from core.persistence.transaction_context import VersionConflict


CLAIMANT_ID = "handa-submission-authorization-claimer"
ISSUER_ID = "handa-submission-authorization-issuer"
SUPPORTED_AUTHORITY_CONTRACT_VERSION = "submission-authority-v1"
SUPPORTED_DECISION_EVIDENCE_PROFILE = "buy-signal-evidence-v1"


def _timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _result(disposition: ClaimDisposition, reason: str = "") -> ClaimResult:
    return ClaimResult(disposition, reason=reason)


@dataclass(frozen=True)
class _ReplayOutcome:
    disposition: ClaimDisposition
    reason: str
    record: Any = None


def _replay_result(outcome: _ReplayOutcome) -> ClaimResult:
    if outcome.disposition is ClaimDisposition.CLAIM_REPLAY:
        return ClaimResult(
            outcome.disposition,
            _issue_claimed_capability(outcome.record),
            outcome.reason,
        )
    return ClaimResult(outcome.disposition, reason=outcome.reason)


class SubmissionAuthorizationClaimer:
    """Claim only when the durable authority remains current at claim time."""

    def __init__(self, persistence: SubmissionClaimPersistence):
        self._persistence = persistence

    def claim(self, submission_authorization_id: str) -> ClaimResult:
        if not isinstance(submission_authorization_id, str) or not submission_authorization_id.strip():
            return _result(ClaimDisposition.CANNOT_CLAIM, "INVALID_CLAIM_INPUT")

        discovery_replay = None
        try:
            with self._persistence._transaction() as context:
                discovered = self._persistence.get_authorization(context, submission_authorization_id)
                if discovered is None:
                    return _result(ClaimDisposition.NOT_FOUND, "AUTHORIZATION_NOT_FOUND")
                if discovered["authorization_state"] == "CLAIMED":
                    discovery_replay = self._replay_result(context, discovered)
                if discovered["authorization_state"] != "AUTHORIZED":
                    if discovery_replay is not None:
                        pass
                    else:
                        return _result(ClaimDisposition.CONFLICT, "AUTHORIZATION_STATE_INVALID")
                else:
                    lineage = (discovered["intent_id"], discovered["submission_attempt_id"])
        except Exception:
            return _result(ClaimDisposition.CANNOT_CLAIM, "TECHNICAL_PERSISTENCE_FAILURE")
        if discovery_replay is not None:
            return _replay_result(discovery_replay)

        claimed_row = None
        authoritative_replay = None
        try:
            with self._persistence._transaction() as context:
                state = self._persistence.get_state_for_update(context)
                if state is None:
                    return _result(ClaimDisposition.CANNOT_CLAIM, "AUTHORITY_STATE_MISSING")
                attempt = self._persistence.get_attempt(context, lineage[1], for_update=True)
                intent = self._persistence.get_intent(context, lineage[0], for_update=True)
                authorization = self._persistence.get_authorization(context, submission_authorization_id, for_update=True)
                if authorization is None:
                    return _result(ClaimDisposition.CANNOT_CLAIM, "AUTHORIZATION_DISAPPEARED")
                if (authorization["intent_id"], authorization["submission_attempt_id"]) != lineage:
                    return _result(ClaimDisposition.CONFLICT, "AUTHORIZATION_LINEAGE_CHANGED")
                if authorization["authorization_state"] == "CLAIMED":
                    authoritative_replay = self._replay_result(context, authorization)
                elif authorization["authorization_state"] != "AUTHORIZED":
                    return _result(ClaimDisposition.CONFLICT, "AUTHORIZATION_STATE_INVALID")
                elif intent is None or attempt is None:
                    return _result(ClaimDisposition.CANNOT_CLAIM, "LINEAGE_RECORD_MISSING")
                elif authorization["current_version"] != 0 or authorization["claimed_by"] is not None or authorization["claimed_at"] is not None:
                    return _result(ClaimDisposition.CONFLICT, "AUTHORIZED_ROW_MALFORMED")
                else:
                    binding_reason = self._binding_failure(authorization, intent, attempt)
                    if binding_reason is not None:
                        disposition = ClaimDisposition.CANNOT_CLAIM if binding_reason.startswith("CANNOT:") else ClaimDisposition.CONFLICT
                        return _result(disposition, binding_reason.removeprefix("CANNOT:"))
                    reason = self._currentness_failure(context, state, authorization, intent, attempt)
                    if reason is not None:
                        return _result(
                            ClaimDisposition.CANNOT_CLAIM if reason.startswith("CANNOT:") else ClaimDisposition.NOT_CURRENT,
                            reason.removeprefix("CANNOT:"),
                        )
                    try:
                        claimed_row = self._persistence.claim_authorization(context, submission_authorization_id, CLAIMANT_ID)
                    except VersionConflict:
                        return _result(ClaimDisposition.ALREADY_CLAIMED, "CLAIM_VERSION_CONFLICT")
        except Exception:
            return _result(ClaimDisposition.CANNOT_CLAIM, "TECHNICAL_PERSISTENCE_FAILURE")
        if authoritative_replay is not None:
            return _replay_result(authoritative_replay)
        return ClaimResult(ClaimDisposition.CLAIMED, _issue_claimed_capability(claimed_row), "CLAIM_COMMITTED")

    def _replay_result(self, context, authorization) -> _ReplayOutcome:
        if (
            authorization["authorization_state"] != "CLAIMED"
            or authorization["current_version"] != 1
            or not authorization["claimed_by"]
            or _timestamp(authorization["claimed_at"]) is None
        ):
            return _ReplayOutcome(ClaimDisposition.CANNOT_CLAIM, "CLAIMED_ROW_MALFORMED")
        intent = self._persistence.get_intent(context, authorization["intent_id"])
        attempt = self._persistence.get_attempt(context, authorization["submission_attempt_id"])
        if intent is None or attempt is None:
            return _ReplayOutcome(ClaimDisposition.CANNOT_CLAIM, "HISTORICAL_LINEAGE_MISSING")
        binding_reason = self._binding_failure(authorization, intent, attempt)
        if binding_reason is not None:
            disposition = ClaimDisposition.CANNOT_CLAIM if binding_reason.startswith("CANNOT:") else ClaimDisposition.CONFLICT
            return _ReplayOutcome(disposition, binding_reason.removeprefix("CANNOT:"))
        decision = self._persistence.get_decision(context, authorization["authority_reference_id"])
        if decision is None:
            return _ReplayOutcome(ClaimDisposition.CANNOT_CLAIM, "HISTORICAL_DECISION_MISSING")
        envelope = self._persistence.get_envelope(context, decision["authority_envelope_id"])
        if envelope is None:
            return _ReplayOutcome(ClaimDisposition.CANNOT_CLAIM, "HISTORICAL_ENVELOPE_MISSING")
        if not self._replay_binding_is_canonical(authorization, intent, attempt, decision, envelope):
            return _ReplayOutcome(ClaimDisposition.CONFLICT, "HISTORICAL_BINDING_CONFLICT")
        if authorization["claimed_by"] != CLAIMANT_ID:
            return _ReplayOutcome(ClaimDisposition.ALREADY_CLAIMED, "DIFFERENT_CLAIMANT")
        return _ReplayOutcome(ClaimDisposition.CLAIM_REPLAY, "CANONICAL_CLAIM_REPLAY", authorization)

    @staticmethod
    def _binding_failure(authorization, intent, attempt) -> Optional[str]:
        if authorization["intent_id"] != intent["intent_id"]:
            return "INTENT_LINEAGE_MISMATCH"
        if authorization["submission_attempt_id"] != attempt["attempt_id"]:
            return "ATTEMPT_LINEAGE_MISMATCH"
        if attempt["intent_id"] != intent["intent_id"]:
            return "ATTEMPT_INTENT_LINEAGE_MISMATCH"
        for column in ("venue", "account_scope", "client_order_id"):
            if authorization[column] != intent[column] or authorization[column] != attempt[column]:
                return f"{column.upper()}_BINDING_MISMATCH"
        for column in ("symbol", "side", "requested_quote_amount", "requested_base_qty"):
            if authorization[column] != intent[column]:
                return f"{column.upper()}_BINDING_MISMATCH"
        if authorization["authorization_sequence"] != attempt["attempt_sequence"]:
            return "AUTHORIZATION_SEQUENCE_MISMATCH"
        if authorization["issuer_id"] != ISSUER_ID:
            return "ISSUER_MISMATCH"
        if authorization["authority_contract_version"] != SUPPORTED_AUTHORITY_CONTRACT_VERSION:
            return "AUTHORITY_CONTRACT_MISMATCH"
        try:
            expected = submission_fingerprint(
                intent_id=intent["intent_id"], submission_attempt_id=attempt["attempt_id"],
                client_order_id=intent["client_order_id"], venue=intent["venue"],
                account_scope=intent["account_scope"], symbol=intent["symbol"], side=intent["side"],
                requested_quote_amount=intent["requested_quote_amount"], requested_base_qty=intent["requested_base_qty"],
            )
        except (TypeError, ValueError):
            return "SUBMISSION_FINGERPRINT_UNVERIFIABLE"
        return None if authorization["submission_fingerprint"] == expected else "SUBMISSION_FINGERPRINT_MISMATCH"

    @staticmethod
    def _replay_binding_is_canonical(authorization, intent, attempt, decision, envelope) -> bool:
        if decision["intent_id"] != intent["intent_id"] or decision["submission_attempt_id"] != attempt["attempt_id"]:
            return False
        if decision["pre_execution_decision_id"] != authorization["authority_reference_id"]:
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
        claimed_at = _timestamp(authorization["claimed_at"])
        if None in (created_at, evaluated_at, valid_until, valid_from, envelope_until, claimed_at):
            return False
        return (
            decision["decision_engine_version"] == SUPPORTED_DECISION_EVIDENCE_PROFILE
            and evaluated_at <= created_at < valid_until
            and valid_from <= created_at < envelope_until
            and claimed_at >= created_at
        )

    def _currentness_failure(self, context, state, authorization, intent, attempt) -> Optional[str]:
        active_id = state["active_authority_envelope_id"]
        if state["operational_mode"] is None or active_id is None:
            return "CANNOT:AUTHORITY_STATE_INCOMPLETE"
        envelope = self._persistence.get_envelope(context, active_id)
        if envelope is None:
            return "CANNOT:ACTIVE_AUTHORITY_ENVELOPE_MISSING"
        decision = self._persistence.latest_decision(context, attempt["attempt_id"])
        if decision is None:
            return "CANNOT:LATEST_DECISION_MISSING"
        if decision["pre_execution_decision_id"] != authorization["authority_reference_id"]:
            return "LATEST_DECISION_NOT_AUTHORIZATION"
        if self._persistence.has_exchange_evidence(context, attempt["attempt_id"]):
            return "EXTERNAL_EVIDENCE_ALREADY_EXISTS"
        required = (
            state["operational_mode"], envelope["runtime_mode"], envelope["authority_contract_version"],
            intent["venue"], attempt["venue"], envelope["venue"], intent["account_scope"],
            attempt["account_scope"], envelope["account_scope"], intent["side"],
            decision["decision_outcome"], decision["decision_engine_version"], decision["evaluated_at"], decision["valid_until"],
        )
        if any(value is None for value in required):
            return "CANNOT:REQUIRED_AUTHORITY_DATA_MISSING"
        now = datetime.now(timezone.utc)
        if state["operational_mode"] != "OPERATIONAL_ENABLED":
            return "AUTHORITY_STATE_NOT_OPERATIONAL"
        if state["operational_mode"] != envelope["runtime_mode"]:
            return "STATE_ENVELOPE_RUNTIME_MISMATCH"
        if envelope["authority_contract_version"] != SUPPORTED_AUTHORITY_CONTRACT_VERSION:
            return "UNSUPPORTED_AUTHORITY_CONTRACT"
        if not envelope["valid_from"] <= now < envelope["valid_until"]:
            return "AUTHORITY_ENVELOPE_NOT_CURRENT"
        if not (intent["venue"] == attempt["venue"] == envelope["venue"] and intent["account_scope"] == attempt["account_scope"] == envelope["account_scope"] and intent["side"] in envelope["allowed_sides"]):
            return "INTENT_ENVELOPE_SCOPE_MISMATCH"
        if intent["submission_lifecycle_state"] != "SUBMISSION_ATTEMPTED":
            return "INTENT_NOT_SUBMISSION_ATTEMPTED"
        if any(intent[column] is not None for column in ("execution_certainty", "reconciliation_state", "exchange_order_id")):
            return "INTENT_EXTERNAL_HANDOFF"
        if attempt["submission_lifecycle_state"] != "SUBMISSION_ATTEMPTED":
            return "ATTEMPT_NOT_SUBMISSION_ATTEMPTED"
        if attempt["exchange_order_id"] is not None or any(attempt[column] is not None for column in ("transport_status", "transport_error", "observed_at", "exchange_event_time")):
            return "ATTEMPT_EXTERNAL_HANDOFF"
        if decision["decision_outcome"] != "ALLOW":
            return "LATEST_DECISION_NOT_ALLOW"
        if decision["authority_envelope_id"] != active_id:
            return "DECISION_ENVELOPE_MISMATCH"
        if decision["runtime_mode"] != state["operational_mode"]:
            return "DECISION_RUNTIME_MISMATCH"
        if decision["global_safety_epoch"] != state["global_safety_epoch"]:
            return "DECISION_EPOCH_MISMATCH"
        if decision["runtime_generation"] != state["runtime_generation"]:
            return "DECISION_RUNTIME_GENERATION_MISMATCH"
        if not (decision["venue"] == intent["venue"] == attempt["venue"] and decision["account_scope"] == intent["account_scope"] == attempt["account_scope"]):
            return "DECISION_SCOPE_MISMATCH"
        if decision["decision_engine_version"] != SUPPORTED_DECISION_EVIDENCE_PROFILE:
            return "UNSUPPORTED_DECISION_EVIDENCE_PROFILE"
        if not (decision["decision_contract_version"] == envelope["decision_contract_version"] and decision["policy_version"] == envelope["policy_version"] and decision["risk_policy_version"] == envelope["risk_policy_version"] and decision["strategy_version"] == envelope["strategy_version"]):
            return "DECISION_CONTRACT_MISMATCH"
        evaluated_at, valid_until = _timestamp(decision["evaluated_at"]), _timestamp(decision["valid_until"])
        valid_from, envelope_until = _timestamp(envelope["valid_from"]), _timestamp(envelope["valid_until"])
        if None in (evaluated_at, valid_until, valid_from, envelope_until):
            return "CANNOT:INVALID_AUTHORITY_TIMESTAMP"
        if not evaluated_at <= now < valid_until:
            return "DECISION_NOT_CURRENT"
        if not evaluated_at >= valid_from or valid_until > envelope_until:
            return "DECISION_OUTSIDE_ENVELOPE_VALIDITY"
        try:
            if intent_semantic_digest(intent) != decision["intent_semantic_digest"]:
                return "INTENT_SEMANTIC_DIGEST_MISMATCH"
            if attempt_semantic_digest(attempt) != decision["submission_attempt_semantic_digest"]:
                return "ATTEMPT_SEMANTIC_DIGEST_MISMATCH"
        except (KeyError, TypeError, ValueError):
            return "CANNOT:SEMANTIC_DIGEST_UNVERIFIABLE"
        return None


__all__ = ["CLAIMANT_ID", "SubmissionAuthorizationClaimer"]
