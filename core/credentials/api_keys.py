import os


BINANCE_API_KEY = "BINANCE_API_KEY"
BINANCE_API_SECRET = "BINANCE_API_SECRET"


def _read_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Required credential is missing: {name}")
    return value


def get_binance_api_key() -> str:
    return _read_required(BINANCE_API_KEY)


def get_binance_api_secret() -> str:
    return _read_required(BINANCE_API_SECRET)
