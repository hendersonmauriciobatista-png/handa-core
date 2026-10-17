"""Slice 2B7 runtime wiring against disposable PostgreSQL."""

from __future__ import annotations

from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest

from core.decision.decision_engine import BuySignal, MarketSnapshot
from core.execution.pre_execution_runtime_coordinator import (
    PreExecutionRuntimeCoordinator,
    PreExecutionRuntimeProposal,
)
from core.governed_runtime_composition import (
    GOVERNED_INFRASTRUCTURE_READY,
    GovernedRuntimeComposition,
    RuntimeCompositionConfig,
)
from core.persistence.persistence_coordinator import DatabaseIdentity


ROOT = Path(__file__).parents[2]
EXPECTED_URL = "postgresql://handa_test:handa_test_only@127.0.0.1:55432/handa_test"
IDENTITY = DatabaseIdentity(
    frozenset({"127.0.0.1", "localhost"}), 55432, "handa_test", "handa_test"
)
MIGRATION_NAMES = tuple(
    f"{number:03d}_{name}"
    for number, name in (
        (1, "create_handa_live.sql"),
        (2, "relax_may_have_been_submitted_certainty.sql"),
        (3, "reconciliation_evidence.sql"),
        (4, "external_order_observation_contract.sql"),
        (5, "decision_ledger.sql"),
        (6, "effect_application_ledger.sql"),
        (7, "position_effect_authority.sql"),
        (8, "effect_request_logical_binding.sql"),
        (9, "submission_authorization.sql"),
        (10, "submission_authority_envelope_and_decision.sql"),
        (11, "pre_execution_evaluation_idempotency.sql"),
        (12, "governed_transport_submission.sql"),
    )
)


def _url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value != EXPECTED_URL:
        pytest.skip("ENVIRONMENT_BLOCKED: disposable local PostgreSQL is required")
    parsed = urlparse(value)
    if not IDENTITY.matches_url(value) or parsed.username != IDENTITY.user:
        pytest.fail("test database identity is outside the disposable database")
    return value


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


@pytest.fixture()
def runtime():
    url = _url()
    connection = psycopg2.connect(url)
    try:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            for name in MIGRATION_NAMES:
                cursor.execute(
                    (ROOT / "core" / "persistence" / "migrations" / name).read_text(
                        encoding="utf-8"
                    )
                )
        connection.commit()
    finally:
        connection.close()

    composition = None
    coordinator = None
    try:
        yield url
    finally:
        if coordinator is not None:
            coordinator.close()
        if composition is not None:
            composition.close()
        _execute(url, "DROP SCHEMA IF EXISTS handa_live CASCADE")


def _proposal():
    snapshot = MarketSnapshot(
        pair="HYPEUSDC", price=100.0, rsi=55.0, ema_fast=101.0,
        ema_slow=99.0, volume_ratio=2.0, atr=0.3, trend="UPTREND",
        momentum="BULLISH", market_state="TRADE_OK",
    )
    signal = BuySignal(
        pair="HYPEUSDC", entry_price=100.0, allocated_usdc=41.41,
        stop_loss=99.0, take_profit=102.0, confidence=0.9,
        reasons=["TEST_CANDIDATE"],
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    return PreExecutionRuntimeProposal.from_buy_signal(snapshot, signal).bind_slot("1")


def _activate(url: str, *, allowed_side: str):
    _execute(
        url,
        """
        INSERT INTO handa_live.authority_envelope (
            authority_envelope_id, runtime_mode, venue, account_scope, allowed_sides,
            strategy_version, decision_contract_version, policy_version,
            risk_policy_version, valid_from, valid_until, configuration_digest,
            authority_contract_version, approved_by, approval_reason
        ) VALUES ('2b7-envelope', 'OPERATIONAL_ENABLED', 'MOCK', 'TEST', ARRAY[%s],
            'strategy-v1', 'decision-contract-v1', 'policy-v1', 'risk-v1',
            CURRENT_TIMESTAMP - INTERVAL '1 second',
            CURRENT_TIMESTAMP + INTERVAL '30 seconds', 'config-test', 'authority-v1',
            'fixture', 'TEST_FIXTURE_AUTHORITY_ONLY')
        """,
        (allowed_side,),
    )
    _execute(
        url,
        """
        UPDATE handa_live.operational_authority_state
        SET operational_mode='OPERATIONAL_ENABLED',
            active_authority_envelope_id='2b7-envelope',
            changed_by='fixture', change_reason='TEST_FIXTURE_AUTHORITY_ONLY'
        WHERE state_id=TRUE
        """,
    )


def _coordinator(url: str):
    config = RuntimeCompositionConfig(url, IDENTITY)
    composition = GovernedRuntimeComposition(config)
    boot = composition.boot()
    assert boot.posture == GOVERNED_INFRASTRUCTURE_READY
    return composition, PreExecutionRuntimeCoordinator(config, boot)


def test_runtime_coordinator_records_block_and_replays_idempotently(runtime):
    _activate(runtime, allowed_side="SELL")
    composition, coordinator = _coordinator(runtime)
    try:
        first = coordinator.evaluate(_proposal())
        second = coordinator.evaluate(_proposal())
    finally:
        coordinator.close()
        composition.close()

    assert first.disposition == "RECORDED_BLOCK"
    assert second.disposition == "ALREADY_RECORDED"
    assert first.intent_id == second.intent_id
    assert first.submission_attempt_id == second.submission_attempt_id
    rows = _execute(
        runtime,
        "SELECT COUNT(*), MIN(submission_lifecycle_state) FROM handa_live.order_intent",
    )
    assert rows == [(1, "SUBMISSION_ATTEMPTED")]
    rows = _execute(
        runtime,
        "SELECT COUNT(*) FROM handa_live.pre_execution_decision",
    )
    assert rows == [(1,)]


def test_current_production_allow_remains_unreachable(runtime):
    _activate(runtime, allowed_side="BUY")
    composition, coordinator = _coordinator(runtime)
    try:
        result = coordinator.evaluate(_proposal())
    finally:
        coordinator.close()
        composition.close()

    assert result.disposition == "CANNOT_EVALUATE"
    assert result.reason == "FRESHNESS_POLICY_UNAVAILABLE"
    assert _execute(runtime, "SELECT COUNT(*) FROM handa_live.pre_execution_decision") == [(0,)]


def test_concurrent_identical_proposals_reuse_one_lineage(runtime):
    _activate(runtime, allowed_side="SELL")

    def evaluate_once():
        composition, coordinator = _coordinator(runtime)
        try:
            return coordinator.evaluate(_proposal())
        finally:
            coordinator.close()
            composition.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _value: evaluate_once(), (1, 2)))

    assert {result.disposition for result in results} == {
        "RECORDED_BLOCK", "ALREADY_RECORDED"
    }
    assert len({result.intent_id for result in results}) == 1
    assert _execute(runtime, "SELECT COUNT(*) FROM handa_live.order_intent") == [(1,)]
    assert _execute(runtime, "SELECT COUNT(*) FROM handa_live.submission_attempt") == [(1,)]
    assert _execute(runtime, "SELECT COUNT(*) FROM handa_live.pre_execution_decision") == [(1,)]

