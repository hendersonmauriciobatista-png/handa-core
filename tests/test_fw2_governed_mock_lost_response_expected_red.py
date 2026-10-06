"""FW2 GREEN regression tests for governed MOCK venue recovery."""

import copy
import gc
import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import psycopg2
import pytest

import executor.mock_executor as mock_executor_module
from core.execution.execution_fact import (
    ExtentCertainty,
    ExternalOrderStatus,
    QuantitySemantics,
)
from core.execution.governed_mock_submission_gateway import (
    GovernedMockSubmissionGateway,
)
from core.execution.live_order_models import LiveOrderIntent, OrderSide
from core.persistence.live_order_store import LiveOrderStore, live_order_resource_scope
from core.persistence.persistence_coordinator import (
    DatabaseIdentity,
    PersistenceCoordinator,
)


EXPECTED_DATABASE_URL = (
    "postgresql://handa_test:handa_test_only@127.0.0.1:55432/handa_test"
)
MIGRATIONS = tuple(
    Path(__file__).parents[1]
    / "core"
    / "persistence"
    / "migrations"
    / name
    for name in (
        "001_create_handa_live.sql",
        "002_relax_may_have_been_submitted_certainty.sql",
        "003_reconciliation_evidence.sql",
        "004_external_order_observation_contract.sql",
        "005_decision_ledger.sql",
        "006_effect_application_ledger.sql",
        "007_position_effect_authority.sql",
        "008_effect_request_logical_binding.sql",
    )
)


class LostResponse(RuntimeError):
    pass


class FakeClient:
    def get_symbol_ticker(self, symbol):
        return {"price": "110"}


