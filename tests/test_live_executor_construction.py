import ast
import inspect
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from core.execution_boundary import build_live_components
from core.execution_mode import ExecutionMode
from executor.executor_live import ExecutorLive


ROOT = Path(__file__).resolve().parents[1]


def _parse(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _find_class(tree, name):
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == name
    )


def _find_method(class_node, name):
    return next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _find_call(tree, function_name):
    return next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == function_name
    )


def _signature_from_method(method):
    parameters = [
        inspect.Parameter(
            argument.arg,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
        for argument in method.args.args
        if argument.arg != "self"
    ]
    return inspect.Signature(parameters)


def _keyword_names(call):
    return [keyword.arg for keyword in call.keywords if keyword.arg]


def test_live_build_arguments_match_binance_executor_signature_with_capability():
    main_tree = _parse(ROOT / "main.py")
    executor_tree = _parse(ROOT / "core" / "executor" / "binance_executor.py")

    live_call = _find_call(main_tree, "BinanceExecutor")
    executor_class = _find_class(executor_tree, "BinanceExecutor")
    constructor = _find_method(executor_class, "__init__")
    signature = _signature_from_method(constructor)

    assert _keyword_names(live_call) == [
        "client",
        "position_manager",
        "tracker",
        "live_capability",
    ]
    assert "notifier" not in signature.parameters
    assert constructor.args.kwarg is None
    signature.bind(
        client=object(),
        position_manager=object(),
        tracker=object(),
        live_capability=object(),
    )


def test_mock_build_arguments_remain_constructible_by_signature():
    main_tree = _parse(ROOT / "main.py")
    executor_tree = _parse(ROOT / "core" / "executor" / "mock_executor.py")

    mock_call = _find_call(main_tree, "MockExecutor")
    executor_class = _find_class(executor_tree, "MockExecutor")
    constructor = _find_method(executor_class, "__init__")
    signature = _signature_from_method(constructor)

    assert set(_keyword_names(mock_call)) == {
        "client",
        "position_manager",
        "tracker",
        "initial_balance",
        "notifier",
    }
    signature.bind(
        client=object(),
        position_manager=object(),
        tracker=object(),
        initial_balance=1000.0,
        notifier=None,
    )


def test_root_live_executor_requires_bound_capability_after_notifier():
    executor_tree = _parse(ROOT / "executor" / "executor_live.py")
    executor_class = _find_class(executor_tree, "ExecutorLive")
    constructor = _find_method(executor_class, "__init__")
    parameters = [argument.arg for argument in constructor.args.args]

    assert parameters == ["self", "client", "notifier", "live_capability"]
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "is_bound_live_capability"
        for node in ast.walk(constructor)
    )


def test_app_runner_constructs_root_live_executor_only_in_live_mode():
    app_tree = _parse(ROOT / "interface" / "runner" / "app.py")
    app_class = _find_class(app_tree, "AppRunner")
    init_core = _find_method(app_class, "init_core")

    live_guard = next(
        node
        for node in ast.walk(init_core)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "current_mode"
        and any(
            isinstance(comparator, ast.Attribute)
            and comparator.attr == "LIVE"
            for comparator in node.test.comparators
        )
    )

    executor_call = next(
        node
        for node in ast.walk(live_guard)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ExecutorLive"
    )
    keyword_names = [keyword.arg for keyword in executor_call.keywords]

    assert keyword_names == ["client", "live_capability"]
    assert any(
        isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute)
            and target.attr == "executor_live"
            for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
        and node.value.value is None
        for node in ast.walk(init_core)
    )


class RecordingLiveClient:
    def __init__(self):
        self.orders = []

    def get_asset_balance(self, asset):
        assert asset == "BTC"
        return {"free": "1.27"}

    def get_symbol_info(self, symbol):
        assert symbol == "BTCUSDC"
        return {"filters": [{"filterType": "LOT_SIZE", "stepSize": "0.1"}]}

    def create_order(self, **kwargs):
        self.orders.append(kwargs)
        if kwargs["side"] == "BUY":
            return {
                "status": "FILLED",
                "executedQty": "0.1",
                "orderId": 1,
                "fills": [{"price": "100", "qty": "0.1"}],
            }
        return {
            "status": "FILLED",
            "executedQty": "1.2",
            "orderId": 2,
        }


class RecordingNotifier:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


def _bound_live_pair(client):
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
        return build_live_components(ExecutionMode.LIVE, lambda *_: client)


def test_root_live_executor_rejects_missing_forged_and_wrong_capability():
    client = RecordingLiveClient()

    with pytest.raises(RuntimeError):
        ExecutorLive(client=client, live_capability=None)

    with pytest.raises(RuntimeError):
        ExecutorLive(client=client, live_capability=object())

    authorized_client, capability = _bound_live_pair(client)
    with pytest.raises(RuntimeError):
        ExecutorLive(client=RecordingLiveClient(), live_capability=capability)

    assert authorized_client.orders == []


def test_root_live_executor_preserves_buy_sell_lot_size_and_notifier():
    client = RecordingLiveClient()
    _, capability = _bound_live_pair(client)
    notifier = RecordingNotifier()
    executor = ExecutorLive(
        client=client,
        notifier=notifier,
        live_capability=capability,
    )

    buy_result = executor.place_market_buy_quote("BTCUSDC", 10.0)
    sell_result = executor.place_market_sell_all("BTCUSDC")

    assert buy_result["status"] == "FILLED"
    assert sell_result["status"] == "FILLED"
    assert client.orders[0]["quoteOrderQty"] == 10.0
    assert client.orders[0]["side"] == "BUY"
    assert client.orders[1]["side"] == "SELL"
    assert client.orders[1]["quantity"] == pytest.approx(1.2)
    assert notifier.messages == ["BUY | BTCUSDC\n100.00000000 | 10.00 USDC"]
