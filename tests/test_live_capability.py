import os
from unittest.mock import patch

from core.execution_boundary import (
    build_live_components,
    is_valid_live_capability,
)
from core.execution_mode import ExecutionMode
from core.executor.binance_executor import BinanceExecutor


class FakeClient:
    def __init__(self):
        self.exchange_info_calls = 0
        self.order_calls = 0

    def get_exchange_info(self):
        self.exchange_info_calls += 1
        return {"symbols": []}

    def order_market_buy(self, **kwargs):
        self.order_calls += 1
        raise AssertionError("order method must not be called")

    def order_market_sell(self, **kwargs):
        self.order_calls += 1
        raise AssertionError("order method must not be called")


class RecordingFactory:
    def __init__(self):
        self.calls = []
        self.client = FakeClient()

    def __call__(self, api_key, api_secret):
        self.calls.append((api_key, api_secret))
        return self.client


def test_mock_emits_no_capability_and_does_not_read_credentials():
    factory = RecordingFactory()

    with patch.dict(
        os.environ,
        {
            "BINANCE_API_KEY": "unit-test-key",
            "BINANCE_API_SECRET": "unit-test-secret",
        },
        clear=True,
    ):
        client, capability = build_live_components(ExecutionMode.MOCK, factory)

    assert client is factory.client
    assert capability is None
    assert factory.calls == [("", "")]


def test_direct_binance_executor_without_capability_fails_closed():
    try:
        BinanceExecutor(
            client=FakeClient(),
            position_manager=object(),
            tracker=object(),
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("missing LIVE capability must be rejected")


def test_forged_capability_fails_closed():
    try:
        BinanceExecutor(
            client=FakeClient(),
            position_manager=object(),
            tracker=object(),
            live_capability=object(),
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("forged LIVE capability must be rejected")


def test_authorized_boundary_builds_executor_without_order_io():
    factory = RecordingFactory()

    with patch.dict(
        os.environ,
        {
            "ENABLE_LIVE_REAL": "true",
            "CONFIRM_LIVE_REAL": "YES",
            "BINANCE_API_KEY": "unit-test-key",
            "BINANCE_API_SECRET": "unit-test-secret",
        },
        clear=True,
    ):
        client, capability = build_live_components(ExecutionMode.LIVE, factory)
        executor = BinanceExecutor(
            client=client,
            position_manager=object(),
            tracker=object(),
            live_capability=capability,
        )

    assert is_valid_live_capability(capability)
    assert executor.client is factory.client
    assert factory.client.exchange_info_calls == 1
    assert factory.client.order_calls == 0
