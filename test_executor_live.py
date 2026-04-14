from datetime import datetime, timezone

from h_a.core.executor.executor_live import ExecutorLive
from h_a.core.exchange_adapter.binance_spot_adapter import BinanceSpotAdapter
from h_a.core.utils.mock_logger import MockLogger


# =========================================================
# 🔐 CHAVES API (JÁ PREENCHIDAS POR VOCÊ)
# =========================================================
API_KEY = "XhLJ00oyaxMtssBcCBqvcokzTQy5hFY3N67CSHRUfuuL3LTXpYnsNWsGNIKYFvvO"
API_SECRET = "FOKEHS57A5fKWBhY30My6dEWzz7POQrhuGyX1Uw1l2JiMrCP7AXK4839SjiKMpiR"


def stop_checker_false():
    return False


logger = MockLogger()

# =========================================================
# ⚙️ CRIAÇÃO DO ADAPTER E DO EXECUTOR (ATIVO)
# =========================================================
adapter = BinanceSpotAdapter(API_KEY, API_SECRET)

executor = ExecutorLive(
    exchange_adapter=adapter,
    stop_checker=stop_checker_false,
    logger=logger
)

# =========================================================
# 📤 COMANDO LIVE (BUY SIMBÓLICO)
# =========================================================
command_live = {
    "slot_id": "SLOT-LIVE-1",
    "side": "BUY",
    "symbol": "BTCUSDC",
    "quantity": 0.0001,  # ajuste SOMENTE se a Binance reclamar
    "mode": "LIVE",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "policy_token": "HUMAN_CONFIRMED"
}

# =========================================================
# 🔴 EXECUÇÃO REAL — LIVE ASSISTIDO
# =========================================================
print("\n--- LIVE ASSISTIDO: PRIMEIRO BUY ---")
result = executor.execute(command_live)
print("RESULTADO:", result)
