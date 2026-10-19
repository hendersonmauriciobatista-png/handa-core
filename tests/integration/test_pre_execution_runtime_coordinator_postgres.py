"""Slice 2B7 runtime wiring against disposable PostgreSQL."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import json
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
from core.execution.pre_execution_provenance_artifact import build_provenance_artifact
from core.governed_runtime_composition import (
    GOVERNED_INFRASTRUCTURE_READY,
    GovernedRuntimeComposition,
    RuntimeCompositionConfig,
)
from core.market.governed_market_observation import canonical_group_digest
from core.persistence.governance_artifact_manifest_store import canonical_manifest_digest
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
        (13, "pre_execution_provenance_artifact.sql"),
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


def _activate(url: str, *, allowed_side: str, manifest_ids=None):
    manifest_columns = ""
    manifest_values = ""
    manifest_parameters = [allowed_side]
    if manifest_ids is not None:
        manifest_columns = ", strategy_manifest_id, policy_manifest_id, risk_manifest_id, configuration_manifest_id, freshness_manifest_id"
        manifest_values = ", %s, %s, %s, %s, %s"
        manifest_parameters.extend(
            manifest_ids[role]
            for role in ("STRATEGY", "POLICY", "RISK", "CONFIGURATION", "FRESHNESS")
        )
    _execute(
        url,
        f"""
        INSERT INTO handa_live.authority_envelope (
            authority_envelope_id, runtime_mode, venue, account_scope, allowed_sides,
            strategy_version, decision_contract_version, policy_version,
            risk_policy_version, valid_from, valid_until, configuration_digest,
            authority_contract_version, approved_by, approval_reason{manifest_columns}
        ) VALUES ('2b7-envelope', 'OPERATIONAL_ENABLED', 'MOCK', 'TEST', ARRAY[%s],
            'strategy-v1', 'decision-contract-v1', 'policy-v1', 'risk-v1',
            CURRENT_TIMESTAMP - INTERVAL '1 second',
            CURRENT_TIMESTAMP + INTERVAL '30 seconds', 'config-test', 'authority-v1',
            'fixture', 'TEST_FIXTURE_AUTHORITY_ONLY'{manifest_values})
        """,
        tuple(manifest_parameters),
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


def _seed_bound_manifests(url: str):
    manifest_ids = {}
    for role in ("STRATEGY", "POLICY", "RISK", "CONFIGURATION", "FRESHNESS"):
        artifact_id = f"post-audit-{role.lower()}"
        payload = {"role": role, "fixture": "post-final-audit"}
        _execute(
            url,
            """
            INSERT INTO handa_live.governance_artifact_manifest (
                artifact_id, artifact_type, artifact_version, canonical_payload,
                canonical_payload_digest, valid_from, valid_until, producer_component,
                schema_version, contract_version, created_at, created_by, approved_at,
                approved_by, approval_reason
            ) VALUES (
                %s, %s, 'v1', %s::jsonb, %s,
                CURRENT_TIMESTAMP - INTERVAL '1 minute',
                CURRENT_TIMESTAMP + INTERVAL '1 minute',
                'post-final-audit-test', 'schema-v1', 'contract-v1',
                CURRENT_TIMESTAMP, 'fixture', CURRENT_TIMESTAMP, 'fixture',
                'TEST_FIXTURE_MANIFEST'
            )
            """,
            (
                artifact_id,
                role,
                json.dumps(payload),
                canonical_manifest_digest(payload),
            ),
        )
        manifest_ids[role] = artifact_id

    return manifest_ids


def _complete_bound_artifact():
    times = {
        "PRICE_TECHNICAL": datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        "SELECTION_RADAR": datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
        "MARKET_CONTEXT": datetime(2026, 1, 1, 0, 3, tzinfo=timezone.utc),
    }
    identities = {
        group: f"{group}:HYPEUSDC:post-audit"
        for group in times
    }
    constituents = {
        group: [{
            "constituent_id": f"{group.lower()}:observation",
            "source": "post-final-audit-test",
            "semantic_digest": f"{group.lower()}-constituent",
            "trustworthy_market_time": True,
            "required_for_completeness": True,
        }]
        for group in times
    }
    intervals = {
        group: {"oldest": value, "newest": value}
        for group, value in times.items()
    }
    digests = {
        group: canonical_group_digest(
            group_type=group,
            group_identity=identities[group],
            constituents=constituents[group],
            market_oldest=intervals[group]["oldest"],
            market_newest=intervals[group]["newest"],
            trust_class="TRUSTED",
        )
        for group in times
    }
    return build_provenance_artifact(
        symbol="HYPEUSDC",
        candidate_evidence_identity="post-audit-bound-candidate",
        source_group_timestamps=times,
        source_group_digests=digests,
        source_group_intervals=intervals,
        source_group_closure_statuses={group: "CLOSED" for group in times},
        source_group_server_times={
            group: value.replace(second=value.second + 1)
            for group, value in times.items()
        },
        source_group_constituent_digests={
            group: (constituents[group][0]["semantic_digest"],)
            for group in times
        },
        source_group_identities=identities,
        source_group_constituents=constituents,
        source_group_missing_evidence={group: () for group in times},
        source_group_trust={group: "TRUSTED" for group in times},
        ticker_value="100.25",
        ticker_application_receipt_at=datetime(
            2026, 1, 1, 0, 4, tzinfo=timezone.utc
        ),
        requested_quote_amount="41.41",
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
    rows = _execute(
        runtime,
        "SELECT COUNT(*) FROM handa_live.pre_execution_provenance_artifact",
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
    assert result.submission_authority == "NONE"
    assert result.execution_authority == "NONE"
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


def test_governed_infrastructure_ready_has_pre_execution_provenance_contract(runtime):
    _activate(runtime, allowed_side="SELL")
    rows = _execute(
        runtime,
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='handa_live'
          AND table_name IN (
              'governance_artifact_manifest',
              'pre_execution_provenance_artifact'
          )
        ORDER BY table_name
        """,
    )
    assert rows == [
        ("governance_artifact_manifest",),
        ("pre_execution_provenance_artifact",),
    ], "EXPECTED_CONTRACT_RED::2B8B provenance tables are not present"


