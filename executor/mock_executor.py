# ============================================================
# executor/mock_executor.py
# MockExecutor MULTI-SLOT compatível com SlotController SAFE COMPAT
# ============================================================

from types import SimpleNamespace
import json
import os
import uuid
from datetime import datetime
from core.execution.execution_fact import normalize_external_execution

try:
    from core.persistence.postgres_state_repository import PostgresStateRepository
except Exception as e:
    print(f"[PERSISTENCE IMPORT ERROR] {e}")
    PostgresStateRepository = None

try:
    from core.executor.live_shadow import LiveShadowSimulator
except Exception:
    LiveShadowSimulator = None


class MockExecutor:
    STATE_FORMAT_VERSION = 1

    """
    Executor MOCK compatível com múltiplos slots.
    Não envia ordens reais.
    Mantém posições independentes por par.
    """

    def __init__(
        self,
        client=None,
        position_manager=None,
        tracker=None,
        initial_balance: float = 1000.0,
        notifier=None,
    ):
        self.client = client
        self.position_manager = position_manager
        self.tracker = tracker
        self.state_file = "/data/mock_state.json"
        self.notifier = notifier

        # valor inicial provisório
        self.balance_usdc = float(initial_balance)
        self.initial_balance = float(initial_balance)
        self.state_format_version = None
        self.state_classification = "NO_STATE"
        self.state_diagnostics = []

        # =========================================
        # POSTGRES PERSISTENCE
        # =========================================
        self.state_repo = None

        if PostgresStateRepository is not None:
            try:
                self.state_repo = PostgresStateRepository()
                self.state_repo.initialize()
                print("[PERSISTENCE] PostgreSQL ativo")
            except Exception as e:
                print(f"[PERSISTENCE] fallback para JSON | erro={e}")
                self.state_repo = None
        else:
            print("[PERSISTENCE] PostgreSQL indisponível")

        # pair -> dados da posição
        self.positions = {}
        self.live_shadow = (
            LiveShadowSimulator() if LiveShadowSimulator is not None else None
        )

        # tenta carregar estado salvo
        loaded = self._load_state()

        # se não carregou nada, mantém initial_balance
        if not loaded:
            print(
                "[MOCK STATE] nenhum estado anterior encontrado, usando saldo inicial"
            )

        print("MockExecutor iniciado")

    # =================================================
    # BALANCE
    # =================================================
    def get_balance(self, asset="USDC"):
        if asset != "USDC":
            return 0.0
        return self.balance_usdc

    # =================================================
    # PREÇO ATUAL
    # =================================================
    def get_current_price(self, symbol: str) -> float:
        if not self.client:
            raise RuntimeError("MockExecutor: client não disponível para preço")

        price_data = self.client.get_symbol_ticker(symbol=symbol)
        price = float(price_data["price"])

        if price <= 0:
            raise RuntimeError(f"MockExecutor: preço inválido para {symbol}")

        return price

    # =================================================
    # HELPERS
    # =================================================
    def has_open_position(self, pair: str = None) -> bool:
        if pair is None:
            return len(self.positions) > 0
        return pair in self.positions

    def get_open_position(self, pair: str):
        return self.positions.get(pair)

    # =================================================
    # EXECUTE BUY
    # =================================================
    def execute_buy(self, signal):

        pair = str(signal.pair).strip().upper()
        entry_price = float(signal.entry_price)
        allocated_usdc = float(signal.allocated_usdc)
        stop_loss = float(signal.stop_loss)
        take_profit = float(signal.take_profit)

        if pair in self.positions:
            raise RuntimeError(f"MockExecutor: posição já aberta para {pair}")

        if entry_price <= 0:
            raise RuntimeError("MockExecutor: entry_price inválido")

        if allocated_usdc <= 0:
            raise RuntimeError("MockExecutor: allocated_usdc inválido")

        if allocated_usdc > self.balance_usdc:
            raise RuntimeError("MockExecutor: saldo insuficiente")

        quantity = allocated_usdc / entry_price

        # registra posição local antes de persistir o novo estado
        self.positions[pair] = {
            "pair": pair,
            "entry_price": entry_price,
            "quantity": quantity,
            "allocated_usdc": allocated_usdc,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position_id": str(uuid.uuid4()),
            "opened_at": datetime.utcnow().isoformat(),
        }
        self.balance_usdc -= allocated_usdc
        self._save_state()

        if self.live_shadow:
            try:
                self.live_shadow.record_buy(
                    symbol=pair,
                    signal_price=entry_price,
                    allocated_usdc=allocated_usdc,
                    quantity=quantity,
                )
            except Exception as e:
                print(f"[SHADOW BUY ERROR] {e}")

        return normalize_external_execution(
            {
                "symbol": pair,
                "side": "BUY",
                "status": "FILLED",
                "executedQty": quantity,
                "cummulativeQuoteQty": allocated_usdc,
                "fullExtentProven": True,
                "rawSourceReference": "mock-exchange-buy",
            }
        )

    # =================================================
    # EXECUTE SELL
    # =================================================
    def execute_sell(self, pair, reason=None):

        pair = str(pair).strip().upper()

        pos = self.positions.get(pair)
        if not pos:
            return normalize_external_execution(
                {"symbol": pair, "side": "SELL", "rawSourceReference": "no-simulated-position"}
            )

        exit_price = self.get_current_price(pair)

        entry_price = float(pos["entry_price"])
        quantity = float(pos["quantity"])
        allocated_usdc = float(pos["allocated_usdc"])

        usdc_received = quantity * exit_price
        net_pnl_usdc = usdc_received - allocated_usdc

        if self.live_shadow:
            try:
                self.live_shadow.record_sell(
                    symbol=pair,
                    signal_entry_price=entry_price,
                    signal_exit_price=exit_price,
                    quantity=quantity,
                    mock_net_pnl_usdc=net_pnl_usdc,
                )
            except Exception as e:
                print(f"[SHADOW SELL ERROR] {e}")

        # devolve saldo e remove a posição antes de persistir o estado final
        previous_balance = self.balance_usdc
        previous_position = dict(pos)
        self.balance_usdc += usdc_received
        del self.positions[pair]

        if not self._save_state():
            self.balance_usdc = previous_balance
            self.positions[pair] = previous_position
            raise RuntimeError("MockExecutor: falha ao persistir SELL")

        return normalize_external_execution(
            {
                "symbol": pair,
                "side": "SELL",
                "status": "FILLED",
                "executedQty": quantity,
                "cummulativeQuoteQty": usdc_received,
                "fullExtentProven": True,
                "rawSourceReference": "mock-exchange-sell",
            }
        )

    # =================================================
    # STATE PERSISTENCE
    # =================================================
    def _apply_loaded_state(self, data):
        if not isinstance(data, dict):
            raise ValueError("mock state must be an object")

        positions = data.get("positions", {}) or {}
        if not isinstance(positions, dict):
            raise ValueError("mock state positions must be an object")

        self.balance_usdc = float(data.get("current_balance", self.balance_usdc))
        self.initial_balance = float(data.get("initial_balance", self.initial_balance))

        normalized_positions = {}
        for key, value in positions.items():
            if not isinstance(value, dict):
                raise ValueError("mock state position must be an object")
            pair = str(value.get("pair", key)).strip().upper()
            if not pair:
                raise ValueError("mock state position pair is required")
            record = dict(value)
            record["pair"] = pair
            normalized_positions[pair] = record

        version = data.get("state_format_version")
        if version is None:
            self.state_format_version = None
            self.state_classification = "LEGACY_UNVERSIONED_RECORD"
        elif version != self.STATE_FORMAT_VERSION:
            raise ValueError(f"unsupported mock state version: {version!r}")
        else:
            required_fields = {
                "pair",
                "entry_price",
                "quantity",
                "allocated_usdc",
                "stop_loss",
                "take_profit",
                "position_id",
                "opened_at",
            }
            for record in normalized_positions.values():
                missing = sorted(required_fields.difference(record))
                if missing:
                    raise ValueError(
                        "versioned mock position missing fields: " + ", ".join(missing)
                    )
                datetime.fromisoformat(str(record["opened_at"]).replace("Z", "+00:00"))
            self.state_format_version = self.STATE_FORMAT_VERSION
            self.state_classification = "CURRENT_VERSIONED_RECORD"

        self.positions = normalized_positions

    def _load_state(self):
        try:
            if self.state_repo is not None:
                data = self.state_repo.load_system_state("mock_executor_state")

                if data:
                    self._apply_loaded_state(data)

                    print(
                        f"[MOCK STATE DB] carregado | balance={self.balance_usdc:.4f}"
                    )
                    return True

                print("[MOCK STATE DB] nenhum estado encontrado — criando inicial")
                self._save_state()
                return False

            if os.path.exists(self.state_file):
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self._apply_loaded_state(data)

                print(f"[MOCK STATE JSON] carregado | balance={self.balance_usdc:.4f}")
                return True

            self._save_state()
            return False

        except Exception as e:
            self.positions = {}
            self.state_classification = "MALFORMED_RECORD"
            self.state_diagnostics = [str(e)]
            print(f"[MOCK STATE ERROR - LOAD] {e}")
            return False

    def _save_state(self):
        try:
            pnl_total = self.balance_usdc - self.initial_balance
            pnl_pct = (
                (pnl_total / self.initial_balance) * 100
                if self.initial_balance > 0
                else 0.0
            )

            data = {
                "state_format_version": self.STATE_FORMAT_VERSION,
                "initial_balance": self.initial_balance,
                "current_balance": self.balance_usdc,
                "positions": self.positions,
                "pnl_total": round(pnl_total, 6),
                "pnl_pct": round(pnl_pct, 4),
                "last_update": datetime.utcnow().isoformat(),
            }

            if self.state_repo is not None:
                self.state_repo.save_system_state("mock_executor_state", data)
                print(f"[MOCK STATE DB] salvo | balance={self.balance_usdc:.4f}")
                return True

            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

            temp_state_file = f"{self.state_file}.tmp"
            with open(temp_state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_state_file, self.state_file)

            print(f"[MOCK STATE JSON] salvo | balance={self.balance_usdc:.4f}")
            return True

        except Exception as e:
            print(f"[MOCK STATE ERROR - SAVE] {e}")
            return False

    # =================================================
    # HARD BLOCKS
    # =================================================
    def place_market_buy(self, *args, **kwargs):
        raise RuntimeError("MockExecutor: compra real bloqueada em MOCK")

    def place_market_sell_all(self, *args, **kwargs):
        raise RuntimeError("MockExecutor: venda real bloqueada em MOCK")

    def create_order(self, *args, **kwargs):
        raise RuntimeError("MockExecutor: create_order bloqueado em MOCK")