def _signal(**overrides):
    values = {
        "pair": "HYPEUSDC",
        "entry_price": 94.87,
        "allocated_usdc": 41.4117522032984,
        "stop_loss": 90.0,
        "take_profit": 100.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _mock_state_redirect(monkeypatch, state_path):
    temp_state_path = Path(f"{state_path}.tmp")
    original_exists = mock_executor_module.os.path.exists
    original_open = open
    original_replace = os.replace

    def exists(path):
        if path in {"/data/mock_state.json", "/data/mock_state.json.tmp"}:
            return True
        return original_exists(path)

    def open_redirect(path, *args, **kwargs):
        if path == "/data/mock_state.json":
            path = state_path
        elif path == "/data/mock_state.json.tmp":
            path = temp_state_path
        return original_open(path, *args, **kwargs)

    def replace_redirect(source, destination):
        if destination == "/data/mock_state.json":
            return original_replace(temp_state_path, state_path)
        return original_replace(source, destination)

    monkeypatch.setattr(mock_executor_module, "PostgresStateRepository", None)
    monkeypatch.setattr(mock_executor_module.os.path, "exists", exists)
    monkeypatch.setattr("builtins.open", open_redirect)
    monkeypatch.setattr(mock_executor_module.os, "makedirs", Mock())
    monkeypatch.setattr(mock_executor_module.os, "replace", replace_redirect)


def _fresh_executor(monkeypatch, tmp_path, state=None):
    state_path = tmp_path / "mock_state.json"
    if state is None:
        state = {
            "state_format_version": 1,
            "initial_balance": 1000.0,
            "current_balance": 1000.0,
            "positions": {},
        }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    _mock_state_redirect(monkeypatch, state_path)
    executor = mock_executor_module.MockExecutor(
        client=FakeClient(),
        initial_balance=1000.0,
    )
    return executor, state_path


def _submit(executor, client_order_id="client-fw2-hype-001", **signal_overrides):
    gateway = GovernedMockSubmissionGateway(executor)
    return gateway.submit_buy(
        _signal(**signal_overrides),
        client_order_id=client_order_id,
    )


def _state_hash(state_path):
    return hashlib.sha256(state_path.read_bytes()).hexdigest()


def _bootstrap_migrations(database_url):
    connection = psycopg2.connect(database_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            for migration in MIGRATIONS:
                cursor.execute(migration.read_text(encoding="utf-8"))
        connection.commit()
    finally:
        connection.close()


def _new_store(database_url):
    coordinator = PersistenceCoordinator(
        database_url,
        DatabaseIdentity(
            allowed_hosts=frozenset({"127.0.0.1", "localhost"}),
            port=55432,
            database="handa_test",
            user="handa_test",
        ),
        resource_scope=live_order_resource_scope(),
    )
    return coordinator, LiveOrderStore(coordinator)


def test_fw2_lost_response_recovers_exact_effect_without_second_buy(
    monkeypatch, tmp_path
):
    executor, state_path = _fresh_executor(monkeypatch, tmp_path)
    executor.execute_buy = Mock(wraps=executor.execute_buy)
    gateway = GovernedMockSubmissionGateway(executor)
    client_order_id = "client-fw2-hype-001"

    try:
        gateway.submit_buy(_signal(), client_order_id=client_order_id)
        raise LostResponse("caller lost response after durable venue mutation")
    except LostResponse:
        pass

    assert executor.execute_buy.call_count == 1
    durable_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert durable_state["state_format_version"] == 2
    assert len(durable_state["orders"]) == 1
    assert len(durable_state["positions"]) == 1

    external_order_id = durable_state["orders"][client_order_id]["external_order_id"]
    trade_id = durable_state["orders"][client_order_id]["fills"][0]["tradeId"]
    del gateway
    del executor
    gc.collect()

    restarted, _ = _fresh_executor(monkeypatch, tmp_path, durable_state)
    restarted.execute_buy = Mock(
        side_effect=AssertionError("FALSIFIER::EXTERNAL_REEXECUTION_AFTER_LOST_RESPONSE")
    )
    recovered = GovernedMockSubmissionGateway(restarted).recover_by_client_order_id(
        client_order_id
    )

    assert restarted.execute_buy.call_count == 0
    assert recovered.client_order_id == client_order_id
    assert recovered.external_order_id == external_order_id
    assert recovered.external_status is ExternalOrderStatus.FILLED
    assert recovered.executed_base_qty > 0
    assert recovered.executed_quote_qty > 0
    assert recovered.quantity_semantics is QuantitySemantics.NON_OVERLAPPING_EXTENT
    assert recovered.execution_extent_identity is not None
    assert recovered.extent_certainty is ExtentCertainty.KNOWN_FULL
    assert restarted.orders[client_order_id]["fills"][0]["tradeId"] == trade_id


def test_duplicate_same_client_id_is_idempotent(monkeypatch, tmp_path):
    executor, state_path = _fresh_executor(monkeypatch, tmp_path)
    first = _submit(executor)
    before_hash = _state_hash(state_path)
    before_balance = executor.balance_usdc
    second = _submit(executor)

    assert second.external_order_id == first.external_order_id
    assert second.fill_digest == first.fill_digest
    assert len(executor.orders) == 1
    assert len(executor.positions) == 1
    assert executor.balance_usdc == before_balance
    assert _state_hash(state_path) == before_hash


def test_conflicting_client_id_reuse_fails_closed_without_mutation(
    monkeypatch, tmp_path
):
    executor, state_path = _fresh_executor(monkeypatch, tmp_path)
    _submit(executor)
    before_hash = _state_hash(state_path)
    before_balance = executor.balance_usdc
    before_positions = copy.deepcopy(executor.positions)

    with pytest.raises(RuntimeError, match="conflicting client_order_id"):
        _submit(executor, allocated_usdc=42.0)

    assert _state_hash(state_path) == before_hash
    assert executor.balance_usdc == before_balance
    assert executor.positions == before_positions
    assert len(executor.orders) == 1


def test_read_only_recovery_does_not_write_or_mutate(monkeypatch, tmp_path):
    executor, state_path = _fresh_executor(monkeypatch, tmp_path)
    fact = _submit(executor)
    before_hash = _state_hash(state_path)
    before_balance = executor.balance_usdc
    before_positions = copy.deepcopy(executor.positions)
    before_orders = copy.deepcopy(executor.orders)

    by_client = executor.get_order_by_client_order_id(fact.client_order_id)
    by_external = executor.get_order_by_external_order_id(fact.external_order_id)
    by_client["fills"][0]["tradeId"] = "tampered-copy"

    assert by_external["external_order_id"] == fact.external_order_id
    assert _state_hash(state_path) == before_hash
    assert executor.balance_usdc == before_balance
    assert executor.positions == before_positions
    assert executor.orders == before_orders


def test_external_and_fill_identity_are_stable_across_restart(monkeypatch, tmp_path):
    executor, state_path = _fresh_executor(monkeypatch, tmp_path)
    first = _submit(executor)
    first_order = executor.get_order_by_client_order_id(first.client_order_id)
    first_trade_id = first_order["fills"][0]["tradeId"]
    first_extent = first.execution_extent_identity

    restarted, _ = _fresh_executor(
        monkeypatch, tmp_path, json.loads(state_path.read_text(encoding="utf-8"))
    )
    by_client = GovernedMockSubmissionGateway(restarted).recover_by_client_order_id(
        first.client_order_id
    )
    by_external = GovernedMockSubmissionGateway(
        restarted
    ).recover_by_external_order_id(first.external_order_id)

    assert by_client.external_order_id == first.external_order_id
    assert by_external.external_order_id == first.external_order_id
    assert restarted.get_order_by_client_order_id(first.client_order_id)["fills"][0][
        "tradeId"
    ] == first_trade_id
    assert by_client.execution_extent_identity == first_extent
    assert by_external.execution_extent_identity == first_extent


def test_legacy_unversioned_state_loads_without_recovery_history(monkeypatch, tmp_path):
    state = {
        "initial_balance": 1000.0,
        "current_balance": 800.0,
        "positions": {
            "BTCUSDC": {
                "pair": "BTCUSDC",
                "entry_price": 100.0,
                "quantity": 2.0,
                "allocated_usdc": 200.0,
                "stop_loss": 90.0,
                "take_profit": 110.0,
            }
        },
    }
    executor, _ = _fresh_executor(monkeypatch, tmp_path, state)

    assert executor.state_classification == "LEGACY_UNVERSIONED_RECORD"
    assert executor.orders == {}
    assert executor.get_order_by_client_order_id("unknown-client") is None


def test_v1_state_loads_without_invented_order_history(monkeypatch, tmp_path):
    state = {
        "state_format_version": 1,
        "initial_balance": 1000.0,
        "current_balance": 800.0,
        "positions": {
            "BTCUSDC": {
                "pair": "BTCUSDC",
                "entry_price": 100.0,
                "quantity": 2.0,
                "allocated_usdc": 200.0,
                "stop_loss": 90.0,
                "take_profit": 110.0,
                "position_id": "venue-position-only",
                "opened_at": "2026-10-04T12:00:00",
            }
        },
    }
    executor, _ = _fresh_executor(monkeypatch, tmp_path, state)

    assert executor.state_format_version == 1
    assert executor.orders == {}
    assert executor.get_order_by_client_order_id("historical-client") is None


def test_v2_state_loads_and_recovers_order_evidence(monkeypatch, tmp_path):
    executor, state_path = _fresh_executor(monkeypatch, tmp_path)
    first = _submit(executor)
    v2 = json.loads(state_path.read_text(encoding="utf-8"))

    restarted, _ = _fresh_executor(monkeypatch, tmp_path, v2)
    recovered = GovernedMockSubmissionGateway(restarted).recover_by_client_order_id(
        first.client_order_id
    )

    assert restarted.state_format_version == 2
    assert recovered.external_order_id == first.external_order_id
    assert recovered.execution_extent_identity == first.execution_extent_identity


def test_failed_persistence_rolls_back_all_external_mutation(monkeypatch, tmp_path):
    executor, state_path = _fresh_executor(monkeypatch, tmp_path)
    before_hash = _state_hash(state_path)
    executor._save_state = Mock(return_value=False)

    with pytest.raises(RuntimeError, match="falha ao persistir BUY"):
        _submit(executor)

    assert executor.balance_usdc == 1000.0
    assert executor.positions == {}
    assert executor.orders == {}
    assert _state_hash(state_path) == before_hash


def test_governed_gateway_has_no_application_authority_leak():
    source = Path(
        "core/execution/governed_mock_submission_gateway.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "EffectEligibility",
        "OperationalApplicationBinding",
        "effect_request_id",
        "application_attempt_id",
        "PositionBinding",
        "PositionEffectAuthority",
        "PositionManager",
        "SlotController",
        "C4D",
    )
    assert not any(token in source for token in forbidden)


def test_fw2_pre_submission_identity_is_preserved_through_postgres_restart(
    monkeypatch, tmp_path
):
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url != EXPECTED_DATABASE_URL:
        pytest.skip("requires disposable local PostgreSQL")
    _bootstrap_migrations(database_url)

    intent_id = "intent-fw2-hype-001"
    client_order_id = "client-fw2-hype-001"
    submission_attempt_id = "submission-fw2-hype-001"
    reconciliation_context_id = "context-fw2-hype-001"
    coordinator, store = _new_store(database_url)
    store.create_intent(
        LiveOrderIntent(
            intent_id=intent_id,
            client_order_id=client_order_id,
            slot_id="1",
            symbol="HYPEUSDC",
            side=OrderSide.BUY,
            requested_quote_amount=Decimal("41.4117522032984"),
            policy_context="FW2_TEST_ONLY",
        ),
        venue="MOCK",
        account_scope="TEST",
    )
    store.create_reconciliation_context(
        context_id=reconciliation_context_id,
        intent_id=intent_id,
    )
    store.record_submission_preparation(
        intent_id=intent_id,
        attempt_id=submission_attempt_id,
        attempt_sequence=1,
        venue="MOCK",
        account_scope="TEST",
        client_order_id=client_order_id,
        expected_version=0,
        context_id=reconciliation_context_id,
    )
    prepared = store.find_by_client_namespace(
        venue="MOCK",
        account_scope="TEST",
        client_order_id=client_order_id,
    )
    assert prepared["intent_id"] == intent_id
    coordinator.close()

    executor, state_path = _fresh_executor(monkeypatch, tmp_path)
    executor.execute_buy = Mock(wraps=executor.execute_buy)
    gateway = GovernedMockSubmissionGateway(executor)
    try:
        gateway.submit_buy(_signal(), client_order_id=client_order_id)
        raise LostResponse("caller lost response after durable venue mutation")
    except LostResponse:
        pass
    assert executor.execute_buy.call_count == 1
    durable_state = json.loads(state_path.read_text(encoding="utf-8"))
    del gateway
    del executor
    gc.collect()

    restarted_coordinator, restarted_store = _new_store(database_url)
    recovered_intent = restarted_store.find_by_client_namespace(
        venue="MOCK",
        account_scope="TEST",
        client_order_id=client_order_id,
    )
    assert recovered_intent["intent_id"] == intent_id
    restarted, _ = _fresh_executor(monkeypatch, tmp_path, durable_state)
    restarted.execute_buy = Mock(
        side_effect=AssertionError("FALSIFIER::EXTERNAL_REEXECUTION_AFTER_LOST_RESPONSE")
    )
    recovered = GovernedMockSubmissionGateway(restarted).recover_by_client_order_id(
        client_order_id
    )
    assert recovered.client_order_id == client_order_id
    assert restarted.execute_buy.call_count == 0
    restarted_coordinator.close()
