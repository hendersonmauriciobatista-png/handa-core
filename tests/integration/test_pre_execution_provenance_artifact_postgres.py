"""Expected-RED PostgreSQL contract checks for slice 2B8B."""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from urllib.parse import urlparse

import psycopg2
import pytest

from core.execution.pre_execution_provenance_artifact import build_provenance_artifact
from core.persistence.persistence_coordinator import DatabaseIdentity, PersistenceCoordinator
from core.persistence.pre_execution_provenance_store import (
    PreExecutionProvenanceStore,
    pre_execution_provenance_resource_scope,
)


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
    if not IDENTITY.matches_url(value):
        pytest.fail("test database identity is outside the disposable database")
    return value


def _apply_migrations(url: str, names=MIGRATION_NAMES):
    connection = psycopg2.connect(url)
    try:
        with connection.cursor() as cursor:
            for name in names:
                cursor.execute(
                    (ROOT / "core" / "persistence" / "migrations" / name).read_text(
                        encoding="utf-8"
                    )
                )
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


def _reset(url: str):
    _execute(url, "DROP SCHEMA IF EXISTS handa_live CASCADE")


def _artifact():
    return build_provenance_artifact(
        symbol="HYPEUSDC",
        candidate_evidence_identity="candidate-test-1",
        source_group_timestamps={
            "PRICE_TECHNICAL": "2026-01-01T00:00:00Z",
            "SELECTION_RADAR": "2026-01-01T00:00:00Z",
            "MARKET_CONTEXT": "2026-01-01T00:00:00Z",
        },
        source_group_digests={
            "PRICE_TECHNICAL": "price-digest",
            "SELECTION_RADAR": "radar-digest",
            "MARKET_CONTEXT": "context-digest",
        },
        source_group_intervals={},
        ticker_value="100.25",
        requested_quote_amount="41.41",
    )


def test_migration_013_contract_exists_before_postgres_execution():
    migration = ROOT / "core" / "persistence" / "migrations" / "013_pre_execution_provenance_artifact.sql"
    assert migration.is_file(), (
        "EXPECTED_CONTRACT_RED::migration 013 is not implemented yet"
    )


def test_provenance_store_contract_module_exists_before_postgres_execution():
    store = ROOT / "core" / "persistence" / "pre_execution_provenance_store.py"
    assert store.is_file(), (
        "EXPECTED_CONTRACT_RED::pre-execution provenance store is not implemented yet"
    )


@pytest.fixture()
def runtime():
    url = _url()
    _reset(url)
    _apply_migrations(url)
    try:
        yield url
    finally:
        _reset(url)


