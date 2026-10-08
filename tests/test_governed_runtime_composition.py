from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.governed_runtime_composition import (
    AUTHORITY_STATE_OBSERVE_ONLY,
    ACTIVE_ENVELOPE_INVALID,
    ACTIVE_ENVELOPE_MISSING,
    BootResult,
    FINAL_SCHEMA_SIGNATURE_VALID,
    GOVERNED_INFRASTRUCTURE_READY,
    OBSERVE_ONLY,
    GovernedRuntimeComposition,
    RuntimeCompositionConfig,
    verify_final_schema_signature,
)
from core.persistence.persistence_coordinator import DatabaseIdentity
from core.persistence.transaction_context import ImmutableRow


IDENTITY = DatabaseIdentity(frozenset({"127.0.0.1"}), 55432, "handa_test", "handa_test")
URL = "postgresql://handa_test@127.0.0.1:55432/handa_test"


class _Cursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def execute(self, statement, parameters=()):
        self.connection.statements.append(str(statement))

    def fetchone(self):
        return self.connection.identity

    def fetchall(self):
        return []


class _Connection:
    def __init__(self):
        self.identity = ("handa_test", "handa_test")
        self.statements = []
        self.autocommit = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        return None

    def commit(self):
        return None

    def close(self):
        self.closed = True


def _row(mode=OBSERVE_ONLY, active=None, *, version=0):
    return ImmutableRow(
        {
            "state_id": True,
            "operational_mode": mode,
            "active_authority_envelope_id": active,
            "global_safety_epoch": 0,
            "runtime_generation": 0,
            "current_version": version,
            "last_event_id": None,
            "changed_by": "migration-010",
            "change_reason": "fail-safe authority state initialization",
            "updated_at": datetime.now(timezone.utc),
        }
    )


def _envelope(
    envelope_id="env-1",
    *,
    valid_from=None,
    valid_until=None,
    runtime_mode="OPERATIONAL_ENABLED",
):
    now = datetime.now(timezone.utc)
    return ImmutableRow(
        {
            "authority_envelope_id": envelope_id,
            "envelope_version": 1,
            "runtime_mode": runtime_mode,
            "venue": "MOCK",
            "account_scope": "TEST",
            "allowed_sides": ("BUY",),
            "strategy_version": "strategy-v1",
            "decision_contract_version": "decision-v1",
            "policy_version": "policy-v1",
            "risk_policy_version": "risk-v1",
            "valid_from": valid_from or now - timedelta(seconds=1),
            "valid_until": valid_until or now + timedelta(minutes=1),
            "configuration_digest": "config-v1",
            "authority_contract_version": "authority-v1",
            "approved_by": "fixture",
            "approved_at": now,
            "approval_reason": "TEST_FIXTURE_AUTHORITY_ONLY",
            "created_at": now,
        }
    )


class _StateStore:
    def __init__(self, states):
        self.states = list(states)

    def get_current_state(self):
        return self.states.pop(0) if len(self.states) > 1 else self.states[0]


class _EnvelopeStore:
    def __init__(self, envelope):
        self.envelope = envelope

    def get_envelope(self, _envelope_id):
        return self.envelope


def _composition(states, envelope=None, *, schema_ok=True):
    state_store = _StateStore(states)
    config = RuntimeCompositionConfig(URL, IDENTITY, connect=lambda _url: _Connection())
    return GovernedRuntimeComposition(
        config,
        schema_verifier=lambda _connection: schema_ok,
        state_store_factory=lambda _coordinator: state_store,
        envelope_store_factory=lambda _coordinator: _EnvelopeStore(envelope),
    )


def test_missing_url_is_observe_only_and_fail_safe():
    result = GovernedRuntimeComposition(RuntimeCompositionConfig(None, IDENTITY)).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.operational_effects_blocked is True
    assert result.execution_authority == "NOT_GRANTED"


def test_connection_failure_is_observe_only():
    def fail(_url):
        raise OSError("connection refused")

    result = GovernedRuntimeComposition(
        RuntimeCompositionConfig(URL, IDENTITY, connect=fail),
        schema_verifier=lambda _: True,
    ).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == "POSTGRES_CONNECTION_FAILED"


def test_missing_identity_configuration_is_observe_only():
    result = GovernedRuntimeComposition(RuntimeCompositionConfig(URL, None)).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == "DATABASE_IDENTITY_CONFIG_MISSING"


