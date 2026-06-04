# ============================================================
# executor/mock_executor.py
# MockExecutor MULTI-SLOT compatível com SlotController SAFE COMPAT
# ============================================================

from types import SimpleNamespace
import json
import os
from datetime import datetime

try:
    from core.persistence.postgres_state_repository import PostgresStateRepository
except Exception as e:
    print(f"[PERSISTENCE IMPORT ERROR] {e}")
    PostgresStateRepository = None

try:
    from core.executor.live_shadow import LiveShadowSimulator
except Exception:
    LiveShadowSimulator = None


def format_buy_telegram(pair: str, entry: float, capital: float) -> str:
    return f"BUY | {pair}\n" f"{entry:.8f} | {capital:.2f} USDC"


class MockExecutor:
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

        # debita saldo
        self.balance_usdc -= allocated_usdc
        self._save_state()

        # registra posição local
        self.positions[pair] = {
            "pair": pair,
            "entry_price": entry_price,
            "quantity": quantity,
            "allocated_usdc": allocated_usdc,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }

        # tracker legado
        if self.tracker:
            try:
                self.tracker.open_position(pair, entry_price, quantity)
            except Exception:
                pass

        # position manager
        if self.position_manager:
            try:
                self.position_manager.open_position(
                    pair=pair,
                    entry_price=entry_price,
                    capital_invested=allocated_usdc,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    quantity=quantity,
                )
            except Exception:
                pass

        if self.notifier:
            msg = format_buy_telegram(
                pair=pair,
                entry=entry_price,
                capital=allocated_usdc,
            )
            print(f"[DEBUG TELEGRAM BUY] enviando BUY de {pair}")
            self.notifier.send(msg)
            print(f"[DEBUG TELEGRAM BUY] BUY enviado com sucesso para {pair}")
        else:
            print(f"[DEBUG TELEGRAM BUY] notifier está None para {pair}")

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

        return SimpleNamespace(
            pair=pair,
            entry_price=entry_price,
            quantity=quantity,
            allocated_usdc=allocated_usdc,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status="FILLED",
        )

    # =================================================
    # EXECUTE SELL
    # =================================================
    def execute_sell(self, pair, reason=None):

        pair = str(pair).strip().upper()

        pos = self.positions.get(pair)
        if not pos:
            return None

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

        # devolve saldo
        self.balance_usdc += usdc_received
        self._save_state()

        # fecha tracker
        if self.tracker:
            try:
                self.tracker.close_position()
            except Exception:
                pass

        # PositionManager é fechado pelo SlotController após SELL executado.
        # O executor apenas remove sua posição local mock e retorna o resultado.
        del self.positions[pair]

        return SimpleNamespace(
            pair=pair,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            net_pnl_usdc=net_pnl_usdc,
            reason=reason,
            status="FILLED",
        )

    # =================================================
    # STATE PERSISTENCE
    # =================================================
    def _load_state(self):
        try:
            if self.state_repo is not None:
                data = self.state_repo.load_system_state("mock_executor_state")

                if data:
                    self.balance_usdc = float(
                        data.get("current_balance", self.balance_usdc)
                    )
                    self.initial_balance = float(
                        data.get("initial_balance", self.initial_balance)
                    )
                    self.positions = data.get("positions", {}) or {}

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

                self.balance_usdc = float(
                    data.get("current_balance", self.balance_usdc)
                )
                self.initial_balance = float(
                    data.get("initial_balance", self.initial_balance)
                )

                print(f"[MOCK STATE JSON] carregado | balance={self.balance_usdc:.4f}")
                return True

            self._save_state()
            return False

        except Exception as e:
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
                return

            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            print(f"[MOCK STATE JSON] salvo | balance={self.balance_usdc:.4f}")

        except Exception as e:
            print(f"[MOCK STATE ERROR - SAVE] {e}")

    # =================================================
    # HARD BLOCKS
    # =================================================
    def place_market_buy(self, *args, **kwargs):
        raise RuntimeError("MockExecutor: compra real bloqueada em MOCK")

    def place_market_sell_all(self, *args, **kwargs):
        raise RuntimeError("MockExecutor: venda real bloqueada em MOCK")

    def create_order(self, *args, **kwargs):
        raise RuntimeError("MockExecutor: create_order bloqueado em MOCK")