def test_clean_001_to_013_installation_contains_immutable_tables(runtime):
    rows = _execute(
        runtime,
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='handa_live'
          AND table_name IN ('governance_artifact_manifest', 'pre_execution_provenance_artifact')
        ORDER BY table_name
        """,
    )
    assert rows == [
        ("governance_artifact_manifest",),
        ("pre_execution_provenance_artifact",),
    ]


def test_existing_001_to_012_upgrade_preserves_legacy_envelope(runtime):
    _reset(runtime)
    _apply_migrations(runtime, MIGRATION_NAMES[:-1])
    _execute(
        runtime,
        """
        INSERT INTO handa_live.authority_envelope (
            authority_envelope_id, runtime_mode, venue, account_scope, allowed_sides,
            strategy_version, decision_contract_version, policy_version, risk_policy_version,
            valid_from, valid_until, configuration_digest, authority_contract_version,
            approved_by, approval_reason
        ) VALUES (
            'legacy-envelope', 'OPERATIONAL_ENABLED', 'MOCK', 'TEST', ARRAY['BUY'],
            'strategy-v1', 'decision-v1', 'policy-v1', 'risk-v1',
            CURRENT_TIMESTAMP - INTERVAL '1 minute', CURRENT_TIMESTAMP + INTERVAL '1 minute',
            'config-v1', 'authority-v1', 'fixture', 'LEGACY_FIXTURE'
        )
        """,
    )
    before = _execute(
        runtime,
        "SELECT authority_envelope_id, approved_by, approval_reason FROM handa_live.authority_envelope",
    )
    _apply_migrations(runtime, (MIGRATION_NAMES[-1],))
    after = _execute(
        runtime,
        """
        SELECT authority_envelope_id, approved_by, approval_reason,
               strategy_manifest_id, policy_manifest_id, risk_manifest_id,
               configuration_manifest_id, freshness_manifest_id
        FROM handa_live.authority_envelope
        """,
    )
    assert before == [("legacy-envelope", "fixture", "LEGACY_FIXTURE")]
    assert after == [
        ("legacy-envelope", "fixture", "LEGACY_FIXTURE", None, None, None, None, None)
    ]


def test_manifest_and_provenance_rows_are_immutable(runtime):
    _execute(
        runtime,
        """
        INSERT INTO handa_live.governance_artifact_manifest (
            artifact_id, artifact_type, artifact_version, canonical_payload,
            canonical_payload_digest, valid_from, valid_until, producer_component,
            schema_version, contract_version, created_at, created_by, approved_at,
            approved_by, approval_reason
        ) VALUES (
            'manifest-1', 'STRATEGY', 'v1', '{}'::jsonb, 'digest-1',
            CURRENT_TIMESTAMP - INTERVAL '1 minute', CURRENT_TIMESTAMP + INTERVAL '1 minute',
            'fixture', 'schema-v1', 'contract-v1', CURRENT_TIMESTAMP, 'fixture',
            CURRENT_TIMESTAMP, 'fixture', 'TEST_FIXTURE'
        )
        """,
    )
    with pytest.raises(psycopg2.Error):
        _execute(runtime, "UPDATE handa_live.governance_artifact_manifest SET artifact_version='v2'")
    artifact = _artifact()
    store = PreExecutionProvenanceStore(
        PersistenceCoordinator(runtime, IDENTITY, resource_scope=pre_execution_provenance_resource_scope())
    )
    store.persist(artifact)
    store._coordinator.close()
    with pytest.raises(psycopg2.Error):
        _execute(
            runtime,
            "UPDATE handa_live.pre_execution_provenance_artifact SET symbol='OTHER'",
        )


def test_foreign_keys_and_replay_identity_fail_closed(runtime):
    with pytest.raises(psycopg2.Error):
        _execute(
            runtime,
            """
            INSERT INTO handa_live.pre_execution_provenance_artifact (
                provenance_artifact_id, candidate_evidence_identity, symbol, side,
                source_group_timestamps, source_group_digests, source_group_intervals,
                source_group_closure_statuses, source_group_server_times,
                source_group_constituent_digests,
                requested_quote_amount, dynamic_policy_evidence, dynamic_risk_evidence,
                strategy_manifest_id, binding_status, canonical_semantic_digest
            ) VALUES (
                'provenance-fk', 'candidate-fk', 'HYPEUSDC', 'BUY', '{}'::jsonb,
                '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb,
                1, '{}'::jsonb, '{}'::jsonb,
                'missing-manifest', 'BOUND', 'digest-fk'
            )
            """,
        )
    artifact = _artifact()
    coordinator = PersistenceCoordinator(
        runtime, IDENTITY, resource_scope=pre_execution_provenance_resource_scope()
    )
    store = PreExecutionProvenanceStore(coordinator)
    first = store.persist(artifact)
    second = store.persist(artifact)
    coordinator.close()
    assert first["provenance_artifact_id"] == second["provenance_artifact_id"]
    assert _execute(
        runtime,
        "SELECT COUNT(*) FROM handa_live.pre_execution_provenance_artifact",
    ) == [(1,)]


def test_concurrent_identical_provenance_insertion_has_one_canonical_row(runtime):
    artifact = _artifact()

    def persist_once(_):
        coordinator = PersistenceCoordinator(
            runtime, IDENTITY, resource_scope=pre_execution_provenance_resource_scope()
        )
        try:
            return PreExecutionProvenanceStore(coordinator).persist(artifact)[
                "provenance_artifact_id"
            ]
        finally:
            coordinator.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(persist_once, (1, 2)))
    assert ids == [artifact.candidate_id, artifact.candidate_id]
    assert _execute(
        runtime,
        "SELECT COUNT(*) FROM handa_live.pre_execution_provenance_artifact",
    ) == [(1,)]


def test_conflicting_transaction_rolls_back_without_partial_provenance(runtime):
    artifact = _artifact()
    coordinator = PersistenceCoordinator(
        runtime, IDENTITY, resource_scope=pre_execution_provenance_resource_scope()
    )
    store = PreExecutionProvenanceStore(coordinator)
    with pytest.raises(Exception):
        with coordinator.transaction() as context:
            context.insert("pre_execution_provenance_artifact", store._values(artifact))
            context.insert(
                "pre_execution_provenance_artifact",
                store._values(artifact),
            )
    coordinator.close()
    assert _execute(
        runtime,
        "SELECT COUNT(*) FROM handa_live.pre_execution_provenance_artifact",
    ) == [(0,)]


def test_real_runtime_datetime_shape_is_json_safe_without_losing_timestamp_semantics(runtime):
    artifact = build_provenance_artifact(
        symbol="HYPEUSDC",
        candidate_evidence_identity="candidate-real-datetime",
        source_group_timestamps={
            "PRICE_TECHNICAL": datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
            "SELECTION_RADAR": datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
            "MARKET_CONTEXT": datetime(2026, 1, 1, 0, 3, tzinfo=timezone.utc),
        },
        source_group_digests={
            "PRICE_TECHNICAL": "price-real-datetime",
            "SELECTION_RADAR": "radar-real-datetime",
            "MARKET_CONTEXT": "context-real-datetime",
        },
        source_group_intervals={
            "PRICE_TECHNICAL": {
                "oldest": datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
                "newest": datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
            },
            "SELECTION_RADAR": {
                "oldest": datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
                "newest": datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
            },
            "MARKET_CONTEXT": {
                "oldest": datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
                "newest": datetime(2026, 1, 1, 0, 3, tzinfo=timezone.utc),
            },
        },
        ticker_value="100.25",
        ticker_application_receipt_at=datetime(
            2026, 1, 1, 0, 4, tzinfo=timezone.utc
        ),
        decision_produced_at=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
        requested_quote_amount="41.41",
    )

    assert isinstance(
        artifact.source_group_timestamps["PRICE_TECHNICAL"], datetime
    )
    assert isinstance(
        artifact.source_group_intervals["PRICE_TECHNICAL"]["oldest"], datetime
    )

    coordinator = PersistenceCoordinator(
        runtime, IDENTITY, resource_scope=pre_execution_provenance_resource_scope()
    )
    try:
        try:
            row = PreExecutionProvenanceStore(coordinator).persist(artifact)
        except TypeError as exc:
            pytest.fail(
                "EXPECTED_CONTRACT_RED::real runtime datetime provenance is not JSON-safe: "
                f"{exc}",
                pytrace=False,
            )
    finally:
        coordinator.close()

    assert row["provenance_artifact_id"] == artifact.candidate_id


def test_get_artifact_reconstructs_temporal_semantics_and_closure_evidence(runtime):
    timestamps = {
        "PRICE_TECHNICAL": datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        "SELECTION_RADAR": datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
        "MARKET_CONTEXT": datetime(2026, 1, 1, 0, 3, tzinfo=timezone.utc),
    }
    intervals = {
        "PRICE_TECHNICAL": {
            "oldest": datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
            "newest": timestamps["PRICE_TECHNICAL"],
        },
        "SELECTION_RADAR": {
            "oldest": datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
            "newest": timestamps["SELECTION_RADAR"],
        },
        "MARKET_CONTEXT": {
            "oldest": datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
            "newest": timestamps["MARKET_CONTEXT"],
        },
    }
    artifact = build_provenance_artifact(
        symbol="HYPEUSDC",
        candidate_evidence_identity="candidate-temporal-reload",
        source_group_timestamps=timestamps,
        source_group_digests={
            "PRICE_TECHNICAL": "price-temporal",
            "SELECTION_RADAR": "radar-temporal",
            "MARKET_CONTEXT": "context-temporal",
        },
        source_group_intervals=intervals,
        source_group_closure_statuses={
            "PRICE_TECHNICAL": "CLOSED",
            "SELECTION_RADAR": "CLOSED_UNPROVEN",
            "MARKET_CONTEXT": "CLOSED",
        },
        source_group_server_times={
            "PRICE_TECHNICAL": datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
            "MARKET_CONTEXT": datetime(2026, 1, 1, 0, 4, tzinfo=timezone.utc),
        },
        ticker_value="100.25",
        ticker_application_receipt_at=datetime(
            2026, 1, 1, 0, 4, tzinfo=timezone.utc
        ),
        requested_quote_amount="41.41",
    )
    coordinator = PersistenceCoordinator(
        runtime, IDENTITY, resource_scope=pre_execution_provenance_resource_scope()
    )
    try:
        store = PreExecutionProvenanceStore(coordinator)
        store.persist(artifact)
        loaded = store.get_artifact(artifact.candidate_id)
    finally:
        coordinator.close()

    assert loaded.candidate_id == artifact.candidate_id
    assert loaded.canonical_semantic_digest == artifact.canonical_semantic_digest
    assert loaded.binding_status == artifact.binding_status
    assert isinstance(loaded.source_group_timestamps["PRICE_TECHNICAL"], datetime)
    assert isinstance(loaded.source_group_intervals["PRICE_TECHNICAL"]["oldest"], datetime)
    assert isinstance(loaded.source_group_intervals["PRICE_TECHNICAL"]["newest"], datetime)
    assert isinstance(loaded.source_group_server_times["PRICE_TECHNICAL"], datetime)
    assert loaded.source_group_closure_statuses["PRICE_TECHNICAL"] == "CLOSED"
    assert loaded.source_group_closure_statuses["SELECTION_RADAR"] == "CLOSED_UNPROVEN"