def test_malformed_identity_configuration_is_observe_only():
    identity = DatabaseIdentity(frozenset({"127.0.0.1"}), 0, "handa_test", "handa_test")
    result = GovernedRuntimeComposition(RuntimeCompositionConfig(URL, identity)).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == "DATABASE_IDENTITY_CONFIG_INVALID"


def test_identity_mismatch_is_observe_only():
    def wrong_identity(_url):
        connection = _Connection()
        connection.identity = ("wrong_database", "wrong_user")
        return connection

    result = GovernedRuntimeComposition(
        RuntimeCompositionConfig(URL, IDENTITY, connect=wrong_identity),
        schema_verifier=lambda _: True,
    ).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == "DATABASE_IDENTITY_MISMATCH"


def test_server_identity_mismatch_is_observe_only():
    connections = [_Connection(), _Connection()]
    connections[1].identity = ("wrong_database", "wrong_user")

    def connect(_url):
        return connections.pop(0)

    result = GovernedRuntimeComposition(
        RuntimeCompositionConfig(URL, IDENTITY, connect=connect),
        schema_verifier=lambda _: True,
    ).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == "DATABASE_IDENTITY_MISMATCH"


def test_incomplete_schema_is_observe_only():
    result = _composition([_row(), _row()], schema_ok=False).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == "FINAL_SCHEMA_SIGNATURE_INVALID"


def test_schema_constraint_metadata_uses_postgres_array_binding():
    class MetadataCursor:
        def __init__(self):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def execute(self, statement, parameters=()):
            self.calls.append((str(statement), parameters))

        def fetchall(self):
            return []

    class MetadataConnection:
        def __init__(self):
            self.cursor_instance = MetadataCursor()

        def cursor(self):
            return self.cursor_instance

    connection = MetadataConnection()
    signature = verify_final_schema_signature(connection)

    assert signature.valid is False
    constraint_call = next(
        call for call in connection.cursor_instance.calls if "constraint_name" in call[0]
    )
    assert "ANY(%s::text[])" in constraint_call[0]
    assert isinstance(constraint_call[1][0], list)


