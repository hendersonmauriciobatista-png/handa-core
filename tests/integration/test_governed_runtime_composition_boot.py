from __future__ import annotations

import os
from pathlib import Path

import psycopg2
import pytest

from core.governed_runtime_composition import (
    AUTHORITY_STATE_OBSERVE_ONLY,
    FINAL_SCHEMA_SIGNATURE_VALID,
    GOVERNED_INFRASTRUCTURE_READY,
    OBSERVE_ONLY,
    GovernedRuntimeComposition,
    RuntimeCompositionConfig,
)
from core.persistence.persistence_coordinator import DatabaseIdentity
from tests.integration.test_submission_authorization_postgres import (
    EXPECTED_DATABASE,
    EXPECTED_HOSTS,
    EXPECTED_PORT,
    EXPECTED_URL,
    EXPECTED_USER,
    _bootstrap,
)


ROOT = Path(__file__).parents[2]
MIGRATION_012 = ROOT / "core" / "persistence" / "migrations" / "012_governed_transport_submission.sql"


def _database_url():
    value = os.getenv("TEST_DATABASE_URL")
    if value != EXPECTED_URL:
        pytest.skip("ENVIRONMENT_BLOCKED: disposable local PostgreSQL is required")
    return value


def _identity():
    return DatabaseIdentity(EXPECTED_HOSTS, EXPECTED_PORT, EXPECTED_DATABASE, EXPECTED_USER)


