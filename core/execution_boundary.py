from typing import Callable, Any

from core.credentials.api_keys import get_binance_api_key, get_binance_api_secret
from core.execution_mode import ExecutionMode
from core.live_guard import LiveGuard


def build_client_for_mode(
    current_mode: ExecutionMode,
    client_factory: Callable[..., Any],
):
    if current_mode != ExecutionMode.LIVE:
        return client_factory("", "")

    LiveGuard.require_live_real()

    api_key = get_binance_api_key()
    api_secret = get_binance_api_secret()
    return client_factory(api_key, api_secret)