def test_expected_schema_catalog_parses_all_add_columns(monkeypatch, tmp_path):
    import core.governed_runtime_composition as composition_module

    migration = tmp_path / "001_multiple_add_columns.sql"
    migration.write_text(
        """
        ALTER TABLE handa_live.fixture_table
            ADD COLUMN first_column TEXT,
            ADD COLUMN second_column TEXT,
            ADD COLUMN third_column TEXT;
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(composition_module, "_migration_sources", lambda: (migration,))

    tables, columns = composition_module._expected_schema_catalog()

    assert tables == frozenset()
    assert columns == frozenset(
        {
            ("fixture_table", "first_column"),
            ("fixture_table", "second_column"),
            ("fixture_table", "third_column"),
        }
    )


def test_expected_schema_catalog_contains_disputed_final_columns():
    import core.governed_runtime_composition as composition_module

    required = {
        ("exchange_evidence", "order_type"),
        ("exchange_evidence", "time_in_force"),
        ("exchange_evidence", "orig_qty"),
        ("exchange_evidence", "orig_quote_order_qty"),
        ("exchange_evidence", "executed_qty"),
        ("exchange_evidence", "cumulative_quote_qty"),
        ("exchange_evidence", "observation_class"),
        ("exchange_evidence", "observation_source"),
        ("order_intent", "current_decision_id"),
        ("pre_execution_decision", "evaluation_request_digest"),
    }

    assert required <= composition_module.EXPECTED_SCHEMA_COLUMNS


def test_schema_signature_ignores_sequences_and_requires_frozen_markers():
    import core.governed_runtime_composition as composition_module

    class CatalogCursor:
        def __init__(self):
            self.statements = []
            self.rows = []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def execute(self, statement, _parameters=()):
            self.statements.append(str(statement))
            if "information_schema.tables" in statement:
                self.rows = [(table,) for table in composition_module.EXPECTED_SCHEMA_TABLES]
            elif "information_schema.columns" in statement:
                self.rows = list(composition_module.EXPECTED_SCHEMA_COLUMNS)
            elif "table_constraints" in statement:
                self.rows = [(constraint,) for constraint in composition_module.EXPECTED_SCHEMA_CONSTRAINTS]
            else:
                raise AssertionError(f"unexpected metadata query: {statement}")

        def fetchall(self):
            return self.rows

    class CatalogConnection:
        def __init__(self):
            self.cursor_instance = CatalogCursor()

        def cursor(self):
            return self.cursor_instance

    connection = CatalogConnection()
    signature = verify_final_schema_signature(connection)

    assert signature.valid is True
    assert not any("information_schema.sequences" in statement for statement in connection.cursor_instance.statements)


def test_schema_signature_fails_closed_on_required_marker_absence():
    import core.governed_runtime_composition as composition_module

    class CatalogCursor:
        def __init__(self):
            self.rows = []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def execute(self, statement, _parameters=()):
            if "information_schema.tables" in statement:
                self.rows = [(table,) for table in composition_module.EXPECTED_SCHEMA_TABLES]
            elif "information_schema.columns" in statement:
                missing = ("order_intent", "current_decision_id")
                self.rows = [row for row in composition_module.EXPECTED_SCHEMA_COLUMNS if row != missing]
            elif "table_constraints" in statement:
                self.rows = []

        def fetchall(self):
            return self.rows

    class CatalogConnection:
        def cursor(self):
            return CatalogCursor()

    signature = verify_final_schema_signature(CatalogConnection())

    assert signature.valid is False
    assert ("order_intent", "current_decision_id") in signature.missing_columns
    assert set(signature.missing_constraints) == composition_module.EXPECTED_SCHEMA_CONSTRAINTS


def test_migration_010_default_is_valid_fail_safe_observe_only():
    result = _composition([_row(), _row()]).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == AUTHORITY_STATE_OBSERVE_ONLY
    assert result.schema_signature_status == FINAL_SCHEMA_SIGNATURE_VALID
    assert result.authority_snapshot is not None
    assert result.authority_snapshot.active_envelope is None
    assert result.operational_effects_blocked is True


def test_valid_enabled_envelope_is_ready_but_not_execution_authorized():
    state = _row("OPERATIONAL_ENABLED", "env-1")
    result = _composition([state, state], _envelope()).boot()
    assert result.posture == GOVERNED_INFRASTRUCTURE_READY
    assert result.operational_effects_blocked is True
    assert result.execution_authority == "NOT_GRANTED"


@pytest.mark.parametrize(
    "field_name",
    ("strategy_version", "decision_contract_version", "policy_version", "risk_policy_version"),
)
@pytest.mark.parametrize("invalid_value", (None, "", "   "))
def test_empty_active_envelope_version_fields_are_invalid(field_name, invalid_value):
    state = _row("OPERATIONAL_ENABLED", "env-1")
    envelope_values = dict(_envelope())
    envelope_values[field_name] = invalid_value

    result = _composition(
        [state, state],
        ImmutableRow(envelope_values),
    ).boot()

    assert result.posture == OBSERVE_ONLY
    assert result.reason == ACTIVE_ENVELOPE_INVALID
    assert result.operational_effects_blocked is True
    assert result.execution_authority == "NOT_GRANTED"


def test_enabled_mode_without_active_envelope_is_missing():
    state = _row("OPERATIONAL_ENABLED", None)
    result = _composition([state, state]).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == ACTIVE_ENVELOPE_MISSING
    assert result.operational_effects_blocked is True
    assert result.execution_authority == "NOT_GRANTED"


def test_expired_future_and_mismatched_envelopes_are_observe_only():
    now = datetime.now(timezone.utc)
    cases = (
        (_envelope(valid_until=now - timedelta(seconds=1)), ACTIVE_ENVELOPE_INVALID),
        (_envelope(valid_from=now + timedelta(seconds=1)), ACTIVE_ENVELOPE_INVALID),
        (_envelope(runtime_mode=OBSERVE_ONLY), ACTIVE_ENVELOPE_INVALID),
    )
    for envelope, reason in cases:
        result = _composition(
            [_row("OPERATIONAL_ENABLED", "env-1"), _row("OPERATIONAL_ENABLED", "env-1")],
            envelope,
        ).boot()
        assert result.posture == OBSERVE_ONLY
        assert result.reason == reason


def test_authority_state_change_between_s1_and_s2_is_observe_only():
    result = _composition([_row(version=0), _row(version=1)]).boot()
    assert result.posture == OBSERVE_ONLY
    assert result.reason == "AUTHORITY_STATE_INCONSISTENT"


def test_close_is_idempotent_and_safe_before_boot():
    composition = GovernedRuntimeComposition(RuntimeCompositionConfig(None, None))
    composition.close()
    composition.close()
    assert composition.boot().posture == OBSERVE_ONLY


def test_composition_does_not_expose_coordinator_or_stores():
    composition = _composition([_row(), _row()])
    assert not hasattr(composition, "coordinator")
    assert "state_store" not in dir(composition)
    assert "envelope_store" not in dir(composition)


def test_boot_result_is_immutable_and_always_blocked():
    result = _composition([_row(), _row()]).boot()
    assert result.operational_effects_blocked is True
    try:
        result.reason = "changed"
    except Exception:
        pass
    else:
        raise AssertionError("BootResult must be immutable")


def test_headless_boot_precedes_radar_and_keeps_execution_contained():
    root = Path(__file__).parents[1]
    headless = (root / "run_headless.py").read_text(encoding="utf-8")
    composition = (root / "core" / "governed_runtime_composition.py").read_text(encoding="utf-8")
    assert headless.index("boot_result = composition.boot()") < headless.index("radar.start()")
    assert "operational_effects_blocked=True" in headless
    assert 'notifier.send("🚀 H&A HEADLESS iniciado com sucesso")' in headless
    for forbidden in ("submission_authorization_issuer", "submission_authorization_claimer", "governed_transport"):
        assert forbidden not in composition


def test_headless_passes_containment_for_both_boot_postures(monkeypatch):
    import run_headless

    for posture in (OBSERVE_ONLY, GOVERNED_INFRASTRUCTURE_READY):
        events = []
        slot_arguments = []

        class FakeComposition:
            def __init__(self, _config):
                pass

            def boot(self):
                events.append("boot")
                return BootResult(posture, "TEST_ONLY")

            def close(self):
                events.append("close")

        class FakeClient:
            def __init__(self, *_args):
                pass

        class FakeExecutor:
            def __init__(self, **_kwargs):
                pass

        class FakeRisk:
            def __init__(self, *_args):
                pass

        class FakeCapital:
            def __init__(self, *_args):
                pass

        class FakeDecision:
            def __init__(self, **_kwargs):
                pass

            def set_alo(self, *_args):
                pass

            def set_system_context_provider(self, *_args):
                pass

            def set_position_manager(self, *_args):
                pass

        class FakeRadar:
            def __init__(self, *_args):
                pass

            def start(self):
                events.append("radar.start")

        class FakeSlot:
            def __init__(self, **kwargs):
                slot_arguments.append(kwargs)

            def reconcile_persisted_mock_state(self):
                return "TEST_ONLY"

        class FakeAutoLoop:
            def __init__(self, **_kwargs):
                pass

            def start(self):
                events.append("autoloop.start")

        class FakePositionManager:
            pass

        class FakeTracker:
            pass

        class FakePassive:
            def __init__(self, **_kwargs):
                pass

        class FakeNotifier:
            def __init__(self, **_kwargs):
                pass

            def send(self, _message):
                events.append("notifier.send")

        monkeypatch.setattr(run_headless, "load_dotenv", lambda: None)
        monkeypatch.setattr(run_headless, "GovernedRuntimeComposition", FakeComposition)
        monkeypatch.setattr(run_headless, "load_runtime_composition_config", lambda: object())
        monkeypatch.setattr(run_headless, "set_execution_mode", lambda *_args: None)
        monkeypatch.setattr(run_headless, "Client", FakeClient)
        monkeypatch.setattr(run_headless, "PositionManager", FakePositionManager)
        monkeypatch.setattr(run_headless, "PositionTracker", FakeTracker)
        monkeypatch.setattr(run_headless, "MockExecutor", FakeExecutor)
        monkeypatch.setattr(run_headless, "RiskManager", FakeRisk)
        monkeypatch.setattr(run_headless, "CapitalAllocator", FakeCapital)
        monkeypatch.setattr(run_headless, "LC1FeedbackAdapter", FakePassive)
        monkeypatch.setattr(run_headless, "AdaptiveLearningObserver", FakePassive)
        monkeypatch.setattr(run_headless, "TelegramNotifier", FakeNotifier)
        monkeypatch.setattr(run_headless, "DecisionEngine", FakeDecision)
        monkeypatch.setattr(run_headless, "MarketRadarEngine", FakeRadar)
        monkeypatch.setattr(run_headless, "SlotController", FakeSlot)
        monkeypatch.setattr(run_headless, "AutoLoop", FakeAutoLoop)

        run_headless.run()

        assert events.index("boot") < events.index("radar.start")
        assert slot_arguments[-1]["operational_effects_blocked"] is True