@pytest.fixture()
def prepared():
    url = _database_url()
    _bootstrap(url)
    with psycopg2.connect(url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(MIGRATION_012.read_text(encoding="utf-8"))
        connection.commit()
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


def _config(url):
    return RuntimeCompositionConfig(url, _identity())


def _execute(url, statement, parameters=()):
    connection = psycopg2.connect(url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
        connection.commit()
    finally:
        connection.close()


def _seed_envelope(url, *, envelope_id, runtime_mode, valid_from, valid_until):
    _execute(
        url,
        f"""
        INSERT INTO handa_live.authority_envelope (
            authority_envelope_id, runtime_mode, venue, account_scope,
            allowed_sides, strategy_version, decision_contract_version,
            policy_version, risk_policy_version, valid_from, valid_until,
            configuration_digest, authority_contract_version, approved_by,
            approval_reason
        ) VALUES (
            %s, %s, 'MOCK', 'TEST', ARRAY['BUY'],
            'strategy-v1', 'decision-v1', 'policy-v1', 'risk-v1',
            CURRENT_TIMESTAMP {valid_from},
            CURRENT_TIMESTAMP {valid_until},
            'config-v1', 'authority-v1', 'fixture',
            'TEST_FIXTURE_AUTHORITY_ONLY'
        )
        """,
        (envelope_id, runtime_mode),
    )
    _execute(
        url,
        """
        UPDATE handa_live.operational_authority_state
        SET operational_mode='OPERATIONAL_ENABLED',
            active_authority_envelope_id=%s,
            changed_by='fixture',
            change_reason='TEST_FIXTURE_AUTHORITY_ONLY'
        WHERE state_id=TRUE
        """,
        (envelope_id,),
    )


def test_migration_010_default_boot_is_valid_observe_only(prepared):
    composition = GovernedRuntimeComposition(_config(prepared))
    try:
        result = composition.boot()
        assert result.posture == OBSERVE_ONLY
        assert result.reason == AUTHORITY_STATE_OBSERVE_ONLY
        assert result.schema_signature_status == FINAL_SCHEMA_SIGNATURE_VALID
        assert result.authority_snapshot.active_envelope is None
        assert result.operational_effects_blocked is True
        assert result.execution_authority == "NOT_GRANTED"
    finally:
        composition.close()


def test_valid_operational_envelope_boot_is_still_effect_blocked(prepared):
    _execute(
        prepared,
        """
        INSERT INTO handa_live.authority_envelope (
            authority_envelope_id, runtime_mode, venue, account_scope,
            allowed_sides, strategy_version, decision_contract_version,
            policy_version, risk_policy_version, valid_from, valid_until,
            configuration_digest, authority_contract_version, approved_by,
            approval_reason
        ) VALUES (
            'boot-envelope', 'OPERATIONAL_ENABLED', 'MOCK', 'TEST', ARRAY['BUY'],
            'strategy-v1', 'decision-v1', 'policy-v1', 'risk-v1',
            CURRENT_TIMESTAMP - INTERVAL '1 minute',
            CURRENT_TIMESTAMP + INTERVAL '1 minute',
            'config-v1', 'authority-v1', 'fixture',
            'TEST_FIXTURE_AUTHORITY_ONLY'
        )
        """,
    )
    _execute(
        prepared,
        """
        UPDATE handa_live.operational_authority_state
        SET operational_mode='OPERATIONAL_ENABLED',
            active_authority_envelope_id='boot-envelope',
            changed_by='fixture',
            change_reason='TEST_FIXTURE_AUTHORITY_ONLY'
        WHERE state_id=TRUE
        """,
    )

    composition = GovernedRuntimeComposition(_config(prepared))
    try:
        result = composition.boot()
        assert result.posture == GOVERNED_INFRASTRUCTURE_READY
        assert result.operational_effects_blocked is True
        assert result.execution_authority == "NOT_GRANTED"
    finally:
        composition.close()


def test_matrix_a_missing_migration_010_schema_is_observe_only(prepared):
    _execute(prepared, "DROP TABLE handa_live.operational_authority_state CASCADE")
    result = GovernedRuntimeComposition(_config(prepared)).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == "FINAL_SCHEMA_SIGNATURE_INVALID"


def test_matrix_d_missing_authority_state_is_observe_only(prepared):
    _execute(prepared, "DELETE FROM handa_live.operational_authority_state")
    result = GovernedRuntimeComposition(_config(prepared)).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == "AUTHORITY_STATE_MISSING"


def test_matrix_e_missing_active_envelope_is_observe_only(prepared):
    _execute(
        prepared,
        """
        UPDATE handa_live.operational_authority_state
        SET operational_mode='OPERATIONAL_ENABLED',
            active_authority_envelope_id=NULL,
            changed_by='fixture',
            change_reason='TEST_FIXTURE_AUTHORITY_ONLY'
        WHERE state_id=TRUE
        """,
    )
    result = GovernedRuntimeComposition(_config(prepared)).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == "ACTIVE_ENVELOPE_MISSING"


def test_matrix_f_expired_envelope_is_observe_only(prepared):
    _seed_envelope(
        prepared,
        envelope_id="expired-envelope",
        runtime_mode="OPERATIONAL_ENABLED",
        valid_from="- INTERVAL '2 minutes'",
        valid_until="- INTERVAL '1 minute'",
    )
    result = GovernedRuntimeComposition(_config(prepared)).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == "ACTIVE_ENVELOPE_INVALID"


def test_matrix_g_future_envelope_is_observe_only(prepared):
    _seed_envelope(
        prepared,
        envelope_id="future-envelope",
        runtime_mode="OPERATIONAL_ENABLED",
        valid_from="+ INTERVAL '1 minute'",
        valid_until="+ INTERVAL '2 minutes'",
    )
    result = GovernedRuntimeComposition(_config(prepared)).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == "ACTIVE_ENVELOPE_INVALID"


def test_matrix_h_runtime_mode_mismatch_is_observe_only(prepared):
    _seed_envelope(
        prepared,
        envelope_id="mismatched-envelope",
        runtime_mode=OBSERVE_ONLY,
        valid_from="- INTERVAL '1 minute'",
        valid_until="+ INTERVAL '1 minute'",
    )
    result = GovernedRuntimeComposition(_config(prepared)).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == "ACTIVE_ENVELOPE_INVALID"


def test_matrix_i_missing_migration_012_marker_is_observe_only(prepared):
    _execute(prepared, "DROP TABLE handa_live.transport_event CASCADE")
    result = GovernedRuntimeComposition(_config(prepared)).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == "FINAL_SCHEMA_SIGNATURE_INVALID"


def test_matrix_j_missing_migration_011_column_is_observe_only(prepared):
    _execute(
        prepared,
        "ALTER TABLE handa_live.pre_execution_decision DROP COLUMN evaluation_request_id CASCADE",
    )
    result = GovernedRuntimeComposition(_config(prepared)).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == "FINAL_SCHEMA_SIGNATURE_INVALID"


def test_s1_s2_authority_state_change_is_observe_only(prepared):
    from core.persistence.operational_authority_state_store import OperationalAuthorityStateStore

    class ChangingStateStore:
        def __init__(self, coordinator):
            self._delegate = OperationalAuthorityStateStore(coordinator)
            self._reads = 0

        def get_current_state(self):
            state = self._delegate.get_current_state()
            self._reads += 1
            if self._reads == 1:
                _execute(
                    prepared,
                    """
                    UPDATE handa_live.operational_authority_state
                    SET current_version=current_version + 1,
                        changed_by='fixture',
                        change_reason='TEST_FIXTURE_S1_S2_CHANGE'
                    WHERE state_id=TRUE
                    """,
                )
            return state

    composition = GovernedRuntimeComposition(
        _config(prepared),
        state_store_factory=ChangingStateStore,
    )
    try:
        result = composition.boot()
        assert result.posture == OBSERVE_ONLY
        assert result.reason == "AUTHORITY_STATE_INCONSISTENT"
    finally:
        composition.close()
