"""Fail-safe Slice 2B2 contracts against disposable PostgreSQL."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest

from core.decision.decision_engine import BuySignal, MarketSnapshot
from core.execution.authority_digest import evaluation_request_digest
from core.execution.live_order_models import LiveOrderIntent, OrderSide
from core.execution.pre_execution_candidate_evidence import (
    DECISION_ENGINE_EVIDENCE_PROFILE_VERSION,
    DECISION_ENGINE_EVIDENCE_SOURCE_COMPONENT,
    PreExecutionCandidateEvidence,
)
from core.execution.pre_execution_decision_evaluator import (
    EvaluationDisposition,
    PreExecutionDecisionEvaluator,
)
from core.persistence.live_order_store import LiveOrderStore, live_order_resource_scope
from core.persistence.persistence_coordinator import DatabaseIdentity, PersistenceCoordinator
from core.persistence.pre_execution_evaluation_store import (
    PreExecutionEvaluationPersistence,
    pre_execution_evaluation_resource_scope,
)


ROOT = Path(__file__).parents[2]
EXPECTED_URL = "postgresql://handa_test:handa_test_only@127.0.0.1:55432/handa_test"
IDENTITY = DatabaseIdentity(frozenset({"127.0.0.1", "localhost"}), 55432, "handa_test", "handa_test")
MIGRATION_NAMES = (
    "001_create_handa_live.sql",
    "002_relax_may_have_been_submitted_certainty.sql",
    "003_reconciliation_evidence.sql",
    "004_external_order_observation_contract.sql",
    "005_decision_ledger.sql",
    "006_effect_application_ledger.sql",
    "007_position_effect_authority.sql",
    "008_effect_request_logical_binding.sql",
    "009_submission_authorization.sql",
    "010_submission_authority_envelope_and_decision.sql",
    "011_pre_execution_evaluation_idempotency.sql",
)


def _url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value != EXPECTED_URL:
        pytest.skip("ENVIRONMENT_BLOCKED: disposable local PostgreSQL is required")
    parsed = urlparse(value)
    if not IDENTITY.matches_url(value) or parsed.username != IDENTITY.user:
        pytest.fail("test database identity is outside the disposable database")
    return value


def _apply(url: str, *, include_011: bool) -> None:
    names = MIGRATION_NAMES if include_011 else MIGRATION_NAMES[:-1]
    connection = psycopg2.connect(url)
    try:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            for name in names:
                cursor.execute((ROOT / "core" / "persistence" / "migrations" / name).read_text())
        connection.commit()
    finally:
        connection.close()


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


def _execute(url: str, statement: str, parameters=()):
    connection = psycopg2.connect(url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            rows = cursor.fetchall() if cursor.description else None
        connection.commit()
        return rows
    finally:
        connection.close()


def _seed_lineage(url: str, prefix: str, *, side: OrderSide = OrderSide.BUY):
    intent_id = f"{prefix}-intent"
    attempt_id = f"{prefix}-attempt"
    client_order_id = f"{prefix}-client"
    coordinator = PersistenceCoordinator(url, IDENTITY, resource_scope=live_order_resource_scope())
    try:
        store = LiveOrderStore(coordinator)
        kwargs = {
            "requested_quote_amount": Decimal("41.41") if side is OrderSide.BUY else None,
            "requested_base_qty": None if side is OrderSide.BUY else Decimal("0.01"),
        }
        store.create_intent(
            LiveOrderIntent(
                intent_id=intent_id,
                client_order_id=client_order_id,
                slot_id=f"{prefix}-slot",
                symbol="HYPEUSDC",
                side=side,
                policy_context="TEST_FIXTURE_AUTHORITY_ONLY",
                **kwargs,
            ),
            venue="MOCK",
            account_scope="TEST",
        )
        store.record_submission_preparation(
            intent_id=intent_id,
            attempt_id=attempt_id,
            attempt_sequence=1,
            venue="MOCK",
            account_scope="TEST",
            client_order_id=client_order_id,
            expected_version=0,
        )
    finally:
        coordinator.close()
    return intent_id, attempt_id


def _insert_envelope(
    url: str,
    envelope_id: str,
    *,
    runtime_mode: str = "OBSERVE_ONLY",
    expires: bool = False,
    venue: str = "MOCK",
    account_scope: str = "TEST",
):
    valid_from_interval = "- INTERVAL '2 seconds'" if expires else "- INTERVAL '1 second'"
    valid_until_interval = "- INTERVAL '1 second'" if expires else "+ INTERVAL '30 seconds'"
    _execute(
        url,
        f"""
        INSERT INTO handa_live.authority_envelope (
            authority_envelope_id, runtime_mode, venue, account_scope, allowed_sides,
            strategy_version, decision_contract_version, policy_version,
            risk_policy_version, valid_from, valid_until, configuration_digest,
            authority_contract_version, approved_by, approval_reason
        ) VALUES (%s, %s, %s, %s, ARRAY['BUY'],
                  'strategy-v1', 'decision-contract-v1', 'policy-v1', 'risk-v1',
                  CURRENT_TIMESTAMP {valid_from_interval},
                  CURRENT_TIMESTAMP {valid_until_interval}, 'config-test', 'authority-v1',
                  'fixture', 'TEST_FIXTURE_AUTHORITY_ONLY')
        """,
        (envelope_id, runtime_mode, venue, account_scope),
    )


def _activate_fixture_state(url: str, envelope_id: str | None):
    _execute(
        url,
        """
        UPDATE handa_live.operational_authority_state
        SET operational_mode='OBSERVE_ONLY', active_authority_envelope_id=%s,
            changed_by='fixture', change_reason='TEST_FIXTURE_AUTHORITY_ONLY'
        WHERE state_id=TRUE
        """,
        (envelope_id,),
    )


def _evidence(
    *,
    symbol: str = "HYPEUSDC",
    reason: str = "TEST_CANDIDATE",
    produced_at: datetime | None = None,
):
    snapshot = MarketSnapshot(
        pair=symbol, price=100.0, rsi=55.0, ema_fast=101.0, ema_slow=99.0,
        volume_ratio=2.0, atr=0.3, trend="UPTREND", momentum="BULLISH",
        market_state="TRADE_OK",
    )
    signal = BuySignal(
        pair=symbol, entry_price=100.0, allocated_usdc=41.41,
        stop_loss=99.0, take_profit=102.0, confidence=0.9,
        reasons=[reason], timestamp=produced_at or datetime.now(timezone.utc),
    )
    return PreExecutionCandidateEvidence.from_buy_signal(snapshot, signal)


def _evaluator(url: str):
    coordinator = PersistenceCoordinator(
        url, IDENTITY, resource_scope=pre_execution_evaluation_resource_scope()
    )
    persistence = PreExecutionEvaluationPersistence(coordinator)
    return coordinator, PreExecutionDecisionEvaluator(persistence)


def test_evidence_profile_is_internal_buy_only_and_stable():
    produced_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    evidence_a = _evidence(produced_at=produced_at)
    evidence_b = _evidence(produced_at=produced_at)
    assert evidence_a.source_component == DECISION_ENGINE_EVIDENCE_SOURCE_COMPONENT
    assert evidence_a.source_contract_version == DECISION_ENGINE_EVIDENCE_PROFILE_VERSION
    assert evidence_a.side == "BUY"
    assert evidence_a.candidate_id == f"candidate-{evidence_a.evidence_digest}"
    assert evidence_a.market_snapshot_digest
    assert evidence_a.strategy_decision_digest
    assert evidence_a.evidence_digest != ""
    assert evidence_a.candidate_id != ""
    assert evidence_a.__dict__.get("requested_quote_amount") is None
    assert evidence_a.__dict__.get("allocated_usdc") is None
    assert evidence_a.evidence_digest == evidence_b.evidence_digest
    assert evidence_a.produced_at == evidence_b.produced_at


def test_evidence_rejects_snapshot_signal_mismatch():
    snapshot = MarketSnapshot(
        pair="HYPEUSDC", price=100.0, rsi=55.0, ema_fast=101.0, ema_slow=99.0,
        volume_ratio=2.0, atr=0.3,
    )
    signal = BuySignal(
        pair="OTHERUSDC", entry_price=100.0, allocated_usdc=1.0,
        stop_loss=99.0, take_profit=102.0, confidence=0.9, reasons=["TEST"],
    )
    with pytest.raises(ValueError, match="symbols must match"):
        PreExecutionCandidateEvidence.from_buy_signal(snapshot, signal)


def test_request_digest_excludes_mutable_authority_state():
    evidence = _evidence()
    first = evaluation_request_digest(
        intent_id="intent-1", submission_attempt_id="attempt-1",
        upstream_evidence_digest_value=evidence.evidence_digest,
    )
    second = evaluation_request_digest(
        intent_id="intent-1", submission_attempt_id="attempt-1",
        upstream_evidence_digest_value=evidence.evidence_digest,
    )
    assert first == second


def test_migration_011_columns_and_validity_contract(prepared):
    rows = _execute(
        prepared,
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='handa_live' AND table_name='pre_execution_decision'
          AND column_name IN ('evaluation_request_id', 'evaluation_request_digest')
        ORDER BY column_name
        """,
    )
    assert [row[0] for row in rows] == ["evaluation_request_digest", "evaluation_request_id"]


