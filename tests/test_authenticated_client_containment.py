import ast
import inspect
from pathlib import Path

import pytest

import executor.mock_executor as mock_executor_module

mock_executor_module.ExecutorMock = mock_executor_module.MockExecutor

from executor.executor_router import ExecutorRouter
from h_a.core.exchange_adapter.binance_spot_adapter import BinanceSpotAdapter
from h_a.engine.credential_service import CredentialService
from h_a.engine.wallet_balance_service import WalletBalanceService


def _client_constructor_calls(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Client"
    ]


def test_scoped_consumers_do_not_construct_authenticated_clients():
    root = Path(inspect.getfile(BinanceSpotAdapter)).parents[3]
    paths = [
        root / "executor" / "executor_router.py",
        root / "interface" / "desktop" / "app_layout.py",
        root / "h_a" / "core" / "exchange_adapter" / "binance_spot_adapter.py",
        root / "h_a" / "engine" / "wallet_balance_service.py",
    ]

    assert all(not _client_constructor_calls(path) for path in paths)


def test_router_rejects_raw_credential_configuration():
    router = ExecutorRouter(executor_mock=object())

    with pytest.raises(RuntimeError, match="ExecutionBoundary"):
        router.configure_keys("unit-test-key", "unit-test-secret")


def test_router_accepts_only_preconstructed_client():
    router = ExecutorRouter(executor_mock=object())
    client = object()

    assert router.configure_client(client) is True
    assert router.client is client
    assert router.api_valid is True


def test_router_rejects_none_client():
    router = ExecutorRouter(executor_mock=object())

    assert router.configure_client(None) is False
    assert router.client is None
    assert router.api_valid is False


def test_subordinate_consumers_require_a_preconstructed_client():
    with pytest.raises(ValueError):
        BinanceSpotAdapter(None)

    with pytest.raises(ValueError):
        WalletBalanceService(None)


def test_credential_service_cannot_persist_governed_credentials():
    service = CredentialService()

    with pytest.raises(RuntimeError):
        service.save("unit-test-key", "unit-test-secret")

    assert service.load() == (None, None)
