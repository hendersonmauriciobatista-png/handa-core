from datetime import datetime, timezone

from h_a.core.executor.executor_live import ExecutorLive
from h_a.core.exchange_adapter.mock_adapter import MockAdapter
from h_a.core.utils.mock_logger import MockLogger


def stop_checker_false():
    return False


def stop_checker_true():
    return True


logger = MockLogger()
adapter = MockAdapter()

executor = ExecutorLive(
    exchange_adapter=adapter,
    stop_checker=stop_checker_false,
    logger=logger
)

command_ok = {
    "slot_id": "SLOT-1",
    "side": "BUY",
    "symbol": "BTCUSDC",
    "quantity": 0.001,
    "mode": "LIVE",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "policy_token": "OK"
}

print("\n--- TESTE 1: EXECUÇÃO OK ---")
executor.execute(command_ok)

print("\n--- TESTE 2: STOP ATIVO ---")
executor_stop = ExecutorLive(
    exchange_adapter=adapter,
    stop_checker=stop_checker_true,
    logger=logger
)
executor_stop.execute(command_ok)

print("\n--- TESTE 3: COMANDO INVÁLIDO (sem policy) ---")
bad_command = command_ok.copy()
bad_command.pop("policy_token")
executor.execute(bad_command)
