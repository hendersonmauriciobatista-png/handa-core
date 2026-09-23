from types import SimpleNamespace

import pytest

from core.executor.mock_executor import MockExecutor as CoreMockExecutor
from core.position.position_manager import CloseReason, PositionManager
from executor.mock_executor import MockExecutor as LegacyMockExecutor


class RecordingNotifier:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


class FailingNotifier:
    def send(self, message):
        raise RuntimeError("telegram unavailable")


def make_position_manager(notifier):
    manager = object.__new__(PositionManager)
    manager._positions = {}
    manager._history = []
    manager._snapshot_buffer = []
    manager._snapshot_buffer_size = 50
    manager.penalty_map = {}
    manager.last_traded_symbol = None
    manager.lc1 = SimpleNamespace(log_buy=lambda event: None, log_sell=lambda event: None)
    manager.notifier = notifier
    manager.get_performance_summary_text = lambda: ""
    manager.get_snapshot_summary_text = lambda: ""
    manager.get_daily_summary_text = lambda: ""
    return manager


def test_position_manager_is_the_single_buy_owner_and_preserves_format():
    notifier = RecordingNotifier()
    manager = make_position_manager(notifier)

    manager.open_position(
        pair="BTCUSDC",
        entry_price=123.45678901,
        capital_invested=12.3456,
        quantity=0.1,
    )

    assert notifier.messages == [
        "BUY | BTCUSDC\nENTRY | 123.45678901\nCAPITAL | 12.3456 USDC"
    ]


def test_position_manager_is_the_single_sell_owner_and_preserves_format():
    notifier = RecordingNotifier()
    manager = make_position_manager(notifier)
    manager.open_position(
        pair="BTCUSDC",
        entry_price=100.0,
        capital_invested=100.0,
        quantity=1.0,
    )
    notifier.messages.clear()

    manager.close_position(
        symbol="BTCUSDC",
        exit_price=110.0,
        reason=CloseReason.TAKE_PROFIT,
    )

    assert len(notifier.messages) == 1
    assert notifier.messages[0].startswith("SELL | BTCUSDC\n🟢 +")
    assert notifier.messages[0].endswith("\nTAKE_PROFIT | 0s")


@pytest.mark.parametrize("executor_class", [CoreMockExecutor, LegacyMockExecutor])
def test_mock_executors_do_not_emit_redundant_buy(executor_class):
    notifier = RecordingNotifier()
    executor = object.__new__(executor_class)
    executor.positions = {}
    executor.balance_usdc = 1000.0
    executor.notifier = notifier
    executor.position_manager = None
    executor.tracker = None
    executor.live_shadow = None
    executor._save_state = lambda: None

    result = executor.execute_buy(
        SimpleNamespace(
            pair="BTCUSDC",
            entry_price=100.0,
            allocated_usdc=100.0,
            stop_loss=95.0,
            take_profit=110.0,
        )
    )

    assert result.status == "FILLED"
    assert notifier.messages == []


def test_telegram_failure_does_not_interfere_with_position_execution():
    manager = make_position_manager(FailingNotifier())

    opened = manager.open_position(
        pair="BTCUSDC",
        entry_price=100.0,
        capital_invested=100.0,
        quantity=1.0,
    )
    closed = manager.close_position(
        symbol="BTCUSDC",
        exit_price=110.0,
        reason=CloseReason.TAKE_PROFIT,
    )

    assert opened is not None
    assert closed is not None
    assert closed.status.value == "CLOSED"
    assert manager.get_position(symbol="BTCUSDC") is None
