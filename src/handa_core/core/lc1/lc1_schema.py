from datetime import datetime


def _now():
    return datetime.utcnow().isoformat()


def build_buy_event(data: dict) -> dict:
    return {
        "timestamp": _now(),
        "layer": "LC1",
        "event_type": "BUY",
        **data,
    }


def build_sell_event(data: dict) -> dict:
    return {
        "timestamp": _now(),
        "layer": "LC1",
        "event_type": "SELL",
        **data,
    }