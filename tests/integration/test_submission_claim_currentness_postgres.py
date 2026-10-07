"""PostgreSQL coverage for claim-time currentness and replay semantics."""

from __future__ import annotations

from pathlib import Path

import psycopg2

from core.execution.submission_authorization_claimer import (
    CLAIMANT_ID,
    SubmissionAuthorizationClaimer,
)
from core.execution.submission_authority import ClaimDisposition, SubmissionClaimRequest
from core.persistence.submission_claim_store import SubmissionClaimPersistence
from tests.integration.test_submission_authorization_postgres import prepared


ROOT = Path(__file__).parents[2]


def _request() -> SubmissionClaimRequest:
    return SubmissionClaimRequest("auth-submit-001")


def _execute(url: str, sql: str, parameters=()) -> None:
    connection = psycopg2.connect(url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, parameters)
        connection.commit()
    finally:
        connection.close()


def _claim(coordinator):
    return SubmissionAuthorizationClaimer(
        SubmissionClaimPersistence(coordinator)
    ).claim("auth-submit-001")


def test_public_claim_input_is_only_authorization_id():
    assert SubmissionClaimRequest.__match_args__ == ("submission_authorization_id",)
    assert tuple(SubmissionClaimRequest.__dataclass_fields__) == (
        "submission_authorization_id",
    )


def test_authorized_claim_requires_current_operational_state(prepared):
    url, coordinator, _ = prepared
    _execute(
        url,
        """
        UPDATE handa_live.operational_authority_state
        SET operational_mode = 'OBSERVE_ONLY'
        WHERE state_id IS TRUE
        """,
    )
    result = _claim(coordinator)
    assert result.disposition is ClaimDisposition.NOT_CURRENT
    assert result.capability is None


def test_newer_block_invalidates_authorization(prepared):
    url, coordinator, _ = prepared
    _execute(
        url,
        """
        INSERT INTO handa_live.pre_execution_decision (
            pre_execution_decision_id, intent_id, submission_attempt_id,
            evaluation_request_id, evaluation_request_digest,
            authority_envelope_id, decision_sequence, decision_outcome,
            decision_reason, intent_semantic_digest,
            submission_attempt_semantic_digest, decision_contract_version,
            decision_engine_version, policy_version, risk_policy_version,
            strategy_version, input_snapshot_digest, decision_semantics_digest,
            global_safety_epoch, runtime_generation, runtime_mode, venue,
            account_scope, evaluated_at, valid_until
        ) VALUES (
            'pre-execution-decision-newer-block', 'intent-submit-001',
            'attempt-submit-001', 'evaluation-newer-block', 'digest-newer-block',
            'envelope-submit-001', 2, 'BLOCK', 'newer decision',
            'intent-digest-newer-block', 'attempt-digest-newer-block',
            'decision-contract-v1', 'buy-signal-evidence-v1', 'policy-test-v1',
            'risk-policy-test-v1', 'strategy-test-v1', 'input-newer-block',
            'semantics-newer-block', 0, 0, 'OPERATIONAL_ENABLED', 'MOCK', 'TEST',
            TIMESTAMPTZ '2020-01-01 00:00:00+00',
            TIMESTAMPTZ '2020-01-01 00:00:00+00'
        )
        """,
    )
    result = _claim(coordinator)
    assert result.disposition is ClaimDisposition.NOT_CURRENT
    assert result.capability is None


def test_newer_allow_invalidates_old_authorization(prepared):
    url, coordinator, _ = prepared
    _execute(
        url,
        """
        INSERT INTO handa_live.pre_execution_decision (
            pre_execution_decision_id, intent_id, submission_attempt_id,
            evaluation_request_id, evaluation_request_digest,
            authority_envelope_id, decision_sequence, decision_outcome,
            decision_reason, intent_semantic_digest,
            submission_attempt_semantic_digest, decision_contract_version,
            decision_engine_version, policy_version, risk_policy_version,
            strategy_version, input_snapshot_digest, decision_semantics_digest,
            global_safety_epoch, runtime_generation, runtime_mode, venue,
            account_scope, evaluated_at, valid_until
        ) VALUES (
            'pre-execution-decision-newer-allow', 'intent-submit-001',
            'attempt-submit-001', 'evaluation-newer-allow', 'digest-newer-allow',
            'envelope-submit-001', 2, 'ALLOW', 'newer decision',
            'intent-digest-newer-allow', 'attempt-digest-newer-allow',
            'decision-contract-v1', 'buy-signal-evidence-v1', 'policy-test-v1',
            'risk-policy-test-v1', 'strategy-test-v1', 'input-newer-allow',
            'semantics-newer-allow', 0, 0, 'OPERATIONAL_ENABLED', 'MOCK', 'TEST',
            TIMESTAMPTZ '2020-01-01 00:00:00+00',
            TIMESTAMPTZ '2020-01-02 00:00:00+00'
        )
        """,
    )
    result = _claim(coordinator)
    assert result.disposition is ClaimDisposition.NOT_CURRENT
    assert result.capability is None


def test_replay_does_not_revalidate_current_authority(prepared):
    url, coordinator, _ = prepared
    first = _claim(coordinator)
    assert first.disposition is ClaimDisposition.CLAIMED
    _execute(
        url,
        """
        UPDATE handa_live.operational_authority_state
        SET operational_mode = 'OBSERVE_ONLY'
        WHERE state_id IS TRUE
        """,
    )
    replay = _claim(coordinator)
    assert replay.disposition is ClaimDisposition.CLAIM_REPLAY
    assert replay.capability is not None
    assert replay.capability.claimed_by == CLAIMANT_ID


def test_different_claimant_never_receives_replay_capability(prepared):
    url, coordinator, _ = prepared
    _execute(
        url,
        """
        UPDATE handa_live.submission_authorization
        SET authorization_state = 'CLAIMED', current_version = 1,
            claimed_by = 'different-claimant', claimed_at = CURRENT_TIMESTAMP
        WHERE submission_authorization_id = 'auth-submit-001'
        """,
    )
    result = _claim(coordinator)
    assert result.disposition is ClaimDisposition.ALREADY_CLAIMED
    assert result.capability is None


def test_legacy_store_cannot_bypass_governed_claimer():
    source = (ROOT / "core" / "persistence" / "submission_authorization_store.py").read_text(encoding="utf-8")
    assert "_matches_request" not in source
    assert "update_if_version" not in source
    assert "SubmissionAuthorizationClaimer" in source
