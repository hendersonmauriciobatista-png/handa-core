import os
from unittest.mock import patch

from core.execution_boundary import (
    build_client_for_mode,
    build_live_components,
    is_bound_live_capability,
)
from core.execution_mode import ExecutionMode


class RecordingClientFactory:
    def __init__(self):
        self.calls = []

    def __call__(self, api_key, api_secret):
        self.calls.append((api_key, api_secret))
        return object()


def test_mock_with_credentials_never_builds_authenticated_client():
    factory = RecordingClientFactory()

    with patch.dict(
        os.environ,
        {
            "BINANCE_API_KEY": "unit-test-key",
            "BINANCE_API_SECRET": "unit-test-secret",
        },
        clear=True,
    ):
        build_client_for_mode(ExecutionMode.MOCK, factory)

    assert factory.calls == [("", "")]


def test_live_denial_matrix_fails_before_credential_loading():
    denied_environments = [
        {},
        {"ENABLE_LIVE_REAL": "false", "CONFIRM_LIVE_REAL": "YES"},
        {"ENABLE_LIVE_REAL": "true"},
        {"ENABLE_LIVE_REAL": "true", "CONFIRM_LIVE_REAL": "NO"},
    ]

    for environment in denied_environments:
        factory = RecordingClientFactory()
        with patch.dict(os.environ, environment, clear=True):
            try:
                build_client_for_mode(ExecutionMode.LIVE, factory)
            except RuntimeError:
                pass
            else:
                raise AssertionError("LIVE authorization should be denied")

        assert factory.calls == []


def test_authorized_live_reaches_only_the_stub_client_boundary():
    factory = RecordingClientFactory()

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
        client = build_client_for_mode(ExecutionMode.LIVE, factory)

    assert client is not None
    assert factory.calls == [("unit-test-key", "unit-test-secret")]


def test_authorized_live_returns_a_capability_bound_to_the_client():
    factory = RecordingClientFactory()

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

    assert is_bound_live_capability(capability, client)
    assert not is_bound_live_capability(capability, object())
