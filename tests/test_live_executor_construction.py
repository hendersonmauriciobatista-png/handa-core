import ast
import inspect
from pathlib import Path


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


def test_live_build_arguments_match_binance_executor_signature_without_notifier():
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
    ]
    assert "notifier" not in signature.parameters
    assert constructor.args.kwarg is None
    signature.bind(
        client=object(),
        position_manager=object(),
        tracker=object(),
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
