# ============================================================
# interface/runner/app.py
# Runner estrutural do H&A
# v8 - AutoLoop conectado ao StateController
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()

from binance.client import Client

from core.market.market_snapshot_service import MarketSnapshotService
from core.slot_controller import SlotController
from core.auto_loop import AutoLoop
from core.system.state_controller import StateController
from h_a.system_state_assembler import SystemStateAssembler

from core.governance.policy_layer import PolicyLayer
from core.decision.decision_engine import DecisionEngine

from core.market.market_data_provider import MarketDataProvider
from core.market.symbol_metadata_provider import SymbolMetadataProvider
from core.market.wallet_balance_provider import WalletBalanceProvider

from executor.mock_executor import ExecutorMock
from executor.executor_live import ExecutorLive


# ============================================================
# CONTEXTO GLOBAL
# ============================================================

class AppContext:

    def __init__(self):

        # Core
        self.state_controller = None
        self.assembler = None
        self.slot_controller = None
        self.auto_loop = None

        # Trading
        self.executor = None
        self.executor_live = None
        self.decision_engine = None

        self.market_provider = None
        self.snapshot_service = None
        self.metadata_provider = None
        self.wallet_provider = None
        self.binance_client = None

        # Governança
        self.policy = None

        # Estado geral
        self.mode = "MOCK"
        self.booted = False
        self.live_ready = False
        self.core_ready = False


# ============================================================
# RUNNER PRINCIPAL
# ============================================================

class AppRunner:

    def __init__(self):
        self.ctx = AppContext()

    # --------------------------------------------------------
    # INIT CORE
    # --------------------------------------------------------

    def init_core(self):

        # Governança
        self.ctx.policy = PolicyLayer()

        # Estado
        self.ctx.state_controller = StateController()
        self.ctx.assembler = SystemStateAssembler(self.ctx.state_controller)

        # Executor MOCK padrão
        self.ctx.executor = ExecutorMock()

        # API Keys
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")

        if not api_key or not api_secret:
            raise ValueError("API keys não encontradas nas variáveis de ambiente.")

        # CLIENT BINANCE
        self.ctx.binance_client = Client(
            api_key,
            api_secret,
            requests_params={"timeout": 5}
        )

        # =====================================================
        # MARKET LAYER
        # =====================================================

        self.ctx.market_provider = MarketDataProvider(self.ctx.binance_client)

        self.ctx.snapshot_service = MarketSnapshotService(
            self.ctx.binance_client
        )

        self.ctx.metadata_provider = SymbolMetadataProvider(self.ctx.binance_client)
        self.ctx.wallet_provider = WalletBalanceProvider(self.ctx.binance_client)

        # Executor LIVE real
        self.ctx.executor_live = ExecutorLive(self.ctx.binance_client)

        # =====================================================
        # DECISION ENGINE
        # =====================================================

        self.ctx.decision_engine = DecisionEngine(
            executor=self.ctx.executor,
            policy_layer=self.ctx.policy,
            snapshot_service=self.ctx.snapshot_service,
            metadata_provider=self.ctx.metadata_provider,
            wallet_provider=self.ctx.wallet_provider,
            symbol="BTCUSDC"
        )

        # =====================================================
        # SLOT CONTROLLER
        # =====================================================

        self.ctx.slot_controller = SlotController(
            slot_ids=[1, 2, 3, 4],
            decision_engine=self.ctx.decision_engine
        )

        # conectar executor ao controller
        self.ctx.slot_controller.executor = self.ctx.executor

        # =====================================================
        # AUTO LOOP
        # =====================================================

        self.ctx.auto_loop = AutoLoop(
            self.ctx.slot_controller,
            interval=4.0
        )

        # =====================================================
        # CONEXÃO STATE CONTROLLER → AUTO LOOP
        # =====================================================

        def system_state_listener(state):

            if state.value == "RUNNING":
                print("\nSTATE → RUNNING")
                self.ctx.auto_loop.start()

            elif state.value == "DRAINING":
                print("\nSTATE → DRAINING")
                self.ctx.auto_loop.stop()

        self.ctx.state_controller.add_listener(system_state_listener)

        self.ctx.core_ready = True

    # --------------------------------------------------------
    # INIT POLICY
    # --------------------------------------------------------

    def init_policy(self):

        self.ctx.policy.enable_safe_mode()
        self.ctx.policy.block_live()
        self.ctx.policy.allow_engine()
        self.ctx.policy.block_integration()
        self.ctx.policy.block_auto()

    # --------------------------------------------------------
    # LIVE TEST
    # --------------------------------------------------------

    def run_live_test_10_usdc(self):

        if self.ctx.mode != "LIVE":
            return {"status": "ABORTED", "reason": "Modo não está LIVE"}

        if os.getenv("LIVE_ENABLED", "false").lower() != "true":
            return {"status": "ABORTED", "reason": "LIVE_ENABLED não está true"}

        try:

            wallet = self.ctx.wallet_provider.get_usdc_balance()

            if wallet["free"] < 10:
                return {"status": "ABORTED", "reason": "Saldo insuficiente"}

            buy_result = self.ctx.executor_live.place_market_buy_quote(
                symbol="BTCUSDC",
                quote_amount=10
            )

            if buy_result.get("status") != "FILLED":
                return {"status": "ERROR", "phase": "BUY", "details": buy_result}

            sell_result = self.ctx.executor_live.place_market_sell_all(
                symbol="BTCUSDC"
            )

            self.ctx.auto_loop.stop()
            self.ctx.policy.block_live()

            return {
                "status": "COMPLETED",
                "buy": buy_result,
                "sell": sell_result
            }

        except Exception as e:
            return {"status": "ERROR", "error": str(e)}

    # --------------------------------------------------------
    # MODE
    # --------------------------------------------------------

    def set_mode(self, mode: str):
        self.ctx.mode = mode

    # --------------------------------------------------------
    # BOOT
    # --------------------------------------------------------

    def boot(self, mode="MOCK"):

        self.init_core()
        self.init_policy()
        self.set_mode(mode)

        self.ctx.booted = True
        return self.ctx

    # --------------------------------------------------------
    # SNAPSHOT DO APP
    # --------------------------------------------------------

    def snapshot(self):

        wallet_data = None
        capital_utilizavel = None

        try:
            wallet_data = self.ctx.wallet_provider.get_usdc_balance()
            capital_utilizavel = wallet_data["free"] * 0.80
        except Exception:
            wallet_data = None
            capital_utilizavel = None

        return {
            "mode": self.ctx.mode,
            "booted": self.ctx.booted,
            "core_ready": self.ctx.core_ready,
            "policy": self.ctx.policy.snapshot(),
            "wallet": wallet_data,
            "capital_utilizavel": capital_utilizavel
        }


APP = AppRunner()