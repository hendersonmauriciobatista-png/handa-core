"""HYPEUSDC runtime-ghost regression under the headless fail-safe policy.

The original expected-RED reproduced an executor-only HYPEUSDC position.
This regression preserves that incident while requiring the authorized
resolution: containment before the executor boundary.
"""

import ast
import json
from unittest.mock import Mock
from types import SimpleNamespace
from pathlib import Path

from tests.test_restart_durability import _fresh_runtime, _state


def _observe_only(controller):
    controller.operational_effects_blocked = True


def _buy_signal(pair="HYPEUSDC"):
    return SimpleNamespace(
        pair=pair,
        entry_price=94.87,
        allocated_usdc=41.4117522032984,
        stop_loss=90.0,
        take_profit=100.0,
    )


def test_headless_mock_buy_is_contained_before_execution(monkeypatch, tmp_path, capsys):
    state_path, position_manager, executor, controller, _ = _fresh_runtime(
        monkeypatch, tmp_path, _state(positions=False)
    )

    _observe_only(controller)
    executor.execute_buy = Mock(side_effect=AssertionError("BUY reached executor"))
    initial_balance = executor.balance_usdc
    initial_positions = dict(executor.positions)
    initial_state = json.loads(state_path.read_text(encoding="utf-8"))

    slot = controller.get_slot(1)
    slot.pair = "HYPEUSDC"
    slot._state = "READY"
    slot.pending_buy_signal = _buy_signal()

    result = controller._execute_buy(slot)

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    controller._audit_operational_consistency()
    audit_output = capsys.readouterr().out

    executor.execute_buy.assert_not_called()
    assert result["status"] == "CONTAINED"
    assert result["outcome"] == "AUTHORITY_UNAVAILABLE"
    assert result["no_effect"] is True
    assert executor.balance_usdc == initial_balance
    assert executor.positions == initial_positions == {}
    assert persisted == initial_state
    assert not position_manager.has_position(symbol="HYPEUSDC")
    assert all(candidate.state != "RUNNING" for candidate in controller.get_slots().values())
    assert controller._contained_execution_facts == {}
    assert controller._operational_containment_events[-1]["no_effect"] is True
    assert controller._operational_containment_events[-1]["operation"] == "BUY"
    assert "stage=PRE_EXECUTION_AUTHORITY_BLOCKED" in audit_output
    assert "[RECONCILE CRITICAL] executor posição fantasma" not in audit_output


def test_blocked_sell_preserves_reconstructed_position(monkeypatch, tmp_path, capsys):
    state_path, position_manager, executor, controller, _ = _fresh_runtime(
        monkeypatch, tmp_path, _state()
    )
    _observe_only(controller)
    executor.execute_sell = Mock(side_effect=AssertionError("SELL reached executor"))

    slot = controller.get_slot(1)
    initial_balance = executor.balance_usdc
    initial_positions = dict(executor.positions)
    initial_state = json.loads(state_path.read_text(encoding="utf-8"))
    initial_position = position_manager.get_position(symbol="BTCUSDC")
    initial_state_name = slot.state

    result = controller._execute_sell(slot)

    assert executor.execute_sell.call_count == 0
    assert result["status"] == "CONTAINED"
    assert result["outcome"] == "AUTHORITY_UNAVAILABLE"
    assert executor.balance_usdc == initial_balance
    assert executor.positions == initial_positions
    assert json.loads(state_path.read_text(encoding="utf-8")) == initial_state
    assert position_manager.get_position(symbol="BTCUSDC") is initial_position
    assert slot.state == initial_state_name == "RUNNING"
    assert slot.pair == "BTCUSDC"
    assert controller._contained_execution_facts == {}
    assert controller._operational_containment_events[-1]["operation"] == "SELL"
    assert "stage=PRE_EXECUTION_AUTHORITY_BLOCKED" in capsys.readouterr().out


def test_observation_continues_after_blocked_buy(monkeypatch, tmp_path):
    _, _, executor, controller, _ = _fresh_runtime(
        monkeypatch, tmp_path, _state(positions=False)
    )
    _observe_only(controller)
    executor.execute_buy = Mock(side_effect=AssertionError("BUY reached executor"))

    slot = controller.get_slot(1)
    slot.pair = "HYPEUSDC"
    slot._state = "READY"
    slot.pending_buy_signal = _buy_signal()
    controller._execute_buy(slot)

    controller.run_cycle()

    assert controller._cycle_counter == 1
    assert controller.get_slot(1).state == "IDLE"
    executor.execute_buy.assert_not_called()


def test_restrictive_policy_does_not_construct_application_authority(monkeypatch, tmp_path):
    _, _, _, controller, _ = _fresh_runtime(
        monkeypatch, tmp_path, _state(positions=False)
    )
    _observe_only(controller)

    assert controller.operational_effects_blocked is True
    assert not hasattr(controller, "operational_application_binding")
    assert not hasattr(controller, "effect_application_coordinator")
    assert not hasattr(controller, "application_attempt_id")
    assert not hasattr(controller, "effect_request_id")
    assert not hasattr(controller, "position_effect_authority")


def test_blocked_buy_does_not_create_restart_effect(monkeypatch, tmp_path):
    state_path, _, executor, controller, _ = _fresh_runtime(
        monkeypatch, tmp_path, _state(positions=False)
    )
    _observe_only(controller)
    executor.execute_buy = Mock(side_effect=AssertionError("BUY reached executor"))

    slot = controller.get_slot(1)
    slot.pair = "HYPEUSDC"
    slot._state = "READY"
    slot.pending_buy_signal = _buy_signal()
    controller._execute_buy(slot)

    restarted_state = json.loads(state_path.read_text(encoding="utf-8"))
    _, restarted_pm, restarted_executor, restarted_controller, reconciliation = _fresh_runtime(
        monkeypatch, tmp_path, restarted_state
    )

    assert restarted_executor.positions == {}
    assert restarted_pm.get_active_positions() == []
    assert restarted_controller.get_active_positions() == 0
    assert reconciliation["status"] == "RECONCILED"


def test_run_headless_explicitly_configures_observe_only_policy():
    run_headless_path = Path(__file__).resolve().parents[1] / "run_headless.py"
    source = run_headless_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(run_headless_path))

    slot_controller_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "SlotController"
    ]
    assert len(slot_controller_calls) == 1

    blocked_keyword = next(
        (
            keyword
            for keyword in slot_controller_calls[0].keywords
            if keyword.arg == "operational_effects_blocked"
        ),
        None,
    )
    assert blocked_keyword is not None
    assert isinstance(blocked_keyword.value, ast.Constant)
    assert blocked_keyword.value.value is True

    startup_semantics = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "mode=OBSERVE_ONLY" in startup_semantics
    assert "operational_effects=BLOCKED" in startup_semantics
    assert (
        "reason=GOVERNED_APPLICATION_AUTHORITY_UNAVAILABLE"
        in startup_semantics
    )
