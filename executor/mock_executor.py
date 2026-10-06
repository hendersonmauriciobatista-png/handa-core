# ============================================================
# executor/mock_executor.py
# MockExecutor MULTI-SLOT compatível com SlotController SAFE COMPAT
# ============================================================

from types import SimpleNamespace
import copy
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
    STATE_FORMAT_VERSION = 2
    LEGACY_STATE_FORMAT_VERSION = 1

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
        # client_order_id -> durable simulated venue order evidence
        self.orders = {}
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
    @staticmethod
    def _required_client_order_id(client_order_id):
        if not isinstance(client_order_id, str) or not client_order_id.strip():
            raise ValueError("MockExecutor: client_order_id must be non-empty")
        return client_order_id.strip()

    @staticmethod
    def _number_text(value):
        return format(float(value), ".15g")

    def _submission_semantics(self, signal, pair):
        return {
            "symbol": pair,
            "side": "BUY",
            "entry_price": self._number_text(signal.entry_price),
            "allocated_usdc": self._number_text(signal.allocated_usdc),
            "stop_loss": self._number_text(signal.stop_loss),
            "take_profit": self._number_text(signal.take_profit),
        }

    @staticmethod
    def _order_evidence(order):
        return copy.deepcopy(order)

    def _normalized_order(self, order):
        return normalize_external_execution(self._order_evidence(order))

    def get_order_by_client_order_id(self, client_order_id):
        """Read-only lookup of durable simulated venue evidence."""

        client_order_id = self._required_client_order_id(client_order_id)
        order = self.orders.get(client_order_id)
        return self._order_evidence(order) if order is not None else None

    def get_order_by_external_order_id(self, external_order_id):
        """Read-only lookup of durable simulated venue evidence."""

        if not isinstance(external_order_id, str) or not external_order_id.strip():
            raise ValueError("MockExecutor: external_order_id must be non-empty")
        for order in self.orders.values():
            if order.get("external_order_id") == external_order_id.strip():
                return self._order_evidence(order)
        return None

    def execute_buy(self, signal, *, client_order_id=None):

        if not hasattr(self, "orders"):
            self.orders = {}

        pair = str(signal.pair).strip().upper()
        entry_price = float(signal.entry_price)
        allocated_usdc = float(signal.allocated_usdc)
        stop_loss = float(signal.stop_loss)
        take_profit = float(signal.take_profit)

        if client_order_id is not None:
            client_order_id = self._required_client_order_id(client_order_id)
            semantics = self._submission_semantics(signal, pair)
            existing = self.orders.get(client_order_id)
            if existing is not None:
                if existing.get("request") != semantics:
                    raise RuntimeError(
                        "MockExecutor: conflicting client_order_id reuse rejected"
                    )
                return self._normalized_order(existing)

        if pair in self.positions:
            raise RuntimeError(f"MockExecutor: posição já aberta para {pair}")

        if entry_price <= 0:
            raise RuntimeError("MockExecutor: entry_price inválido")

        if allocated_usdc <= 0:
            raise RuntimeError("MockExecutor: allocated_usdc inválido")

        if allocated_usdc > self.balance_usdc:
            raise RuntimeError("MockExecutor: saldo insuficiente")

        quantity = allocated_usdc / entry_price

        previous_positions = copy.deepcopy(self.positions)
        previous_orders = copy.deepcopy(self.orders)
        previous_balance = self.balance_usdc

        position = {
            "pair": pair,
            "entry_price": entry_price,
            "quantity": quantity,
            "allocated_usdc": allocated_usdc,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position_id": str(uuid.uuid4()),
            "opened_at": datetime.utcnow().isoformat(),
        }
        self.positions[pair] = position
        self.balance_usdc -= allocated_usdc

        order = None
        if client_order_id is not None:
            external_order_id = f"mock-order-{uuid.uuid4().hex}"
            trade_id = f"mock-fill-{uuid.uuid4().hex}"
            order = {
                "client_order_id": client_order_id,
                "external_order_id": external_order_id,
                "symbol": pair,
                "side": "BUY",
                "status": "FILLED",
                "executedQty": quantity,
                "cummulativeQuoteQty": allocated_usdc,
                "fills": [
                    {
                        "tradeId": trade_id,
                        "price": entry_price,
                        "qty": quantity,
                        "quoteQty": allocated_usdc,
                    }
                ],
                "singleFill": True,
                "fullExtentProven": True,
                "rawSourceReference": "mock-exchange-buy",
                "exchangeTimestamp": position["opened_at"],
                "request": self._submission_semantics(signal, pair),
            }
            self.orders[client_order_id] = order

        if self._save_state() is False:
            self.balance_usdc = previous_balance
            self.positions = previous_positions
            self.orders = previous_orders
            raise RuntimeError("MockExecutor: falha ao persistir BUY")

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

        if order is not None:
            return self._normalized_order(order)

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
            self.orders = {}
        elif version == self.LEGACY_STATE_FORMAT_VERSION:
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
                        "versioned mock position missing fields: "
                        + ", ".join(missing)
                    )
                datetime.fromisoformat(str(record["opened_at"]).replace("Z", "+00:00"))
            self.state_format_version = version
            self.state_classification = "CURRENT_VERSIONED_RECORD"
            self.orders = {}
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

            orders = data.get("orders", {}) or {}
            if not isinstance(orders, dict):
                raise ValueError("mock state orders must be an object")
            required_order_fields = {
                "client_order_id",
                "external_order_id",
                "symbol",
                "side",
                "status",
                "executedQty",
                "cummulativeQuoteQty",
                "fills",
                "singleFill",
                "fullExtentProven",
                "rawSourceReference",
                "exchangeTimestamp",
                "request",
            }
            normalized_orders = {}
            for key, value in orders.items():
                if not isinstance(value, dict):
                    raise ValueError("mock state order must be an object")
                missing = sorted(required_order_fields.difference(value))
                if missing:
                    raise ValueError(
                        "versioned mock order missing fields: "
                        + ", ".join(missing)
                    )
                order_client_id = self._required_client_order_id(
                    value["client_order_id"]
                )
                if str(key) != order_client_id:
                    raise ValueError("mock state order key must match client_order_id")
                self._required_client_order_id(value["external_order_id"])
                if value["side"] != "BUY" or value["status"] != "FILLED":
                    raise ValueError("mock state order has unsupported semantics")
                if not isinstance(value["fills"], list) or len(value["fills"]) != 1:
                    raise ValueError("mock state governed order requires one fill")
                fill = value["fills"][0]
                trade_id = fill.get("tradeId") if isinstance(fill, dict) else None
                if not isinstance(trade_id, str) or not trade_id.strip():
                    raise ValueError("mock state governed order requires tradeId")
                normalized_orders[order_client_id] = copy.deepcopy(value)
            self.orders = normalized_orders

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

            state_version = (
                self.STATE_FORMAT_VERSION
                if self.orders
                else (
                    None
                    if self.state_classification == "LEGACY_UNVERSIONED_RECORD"
                    else (
                        self.state_format_version
                        if self.state_format_version in (1, self.STATE_FORMAT_VERSION)
                        else self.LEGACY_STATE_FORMAT_VERSION
                    )
                )
            )
            data = {
                "initial_balance": self.initial_balance,
                "current_balance": self.balance_usdc,
                "positions": self.positions,
                "pnl_total": round(pnl_total, 6),
                "pnl_pct": round(pnl_pct, 4),
                "last_update": datetime.utcnow().isoformat(),
            }
            if state_version is not None:
                data["state_format_version"] = state_version
            if state_version == self.STATE_FORMAT_VERSION:
                data["orders"] = copy.deepcopy(self.orders)

            if self.state_repo is not None:
                self.state_repo.save_system_state("mock_executor_state", data)
                self.state_format_version = state_version
                print(f"[MOCK STATE DB] salvo | balance={self.balance_usdc:.4f}")
                return True

            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

            temp_state_file = f"{self.state_file}.tmp"
            with open(temp_state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_state_file, self.state_file)
            self.state_format_version = state_version

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