def test_migration_011_validity_is_outcome_aware(prepared):
    intent_id, attempt_id = _seed_lineage(prepared, "validity")
    _insert_envelope(prepared, "validity-envelope")
    evaluated_at = datetime.now(timezone.utc)

    def insert_direct(decision_id, outcome, valid_until):
        _execute(
            prepared,
            """
            INSERT INTO handa_live.pre_execution_decision (
                pre_execution_decision_id, intent_id, submission_attempt_id,
                authority_envelope_id, decision_sequence, decision_outcome,
                decision_reason, intent_semantic_digest, submission_attempt_semantic_digest,
                decision_contract_version, decision_engine_version, policy_version,
                risk_policy_version, strategy_version, input_snapshot_digest,
                decision_semantics_digest, global_safety_epoch, runtime_generation,
                runtime_mode, venue, account_scope, evaluated_at, valid_until,
                evaluation_request_id, evaluation_request_digest
            ) VALUES (
                %s, %s, %s, 'validity-envelope', %s, %s,
                'TEST_FIXTURE_AUTHORITY_ONLY', 'intent', 'attempt', 'decision',
                'buy-signal-evidence-v1', 'policy', 'risk', 'strategy', 'input',
                'semantics', 0, 0, 'OBSERVE_ONLY', 'MOCK', 'TEST', %s, %s, %s, %s
            )
            """,
            (
                decision_id,
                intent_id,
                attempt_id,
                int(decision_id.rsplit("-", 1)[-1]),
                outcome,
                evaluated_at,
                valid_until,
                f"TEST_ONLY_EVALUATION_IDENTITY-{decision_id}",
                f"TEST_ONLY_EVALUATION_DIGEST-{decision_id}",
            ),
        )

    insert_direct("valid-1", "ALLOW", evaluated_at + timedelta(seconds=1))
    insert_direct("valid-2", "BLOCK", evaluated_at)
    with pytest.raises(psycopg2.errors.CheckViolation):
        insert_direct("invalid-1", "ALLOW", evaluated_at)
    with pytest.raises(psycopg2.errors.CheckViolation):
        insert_direct("invalid-2", "BLOCK", evaluated_at + timedelta(seconds=1))
    with pytest.raises(psycopg2.errors.CheckViolation):
        insert_direct("invalid-3", "BLOCK", evaluated_at - timedelta(seconds=1))


