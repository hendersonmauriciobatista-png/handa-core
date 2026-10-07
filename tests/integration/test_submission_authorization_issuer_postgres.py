"""Focused PostgreSQL coverage for the Slice 2B3 issuance boundary."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path

import psycopg2
import pytest

from core.execution.authority_digest import attempt_semantic_digest, intent_semantic_digest
from core.execution.submission_authority import submission_fingerprint
from core.execution.submission_authorization_issuer import (
    IssuanceDisposition,
    SubmissionAuthorizationIssuer,
)
from core.persistence.persistence_coordinator import DatabaseIdentity, PersistenceCoordinator
from core.persistence.submission_authorization_issuer_store import (
    SubmissionAuthorizationIssuerPersistence,
    submission_authorization_issuer_resource_scope,
)
from tests.integration.test_pre_execution_decision_evaluator_postgres import (
    EXPECTED_URL,
    IDENTITY,
    MIGRATION_NAMES,
    ROOT,
    _apply,
    _execute,
    _seed_lineage,
)


def _url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value != EXPECTED_URL:
        pytest.skip("ENVIRONMENT_BLOCKED: disposable local PostgreSQL is required")
    return value


@pytest.fixture()
def prepared():
    url = _url()
    _apply(url, include_011=True)
    try:
        yield url
    finally:
        connection = psycopg2.connect(url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            connection.commit()
        finally:
            connection.close()


def _issuer(url: str):
    coordinator = PersistenceCoordinator(
        url, IDENTITY, resource_scope=submission_authorization_issuer_resource_scope()
    )
    return coordinator, SubmissionAuthorizationIssuer(
        SubmissionAuthorizationIssuerPersistence(coordinator)
    )


def _activate(url: str, envelope_id: str, *, mode: str = "OPERATIONAL_ENABLED"):
    _execute(
        url,
        """
        UPDATE handa_live.operational_authority_state
        SET operational_mode=%s, active_authority_envelope_id=%s,
            changed_by='fixture', change_reason='TEST_FIXTURE_AUTHORITY_ONLY'
        WHERE state_id=TRUE
        """,
        (mode, envelope_id),
    )


def _insert_issuer_envelope(
    url: str,
    envelope_id: str,
    *,
    runtime_mode: str = "OPERATIONAL_ENABLED",
    authority_contract_version: str = "submission-authority-v1",
):
    _execute(
        url,
        """
        INSERT INTO handa_live.authority_envelope (
            authority_envelope_id, runtime_mode, venue, account_scope, allowed_sides,
            strategy_version, decision_contract_version, policy_version,
            risk_policy_version, valid_from, valid_until, configuration_digest,
            authority_contract_version, approved_by, approval_reason
        ) VALUES (%s, %s, 'MOCK', 'TEST', ARRAY['BUY'],
                  'strategy-v1', 'decision-contract-v1', 'policy-v1', 'risk-v1',
                  CURRENT_TIMESTAMP - INTERVAL '1 second',
                  CURRENT_TIMESTAMP + INTERVAL '30 seconds', 'config-test', %s,
                  'fixture', 'TEST_FIXTURE_AUTHORITY_ONLY')
        """,
        (envelope_id, runtime_mode, authority_contract_version),
    )


def _lineage_rows(url: str, intent_id: str, attempt_id: str):
    intent = _execute(
        url,
        """
        SELECT intent_id, venue, account_scope, client_order_id, slot_id, symbol,
               side, requested_quote_amount, requested_base_qty, policy_context,
               submission_lifecycle_state, execution_certainty, reconciliation_state,
               exchange_order_id, current_version, current_context_id, current_decision_id,
               recorded_at
        FROM handa_live.order_intent WHERE intent_id=%s
        """,
        (intent_id,),
    )[0]
    attempt = _execute(
        url,
        """
        SELECT attempt_id, intent_id, attempt_sequence, venue, context_id,
               account_scope, client_order_id, submission_lifecycle_state,
               exchange_order_id, transport_status, transport_error, recorded_at,
               observed_at, exchange_event_time
        FROM handa_live.submission_attempt WHERE attempt_id=%s
        """,
        (attempt_id,),
    )[0]
    intent_columns = (
        "intent_id", "venue", "account_scope", "client_order_id", "slot_id", "symbol",
        "side", "requested_quote_amount", "requested_base_qty", "policy_context",
        "submission_lifecycle_state", "execution_certainty", "reconciliation_state",
        "exchange_order_id", "current_version", "current_context_id", "current_decision_id",
        "recorded_at",
    )
    attempt_columns = (
        "attempt_id", "intent_id", "attempt_sequence", "venue", "context_id",
        "account_scope", "client_order_id", "submission_lifecycle_state",
        "exchange_order_id", "transport_status", "transport_error", "recorded_at",
        "observed_at", "exchange_event_time",
    )
    return dict(zip(intent_columns, intent)), dict(zip(attempt_columns, attempt))


def _insert_decision(
    url: str,
    intent_id: str,
    attempt_id: str,
    *,
    decision_id: str = "decision-1",
    sequence: int = 1,
    outcome: str = "ALLOW",
    evaluated_at: datetime | None = None,
    valid_until: datetime | None = None,
    envelope_id: str = "issuer-envelope",
    runtime_mode: str = "OPERATIONAL_ENABLED",
    epoch: int = 0,
    generation: int = 0,
    decision_engine_version: str = "buy-signal-evidence-v1",
    intent_digest: str | None = None,
    attempt_digest: str | None = None,
):
    intent, attempt = _lineage_rows(url, intent_id, attempt_id)
    evaluated_at = evaluated_at or (datetime.now(timezone.utc) - timedelta(seconds=1))
    valid_until = valid_until or (
        evaluated_at if outcome == "BLOCK"
        else datetime.now(timezone.utc) + timedelta(seconds=20)
    )
    intent_digest = intent_digest or intent_semantic_digest(intent)
    attempt_digest = attempt_digest or attempt_semantic_digest(attempt)
    _execute(
        url,
        """
        INSERT INTO handa_live.pre_execution_decision (
            pre_execution_decision_id, intent_id, submission_attempt_id,
            evaluation_request_id, evaluation_request_digest, authority_envelope_id,
            decision_sequence, decision_outcome, decision_reason,
            intent_semantic_digest, submission_attempt_semantic_digest,
            decision_contract_version, decision_engine_version, policy_version,
            risk_policy_version, strategy_version, input_snapshot_digest,
            decision_semantics_digest, global_safety_epoch, runtime_generation,
            runtime_mode, venue, account_scope, evaluated_at, valid_until
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                  'TEST_FIXTURE_AUTHORITY_ONLY', %s, %s,
                  'decision-contract-v1', %s, 'policy-v1', 'risk-v1', 'strategy-v1',
                  'input-fixture', 'semantics-fixture', %s, %s, %s, 'MOCK', 'TEST', %s, %s)
        """,
        (
            decision_id, intent_id, attempt_id,
            f"TEST_ONLY_EVALUATION_IDENTITY-{decision_id}",
            f"TEST_ONLY_EVALUATION_DIGEST-{decision_id}", envelope_id,
            sequence, outcome, intent_digest, attempt_digest,
            decision_engine_version, epoch, generation, runtime_mode,
            evaluated_at, valid_until,
        ),
    )


def _prepare_allow(url: str, prefix: str = "issuer"):
    intent_id, attempt_id = _seed_lineage(url, prefix)
    _insert_issuer_envelope(url, "issuer-envelope")
    _activate(url, "issuer-envelope")
    _insert_decision(url, intent_id, attempt_id)
    return intent_id, attempt_id


def _call_issue(url: str, intent_id: str, attempt_id: str):
    coordinator, issuer = _issuer(url)
    try:
        return issuer.issue(intent_id=intent_id, submission_attempt_id=attempt_id)
    finally:
        coordinator.close()


def test_valid_allow_issues_one_authorization(prepared):
    intent_id, attempt_id = _prepare_allow(prepared)
    result = _call_issue(prepared, intent_id, attempt_id)
    assert result.disposition is IssuanceDisposition.ISSUED
    assert result.submission_authorization_id.startswith("submission-auth-")
    row = _execute(
        prepared,
        """
        SELECT submission_authorization_id, intent_id, submission_attempt_id,
               authority_reference_id, issuer_id, authority_contract_version,
               authorization_sequence, submission_fingerprint, authorization_state
        FROM handa_live.submission_authorization
        """,
    )[0]
    assert row[0] == result.submission_authorization_id
    assert row[1:3] == (intent_id, attempt_id)
    assert row[3] == "decision-1"
    assert row[4:6] == (
        "handa-submission-authorization-issuer", "submission-authority-v1"
    )
    assert row[6] == 1
    assert row[7] == submission_fingerprint(
        intent_id=intent_id, submission_attempt_id=attempt_id,
        client_order_id="issuer-client", venue="MOCK", account_scope="TEST",
        symbol="HYPEUSDC", side="BUY", requested_quote_amount=Decimal("41.41"),
        requested_base_qty=None,
    )
    assert row[8] == "AUTHORIZED"


def test_latest_block_is_not_eligible_and_older_allow_is_not_reused(prepared):
    intent_id, attempt_id = _prepare_allow(prepared)
    _insert_decision(prepared, intent_id, attempt_id, decision_id="decision-2", sequence=2, outcome="BLOCK")
    result = _call_issue(prepared, intent_id, attempt_id)
    assert result.disposition is IssuanceDisposition.NOT_ELIGIBLE
    assert result.reason == "LATEST_DECISION_NOT_ALLOW"
    assert _execute(prepared, "SELECT COUNT(*) FROM handa_live.submission_authorization")[0][0] == 0


def test_newer_allow_is_selected(prepared):
    intent_id, attempt_id = _prepare_allow(prepared)
    _insert_decision(prepared, intent_id, attempt_id, decision_id="decision-2", sequence=2)
    result = _call_issue(prepared, intent_id, attempt_id)
    assert result.disposition is IssuanceDisposition.ISSUED
    assert result.authority_reference_id == "decision-2"


@pytest.mark.parametrize(
    ("change", "expected"),
    (
        ("expired", "DECISION_NOT_CURRENT"),
        ("future", "DECISION_NOT_CURRENT"),
        ("epoch", "DECISION_EPOCH_MISMATCH"),
        ("generation", "DECISION_RUNTIME_GENERATION_MISMATCH"),
        ("runtime", "DECISION_RUNTIME_MISMATCH"),
        ("profile", "UNSUPPORTED_DECISION_EVIDENCE_PROFILE"),
        ("contract", "UNSUPPORTED_AUTHORITY_CONTRACT"),
        ("envelope", "DECISION_ENVELOPE_MISMATCH"),
    ),
)
def test_currentness_guards_fail_closed(prepared, change, expected):
    intent_id, attempt_id = _seed_lineage(prepared, f"guard-{change}")
    envelope_id = "issuer-envelope"
    _insert_issuer_envelope(prepared, envelope_id)
    _activate(prepared, envelope_id)
    now = datetime.now(timezone.utc)
    kwargs = {}
    if change == "expired":
        kwargs.update(evaluated_at=now - timedelta(seconds=5), valid_until=now - timedelta(seconds=1))
    elif change == "future":
        kwargs.update(evaluated_at=now + timedelta(seconds=2), valid_until=now + timedelta(seconds=20))
    elif change == "epoch":
        kwargs["epoch"] = 1
    elif change == "generation":
        kwargs["generation"] = 1
    elif change == "runtime":
        kwargs["runtime_mode"] = "OBSERVE_ONLY"
    elif change == "profile":
        kwargs["decision_engine_version"] = "unsupported-profile"
    elif change == "contract":
        _execute(
            prepared,
            """
            INSERT INTO handa_live.authority_envelope (
                authority_envelope_id, runtime_mode, venue, account_scope, allowed_sides,
                strategy_version, decision_contract_version, policy_version,
                risk_policy_version, valid_from, valid_until, configuration_digest,
                authority_contract_version, approved_by, approval_reason
            ) VALUES ('wrong-envelope', 'OPERATIONAL_ENABLED', 'MOCK', 'TEST', ARRAY['BUY'],
                      'strategy-v1', 'decision-contract-v1', 'policy-v1', 'risk-v1',
                      CURRENT_TIMESTAMP - INTERVAL '1 second', CURRENT_TIMESTAMP + INTERVAL '30 seconds',
                      'config-wrong', 'unsupported-authority', 'fixture',
                      'TEST_FIXTURE_AUTHORITY_ONLY')
            """,
        )
        _execute(prepared, "UPDATE handa_live.operational_authority_state SET active_authority_envelope_id='wrong-envelope' WHERE state_id=TRUE")
        _insert_decision(prepared, intent_id, attempt_id, envelope_id="wrong-envelope")
        result = _call_issue(prepared, intent_id, attempt_id)
        assert result.disposition is IssuanceDisposition.NOT_ELIGIBLE
        assert result.reason == expected
        return
    elif change == "envelope":
        kwargs["envelope_id"] = "wrong-envelope"
        _insert_issuer_envelope(prepared, "wrong-envelope")
    _insert_decision(prepared, intent_id, attempt_id, **kwargs)
    result = _call_issue(prepared, intent_id, attempt_id)
    assert result.disposition is IssuanceDisposition.NOT_ELIGIBLE
    assert result.reason == expected


def test_digest_mismatch_and_prehandoff_guards(prepared):
    intent_id, attempt_id = _seed_lineage(prepared, "digest")
    _insert_issuer_envelope(prepared, "issuer-envelope")
    _activate(prepared, "issuer-envelope")
    _insert_decision(prepared, intent_id, attempt_id, intent_digest="wrong-intent")
    result = _call_issue(prepared, intent_id, attempt_id)
    assert result.disposition is IssuanceDisposition.NOT_ELIGIBLE
    assert result.reason == "INTENT_SEMANTIC_DIGEST_MISMATCH"


@pytest.mark.parametrize(
    "column,value,reason",
    (
        ("execution_certainty", "UNKNOWN", "INTENT_EXTERNAL_HANDOFF"),
        ("reconciliation_state", "PENDING", "INTENT_EXTERNAL_HANDOFF"),
        ("exchange_order_id", "exchange-1", "INTENT_EXTERNAL_HANDOFF"),
    ),
)
def test_intent_prehandoff_guards(prepared, column, value, reason):
    intent_id, attempt_id = _prepare_allow(prepared, f"intent-{column}")
    if column == "execution_certainty":
        _execute(
            prepared,
            "UPDATE handa_live.order_intent SET execution_certainty=%s, reconciliation_state='PENDING' WHERE intent_id=%s",
            (value, intent_id),
        )
    else:
        _execute(prepared, f"UPDATE handa_live.order_intent SET {column}=%s WHERE intent_id=%s", (value, intent_id))
    result = _call_issue(prepared, intent_id, attempt_id)
    assert result.disposition is IssuanceDisposition.NOT_ELIGIBLE
    assert result.reason == reason


def test_attempt_transport_and_exchange_evidence_guards(prepared):
    intent_id, attempt_id = _prepare_allow(prepared, "attempt-transport")
    _execute(prepared, "UPDATE handa_live.submission_attempt SET transport_status='SENT' WHERE attempt_id=%s", (attempt_id,))
    result = _call_issue(prepared, intent_id, attempt_id)
    assert result.disposition is IssuanceDisposition.NOT_ELIGIBLE
    assert result.reason == "ATTEMPT_EXTERNAL_HANDOFF"


def test_exchange_evidence_is_terminal_for_issuance(prepared):
    intent_id, attempt_id = _prepare_allow(prepared, "evidence")
    _execute(
        prepared,
        """
        INSERT INTO handa_live.exchange_evidence (
            evidence_id, intent_id, attempt_id, evidence_sequence, symbol,
            exchange_status, raw_snapshot, observed_at
        ) VALUES ('evidence-1', %s, %s, 1, 'HYPEUSDC', 'NEW', '{}'::jsonb, CURRENT_TIMESTAMP)
        """,
        (intent_id, attempt_id),
    )
    result = _call_issue(prepared, intent_id, attempt_id)
    assert result.disposition is IssuanceDisposition.NOT_ELIGIBLE
    assert result.reason == "EXTERNAL_EVIDENCE_ALREADY_EXISTS"


def test_replay_is_historical_and_survives_authority_change(prepared):
    intent_id, attempt_id = _prepare_allow(prepared, "replay")
    issued = _call_issue(prepared, intent_id, attempt_id)
    replay = _call_issue(prepared, intent_id, attempt_id)
    assert issued.disposition is IssuanceDisposition.ISSUED
    assert replay.disposition is IssuanceDisposition.ALREADY_ISSUED
    _execute(
        prepared,
        "UPDATE handa_live.operational_authority_state SET operational_mode='OBSERVE_ONLY', active_authority_envelope_id=NULL WHERE state_id=TRUE",
    )
    after_change = _call_issue(prepared, intent_id, attempt_id)
    assert after_change.disposition is IssuanceDisposition.ALREADY_ISSUED
    _execute(
        prepared,
        "UPDATE handa_live.submission_authorization SET authorization_state='CLAIMED', current_version=1, claimed_by='fixture' WHERE submission_attempt_id=%s",
        (attempt_id,),
    )
    claimed = _call_issue(prepared, intent_id, attempt_id)
    assert claimed.disposition is IssuanceDisposition.ALREADY_ISSUED
    assert claimed.authorization_state == "CLAIMED"


def test_noncanonical_existing_binding_is_conflict(prepared):
    intent_id, attempt_id = _prepare_allow(prepared, "conflict")
    _execute(
        prepared,
        """
        INSERT INTO handa_live.submission_authorization (
            submission_authorization_id, intent_id, submission_attempt_id,
            client_order_id, venue, account_scope, symbol, side,
            requested_quote_amount, authority_reference_id, issuer_id,
            authority_contract_version, authorization_sequence,
            submission_fingerprint, authorization_state
        ) VALUES ('auth-conflict', %s, %s, 'conflict-client', 'MOCK', 'TEST',
                  'HYPEUSDC', 'BUY', 41.41, 'decision-1',
                  'handa-submission-authorization-issuer', 'submission-authority-v1',
                  1, 'wrong-fingerprint', 'AUTHORIZED')
        """,
        (intent_id, attempt_id),
    )
    result = _call_issue(prepared, intent_id, attempt_id)
    assert result.disposition is IssuanceDisposition.CONFLICT


def test_concurrent_issuers_create_one_row(prepared):
    intent_id, attempt_id = _prepare_allow(prepared, "concurrent")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: _call_issue(prepared, intent_id, attempt_id),
                (1, 2),
            )
        )
    assert sorted(result.disposition.value for result in results) == [
        "ALREADY_ISSUED", "ISSUED"
    ]
    assert _execute(prepared, "SELECT COUNT(*) FROM handa_live.submission_authorization")[0][0] == 1


def test_issuer_boundary_has_no_claim_or_operational_dependencies():
    source = (ROOT / "core" / "execution" / "submission_authorization_issuer.py").read_text()
    for forbidden in (
        "ClaimedSubmissionCapability", "_issue_claimed_capability", "GovernedMockSubmissionGateway",
        "MockExecutor", "BinanceExecutor", "EffectApplicationCoordinator",
        "OperationalEffectAdapter", "PositionManager", "SlotController",
        "SubmissionAuthorizationStore", "gateway", "executor",
    ):
        assert forbidden not in source
    assert "AUTHORIZED" in source
    assert "CLAIMED" in source
