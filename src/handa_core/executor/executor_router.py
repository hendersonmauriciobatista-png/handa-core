# =================================================
# executor/executor_router.py
# Executor Router — H&A
# Decide MOCK ou LIVE e protege execução
# =================================================

from executor.mock_executor import ExecutorMock
from binance.client import Client


class ExecutorRouter:

    MODE_MOCK = "MOCK"
    MODE_LIVE = "LIVE"

    # =================================================
    # INIT
    # =================================================

    def __init__(self, executor_mock: ExecutorMock, executor_live=None):

        self.executor_mock = executor_mock
        self.executor_live = executor_live

        self.mode = self.MODE_MOCK

        # estado da API
        self.client = None
        self.api_valid = False

    # =================================================
    # CONFIGURAÇÃO DE API BINANCE
    # =================================================

    def configure_keys(self, api_key: str, secret_key: str):

        try:

            client = Client(api_key, secret_key)

            # testa conexão com Binance
            client.ping()

            self.client = client
            self.api_valid = True

            print("BINANCE CONNECTED ✔")

            return True

        except Exception as e:

            print("API ERROR:", e)

            self.api_valid = False

            return False

    # =================================================
    # ALIAS DE COMPATIBILIDADE
    # =================================================

    def execute(self, *args, **kwargs):
        """
        Alias para compatibilidade com AutoLoop
        """
        return self.executar(*args, **kwargs)

    # =================================================
    # MODE
    # =================================================

    def set_mode(self, mode: str):

        if mode not in (self.MODE_MOCK, self.MODE_LIVE):
            raise ValueError("Modo inválido")

        # LIVE só ativa se API válida
        if mode == self.MODE_LIVE and not self.api_valid:
            print("LIVE BLOCKED — API NOT VALID")
            return

        self.mode = mode

    # =================================================
    # EXECUÇÃO DE CICLO (TRADE)
    # =================================================

    def executar(self, *args, **kwargs):
        """
        Execução genérica (usada pelo AutoLoop)
        """

        if self.mode == self.MODE_MOCK:
            return self.executor_mock.executar(*args, **kwargs)

        elif self.mode == self.MODE_LIVE:

            # proteção extra
            if not self.api_valid:
                return {
                    "status": "blocked",
                    "reason": "API_NOT_VALID"
                }

            if self.executor_live:
                return self.executor_live.executar(*args, **kwargs)

            return {
                "status": "blocked",
                "reason": "LIVE_EXECUTOR_NOT_READY"
            }

    # =================================================
    # SALDO
    # =================================================

    def get_balance(self):

        if self.mode == self.MODE_MOCK:
            return self.executor_mock.get_balance()

        elif self.mode == self.MODE_LIVE:

            if not self.client:
                return {
                    "error": "NO_BINANCE_CONNECTION"
                }

            try:

                account = self.client.get_account()

                for asset in account["balances"]:

                    if asset["asset"] == "USDC":
                        return float(asset["free"])

                return 0.0

            except Exception as e:

                return {
                    "error": str(e)
                }

    # =================================================
    # STATUS
    # =================================================

    def snapshot(self):

        return {
            "mode": self.mode,
            "api_valid": self.api_valid,
            "exchange": "BINANCE_SPOT"
        }