def test_real_bound_manifest_runtime_roundtrip_persists_text_ids_and_identity(runtime):
    manifest_ids = _seed_bound_manifests(runtime)
    _activate(runtime, allowed_side="BUY", manifest_ids=manifest_ids)
    proposal = replace(
        _proposal(),
        provenance_artifact=_complete_bound_artifact(),
    )
    composition, coordinator = _coordinator(runtime)
    try:
        persisted = coordinator.persist_provenance_artifact(
            proposal,
            require_complete=True,
        )
        reloaded = coordinator._provenance_store.get_artifact(
            persisted.candidate_id
        )
    finally:
        coordinator.close()
        composition.close()

    assert persisted.binding_status.value == "BOUND", (
        "EXPECTED_CONTRACT_RED::BOUND_MANIFEST_IDS_NOT_PERSISTABLE"
    )
    assert reloaded.binding_status.value == "BOUND"
    assert reloaded.static_manifest_identity == persisted.static_manifest_identity
    assert reloaded.canonical_semantic_digest == persisted.canonical_semantic_digest
    assert reloaded.candidate_id == persisted.candidate_id
    rows = _execute(
        runtime,
        """
        SELECT strategy_manifest_id, policy_manifest_id, risk_manifest_id,
               configuration_manifest_id, freshness_manifest_id
        FROM handa_live.pre_execution_provenance_artifact
        WHERE provenance_artifact_id=%s
        """,
        (persisted.candidate_id,),
    )
    assert rows == [(
        manifest_ids["STRATEGY"],
        manifest_ids["POLICY"],
        manifest_ids["RISK"],
        manifest_ids["CONFIGURATION"],
        manifest_ids["FRESHNESS"],
    )], "EXPECTED_CONTRACT_RED::BOUND_MANIFEST_IDS_NOT_PERSISTABLE"
    assert all(isinstance(value, str) for value in rows[0])

