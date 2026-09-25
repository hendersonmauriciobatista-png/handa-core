from typing import Callable, Any

from core.credentials.api_keys import get_binance_api_key, get_binance_api_secret
from core.execution_mode import ExecutionMode
from core.live_guard import LiveGuard


class LiveExecutionCapability:
    """Opaque in-process evidence issued only by the LIVE boundary."""

    __slots__ = ("_marker", "_bound_client")

    def __init__(self, marker: object, bound_client: object):
        self._marker = marker
        self._bound_client = bound_client


_CAPABILITY_MARKER = object()


def is_valid_live_capability(capability: object) -> bool:
    return (
        isinstance(capability, LiveExecutionCapability)
        and capability._marker is _CAPABILITY_MARKER
    )


def is_bound_live_capability(capability: object, client: object) -> bool:
    return (
        is_valid_live_capability(capability)
        and capability._bound_client is client
    )


def build_live_components(
    current_mode: ExecutionMode,
    client_factory: Callable[..., Any],
):
    if current_mode != ExecutionMode.LIVE:
        return client_factory("", ""), None

    LiveGuard.require_live_real()

    api_key = get_binance_api_key()
    api_secret = get_binance_api_secret()
    client = client_factory(api_key, api_secret)
    capability = LiveExecutionCapability(_CAPABILITY_MARKER, client)
    return client, capability


def build_client_for_mode(
    current_mode: ExecutionMode,
    client_factory: Callable[..., Any],
):
    client, _capability = build_live_components(current_mode, client_factory)
    return client
