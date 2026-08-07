from typing import Dict, Any
from datetime import datetime, timezone

from h_a.core.exchange_adapter.base_adapter import ExchangeAdapter


class ExecutorLive:
    """
    ExecutorLive
    - Executa ordens REAIS
    - Não decide
    - Não recalcula
    - Não tenta corrigir erro
    - Sempre retorna status explícito
    """

    def __init__(self, exchange_adapter: ExchangeAdapter, stop_checker, logger):
        self.exchange_adapter = exchange_adapter
        self.stop_checker = stop_checker
        self.logger = logger

    def execute(self, command: Dict[str, Any]) -> Dict[str, Any]:
        started_at = datetime.now(timezone.utc).isoformat()

        # 1️⃣ STOP global
        if self.stop_checker():
            result = {
                "status": "ABORTED",
                "reason": "STOP_ACTIVE",
                "timestamp": started_at
            }
            self._log(command, result)
            return result

        # 2️⃣ Validação mínima
        missing = self._missing_fields(command)
        if missing:
            result = {
                "status": "ABORTED",
                "reason": f"MISSING_FIELDS: {missing}",
                "timestamp": started_at
            }
            self._log(command, result)
            return result

        # 3️⃣ Modo LIVE
        if command.get("mode") != "LIVE":
            result = {
                "status": "ABORTED",
                "reason": "INVALID_MODE",
                "timestamp": started_at
            }
            self._log(command, result)
            return result

        # 4️⃣ Policy token
        if not command.get("policy_token"):
            result = {
                "status": "ABORTED",
                "reason": "POLICY_TOKEN_MISSING",
                "timestamp": started_at
            }
            self._log(command, result)
            return result

        # 5️⃣ Execução via Adapter
        adapter_payload = {
            "side": command["side"],
            "symbol": command["symbol"],
            "quantity": command["quantity"],
            "order_type": "MARKET"
        }

        response = self.exchange_adapter.send_order(adapter_payload)

        # 6️⃣ Log obrigatório
        self._log(command, response)

        return response

    @staticmethod
    def _missing_fields(command: Dict[str, Any]) -> list:
        required = [
            "slot_id",
            "side",
            "symbol",
            "quantity",
            "mode",
            "timestamp",
            "policy_token"
        ]
        return [f for f in required if f not in command]

    def _log(self, command: Dict[str, Any], result: Dict[str, Any]) -> None:
        payload = {
            "executor": "ExecutorLive",
            "mode": "LIVE",
            "slot_id": command.get("slot_id"),
            "side": command.get("side"),
            "symbol": command.get("symbol"),
            "quantity": command.get("quantity"),
            "result": result,
            "logged_at": datetime.now(timezone.utc).isoformat()
        }
        self.logger.info(payload)
