import json
import os
from contextlib import ExitStack
from unittest.mock import Mock, patch

import executor.mock_executor as mock_executor_module
from core.position.position_manager import PositionManager
from core.slot_controller import SlotController


class FakeClient:
    def get_symbol_ticker(self, symbol):
        return {"price": "110"}


def _position_record(*, legacy=False):
    record = {
        "pair": "BTCUSDC",
        "entry_price": 100.0,
        "quantity": 2.0,
        "allocated_usdc": 200.0,
        "stop_loss": 90.0,
        "take_profit": 110.0,
    }
    if not legacy:
        record.update(
            {
                "position_id": "position-btc-1",
                "opened_at": "2026-10-04T12:00:00",
            }
        )
    return record


def _state(*, versioned=True, positions=True):
    data = {
        "initial_balance": 1000.0,
        "current_balance": 800.0,
        "positions": {"BTCUSDC": _position_record(legacy=not versioned)}
        if positions
        else {},
    }
    if versioned:
        data["state_format_version"] = 1
    return data


def _fresh_runtime(monkeypatch, tmp_path, state):
    state_path = tmp_path / "mock_state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    temp_state_path = tmp_path / "mock_state.json.tmp"
    original_exists = mock_executor_module.os.path.exists
    original_open = open

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
            os.replace(temp_state_path, state_path)
        else:
            os.replace(source, destination)

    with ExitStack() as stack:
        stack.enter_context(patch.object(mock_executor_module, "PostgresStateRepository", None))
        stack.enter_context(patch.object(mock_executor_module.os.path, "exists", exists))
        stack.enter_context(patch("builtins.open", open_redirect))
        stack.enter_context(patch.object(mock_executor_module.os, "makedirs"))
        stack.enter_context(patch.object(mock_executor_module.os, "replace", replace_redirect))

        manager = PositionManager()
        manager.lc1.log_buy = Mock()
        manager.notifier = Mock()
        executor = mock_executor_module.MockExecutor(
            client=FakeClient(),
            position_manager=manager,
            initial_balance=1000.0,
        )
        controller = SlotController(
            slot_ids=[1, 2],
            client=FakeClient(),
            executor=executor,
            risk_manager=None,
            cooldown=0,
        )
        controller.position_manager = manager
        reconciliation = controller.reconcile_persisted_mock_state()
        executor.state_file = str(state_path)

    return state_path, manager, executor, controller, reconciliation


def test_versioned_restart_reconstructs_authorities_without_side_effects(
    monkeypatch, tmp_path
):
    state_path, manager, executor, controller, reconciliation = _fresh_runtime(
        monkeypatch, tmp_path, _state()
    )

    assert executor.state_classification == "CURRENT_VERSIONED_RECORD"
    assert list(executor.positions) == ["BTCUSDC"]
    assert manager.has_position(symbol="BTCUSDC")
    assert controller.get_active_positions() == 1
    assert controller.get_slot(1).state == "RUNNING"
    assert controller.get_slot(1).pair == "BTCUSDC"
    assert reconciliation["status"] == "RECONCILED"
    assert controller._contained_execution_facts == {}
    assert manager.get_history() == []
    manager.lc1.log_buy.assert_not_called()
    manager.notifier.send.assert_not_called()


def test_legacy_restart_is_contained_and_blocks_duplicate(monkeypatch, tmp_path):
    _, manager, executor, controller, reconciliation = _fresh_runtime(
        monkeypatch, tmp_path, _state(versioned=False)
    )

    assert executor.state_classification == "LEGACY_UNVERSIONED_RECORD"
    assert not manager.has_position(symbol="BTCUSDC")
    assert controller.get_active_positions() == 1
    assert reconciliation["status"] == "CONTAINED"
    assert reconciliation["reserved_symbols"] == ["BTCUSDC"]
    assert "LEGACY_STATE_REQUIRES_CONTAINMENT" in reconciliation["diagnostics"][0]

    executor.execute_buy = Mock(side_effect=AssertionError("duplicate reached executor"))
    slot = controller.get_slot(1)
    slot.pair = "BTCUSDC"
    slot.pending_buy_signal = Mock(
        pair="BTCUSDC",
        entry_price=100.0,
        allocated_usdc=100.0,
        stop_loss=90.0,
        take_profit=110.0,
    )
    controller._execute_buy(slot)
    executor.execute_buy.assert_not_called()


def test_reconstruction_is_idempotent_and_zero_state_is_normal(monkeypatch, tmp_path):
    _, manager, _, controller, first = _fresh_runtime(monkeypatch, tmp_path, _state())
    first_id = manager.get_position(symbol="BTCUSDC").id
    second = controller.reconcile_persisted_mock_state()

    assert first == second
    assert manager.get_position(symbol="BTCUSDC").id == first_id
    assert len(manager.get_active_positions()) == 1

    _, empty_manager, _, empty_controller, empty = _fresh_runtime(
        monkeypatch, tmp_path, _state(positions=False)
    )
    assert empty["status"] == "RECONCILED"
    assert empty_manager.get_active_positions() == []
    assert empty_controller.get_active_positions() == 0


def test_malformed_versioned_state_fails_safe(monkeypatch, tmp_path):
    malformed = _state()
    del malformed["positions"]["BTCUSDC"]["opened_at"]
    _, manager, executor, controller, reconciliation = _fresh_runtime(
        monkeypatch, tmp_path, malformed
    )

    assert executor.state_classification == "MALFORMED_RECORD"
    assert executor.positions == {}
    assert manager.get_active_positions() == []
    assert controller.get_active_positions() == 0
    assert reconciliation["status"] == "CONTAINED"
    assert reconciliation["diagnostics"]
    assert controller._restart_entries_blocked is True


def test_successful_sell_persists_closed_state(monkeypatch, tmp_path):
    state_path, _, executor, _, _ = _fresh_runtime(monkeypatch, tmp_path, _state())

    result = executor.execute_sell("BTCUSDC")

    assert result.symbol == "BTCUSDC"
    assert executor.positions == {}
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["state_format_version"] == 1
    assert persisted["positions"] == {}