def test_migration_011_fails_closed_on_historical_decision():
    url = _url()
    _apply(url, include_011=False)
    try:
        _seed_lineage(url, "legacy")
        _insert_envelope(url, "legacy-envelope")
        _execute(
            url,
            """
            INSERT INTO handa_live.pre_execution_decision (
                pre_execution_decision_id, intent_id, submission_attempt_id,
                authority_envelope_id, decision_sequence, decision_outcome,
                decision_reason, intent_semantic_digest, submission_attempt_semantic_digest,
                decision_contract_version, decision_engine_version, policy_version,
                risk_policy_version, strategy_version, input_snapshot_digest,
                decision_semantics_digest, global_safety_epoch, runtime_generation,
                runtime_mode, venue, account_scope, evaluated_at, valid_until
            ) VALUES (
                'legacy-decision', 'legacy-intent', 'legacy-attempt', 'legacy-envelope', 1,
                'ALLOW', 'TEST_FIXTURE_AUTHORITY_ONLY', 'i', 'a', 'd', 'e', 'p', 'r', 's',
                'input', 'semantics', 0, 0, 'OBSERVE_ONLY', 'MOCK', 'TEST',
                CURRENT_TIMESTAMP - INTERVAL '1 second', CURRENT_TIMESTAMP + INTERVAL '1 second'
            )
            """,
        )
        connection = psycopg2.connect(url)
        try:
            with connection.cursor() as cursor:
                with pytest.raises(psycopg2.Error, match="requires an empty"):
                    cursor.execute((ROOT / "core/persistence/migrations/011_pre_execution_evaluation_idempotency.sql").read_text())
            connection.rollback()
        finally:
            connection.close()
    finally:
        connection = psycopg2.connect(url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            connection.commit()
        finally:
            connection.close()


def test_observe_only_records_block_with_zero_future_validity(prepared):
    intent_id, attempt_id = _seed_lineage(prepared, "observe")
    _insert_envelope(prepared, "observe-envelope", runtime_mode="OBSERVE_ONLY")
    _activate_fixture_state(prepared, "observe-envelope")
    coordinator, evaluator = _evaluator(prepared)
    try:
        result = evaluator.evaluate(
            evaluation_request_id="observe-request",
            intent_id=intent_id,
            submission_attempt_id=attempt_id,
            evidence=_evidence(),
        )
    finally:
        coordinator.close()
    assert result.disposition is EvaluationDisposition.RECORDED_BLOCK
    assert result.decision_outcome == "BLOCK"
    rows = _execute(
        prepared,
        "SELECT evaluated_at, valid_until FROM handa_live.pre_execution_decision WHERE evaluation_request_id='observe-request'",
    )
    assert len(rows) == 1
    assert rows[0][0] == rows[0][1]


def test_no_active_envelope_is_cannot_evaluate_without_row(prepared):
    intent_id, attempt_id = _seed_lineage(prepared, "no-envelope")
    _activate_fixture_state(prepared, None)
    coordinator, evaluator = _evaluator(prepared)
    try:
        result = evaluator.evaluate(
            evaluation_request_id="no-envelope-request",
            intent_id=intent_id,
            submission_attempt_id=attempt_id,
            evidence=_evidence(),
        )
    finally:
        coordinator.close()
    assert result.disposition is EvaluationDisposition.CANNOT_EVALUATE
    assert _execute(
        prepared,
        "SELECT COUNT(*) FROM handa_live.pre_execution_decision",
    )[0][0] == 0


def test_operational_enabled_allow_eligible_path_remains_fail_safe(prepared):
    intent_id, attempt_id = _seed_lineage(prepared, "allow-gate")
    _insert_envelope(prepared, "allow-envelope", runtime_mode="OPERATIONAL_ENABLED")
    _execute(
        prepared,
        "UPDATE handa_live.operational_authority_state SET operational_mode='OPERATIONAL_ENABLED', active_authority_envelope_id='allow-envelope' WHERE state_id=TRUE",
    )
    coordinator, evaluator = _evaluator(prepared)
    try:
        result = evaluator.evaluate(
            evaluation_request_id="allow-gate-request",
            intent_id=intent_id,
            submission_attempt_id=attempt_id,
            evidence=_evidence(),
        )
    finally:
        coordinator.close()
    assert result.disposition is EvaluationDisposition.CANNOT_EVALUATE
    assert result.reason == "FRESHNESS_POLICY_UNAVAILABLE"
    assert _execute(prepared, "SELECT COUNT(*) FROM handa_live.pre_execution_decision")[0][0] == 0


def test_expired_envelope_records_block(prepared):
    intent_id, attempt_id = _seed_lineage(prepared, "expired")
    _insert_envelope(prepared, "expired-envelope", runtime_mode="OBSERVE_ONLY", expires=True)
    _activate_fixture_state(prepared, "expired-envelope")
    coordinator, evaluator = _evaluator(prepared)
    try:
        result = evaluator.evaluate(
            evaluation_request_id="expired-request",
            intent_id=intent_id,
            submission_attempt_id=attempt_id,
            evidence=_evidence(),
        )
    finally:
        coordinator.close()
    assert result.disposition is EvaluationDisposition.RECORDED_BLOCK
    assert result.reason == "AUTHORITY_ENVELOPE_EXPIRED_OR_NOT_YET_VALID"


@pytest.mark.parametrize(
    ("case_name", "envelope_kwargs", "seed_side", "evidence_symbol", "reason"),
    (
        ("wrong-side", {}, OrderSide.SELL, "HYPEUSDC", "SIDE_NOT_PERMITTED"),
        ("wrong-venue", {"venue": "OTHER"}, OrderSide.BUY, "HYPEUSDC", "VENUE_MISMATCH"),
        ("wrong-account", {"account_scope": "OTHER"}, OrderSide.BUY, "HYPEUSDC", "ACCOUNT_SCOPE_MISMATCH"),
        ("symbol-mismatch", {}, OrderSide.BUY, "OTHERUSDC", "EVIDENCE_SYMBOL_MISMATCH"),
    ),
)
def test_legitimate_mismatches_record_block(
    prepared, case_name, envelope_kwargs, seed_side, evidence_symbol, reason
):
    intent_id, attempt_id = _seed_lineage(prepared, case_name, side=seed_side)
    _insert_envelope(prepared, f"{case_name}-envelope", **envelope_kwargs)
    _activate_fixture_state(prepared, f"{case_name}-envelope")
    coordinator, evaluator = _evaluator(prepared)
    try:
        result = evaluator.evaluate(
            evaluation_request_id=f"{case_name}-request",
            intent_id=intent_id,
            submission_attempt_id=attempt_id,
            evidence=_evidence(symbol=evidence_symbol),
        )
    finally:
        coordinator.close()
    assert result.disposition is EvaluationDisposition.RECORDED_BLOCK
    assert result.reason == reason


def test_missing_state_is_cannot_evaluate_without_row(prepared):
    intent_id, attempt_id = _seed_lineage(prepared, "missing-state")
    _execute(prepared, "DELETE FROM handa_live.operational_authority_state")
    coordinator, evaluator = _evaluator(prepared)
    try:
        result = evaluator.evaluate(
            evaluation_request_id="missing-state-request",
            intent_id=intent_id,
            submission_attempt_id=attempt_id,
            evidence=_evidence(),
        )
    finally:
        coordinator.close()
    assert result.disposition is EvaluationDisposition.CANNOT_EVALUATE
    assert result.reason == "STATE_MISSING"
    assert _execute(prepared, "SELECT COUNT(*) FROM handa_live.pre_execution_decision")[0][0] == 0


def test_malformed_and_unsupported_evidence_are_cannot_evaluate(prepared):
    intent_id, attempt_id = _seed_lineage(prepared, "bad-evidence")
    _insert_envelope(prepared, "bad-evidence-envelope")
    _activate_fixture_state(prepared, "bad-evidence-envelope")
    coordinator, evaluator = _evaluator(prepared)
    try:
        malformed = evaluator.evaluate(
            evaluation_request_id="malformed-evidence-request",
            intent_id=intent_id,
            submission_attempt_id=attempt_id,
            evidence=object(),
        )
        unsupported = _evidence()
        object.__setattr__(unsupported, "source_contract_version", "unsupported-profile")
        unsupported_result = evaluator.evaluate(
            evaluation_request_id="unsupported-evidence-request",
            intent_id=intent_id,
            submission_attempt_id=attempt_id,
            evidence=unsupported,
        )
    finally:
        coordinator.close()
    assert malformed.disposition is EvaluationDisposition.CANNOT_EVALUATE
    assert malformed.reason == "MALFORMED_EVIDENCE"
    assert unsupported_result.disposition is EvaluationDisposition.CANNOT_EVALUATE
    assert unsupported_result.reason == "UNSUPPORTED_EVIDENCE_PROFILE"
    assert _execute(prepared, "SELECT COUNT(*) FROM handa_live.pre_execution_decision")[0][0] == 0


def test_replay_conflict_and_reevaluation_sequences(prepared):
    intent_id, attempt_id = _seed_lineage(prepared, "replay")
    _insert_envelope(prepared, "replay-envelope")
    _activate_fixture_state(prepared, "replay-envelope")
    evidence = _evidence()
    coordinator, evaluator = _evaluator(prepared)
    try:
        first = evaluator.evaluate(
            evaluation_request_id="replay-r1", intent_id=intent_id,
            submission_attempt_id=attempt_id, evidence=evidence,
        )
        replay = evaluator.evaluate(
            evaluation_request_id="replay-r1", intent_id=intent_id,
            submission_attempt_id=attempt_id, evidence=evidence,
        )
        conflict = evaluator.evaluate(
            evaluation_request_id="replay-r1", intent_id=intent_id,
            submission_attempt_id=attempt_id, evidence=_evidence(reason="DIFFERENT"),
        )
        reevaluation = evaluator.evaluate(
            evaluation_request_id="replay-r2", intent_id=intent_id,
            submission_attempt_id=attempt_id, evidence=evidence,
        )
    finally:
        coordinator.close()
    assert first.disposition is EvaluationDisposition.RECORDED_BLOCK
    assert replay.disposition is EvaluationDisposition.ALREADY_RECORDED
    assert replay.decision_sequence == first.decision_sequence
    assert conflict.disposition is EvaluationDisposition.CONFLICT
    assert reevaluation.disposition is EvaluationDisposition.RECORDED_BLOCK
    assert reevaluation.decision_sequence == first.decision_sequence + 1


def test_concurrent_same_request_has_one_row(prepared):
    intent_id, attempt_id = _seed_lineage(prepared, "concurrent")
    _insert_envelope(prepared, "concurrent-envelope")
    _activate_fixture_state(prepared, "concurrent-envelope")
    evidence = _evidence()

    def run_once():
        coordinator, evaluator = _evaluator(prepared)
        try:
            return evaluator.evaluate(
                evaluation_request_id="concurrent-r1",
                intent_id=intent_id,
                submission_attempt_id=attempt_id,
                evidence=evidence,
            )
        finally:
            coordinator.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run_once(), (1, 2)))
    assert {result.disposition for result in results} == {
        EvaluationDisposition.RECORDED_BLOCK,
        EvaluationDisposition.ALREADY_RECORDED,
    }
    assert _execute(
        prepared,
        "SELECT COUNT(*) FROM handa_live.pre_execution_decision WHERE evaluation_request_id='concurrent-r1'",
    )[0][0] == 1


def test_concurrent_reevaluations_receive_distinct_sequences(prepared):
    intent_id, attempt_id = _seed_lineage(prepared, "concurrent-reevaluation")
    _insert_envelope(prepared, "concurrent-reevaluation-envelope")
    _activate_fixture_state(prepared, "concurrent-reevaluation-envelope")
    evidence = _evidence()

    def run_once(request_id):
        coordinator, evaluator = _evaluator(prepared)
        try:
            return evaluator.evaluate(
                evaluation_request_id=request_id,
                intent_id=intent_id,
                submission_attempt_id=attempt_id,
                evidence=evidence,
            )
        finally:
            coordinator.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run_once, ("concurrent-r1", "concurrent-r2")))
    assert all(result.disposition is EvaluationDisposition.RECORDED_BLOCK for result in results)
    assert sorted(result.decision_sequence for result in results) == [1, 2]
