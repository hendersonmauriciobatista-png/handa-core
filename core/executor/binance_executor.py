# =============================================================================
# core/executor/binance_executor.py
# H&A — BINANCE EXECUTOR (SAFE COMPAT + FILTERS + REAL SELL BALANCE)
# =============================================================================

import logging
from decimal import Decimal, ROUND_DOWN
from typing import Optional, Dict, Any

from binance.client import Client

from core.position.position_manager import PositionManager, CloseReason
from core.position.position_tracker import PositionTracker
from core.decision.decision_engine import BuySignal
from core.execution_boundary import is_bound_live_capability
from core.execution.execution_fact import normalize_external_execution

logger = logging.getLogger(__name__)


class BinanceExecutor:

    def __init__(
        self,
        client: Client,
        position_manager: PositionManager,
        tracker: PositionTracker,
        live_capability=None,
    ):
        if not is_bound_live_capability(live_capability, client):
            raise RuntimeError(
                "BinanceExecutor exige capability LIVE vinculada ao client emitido pela fronteira institucional"
            )

        self.client = client
        self.position_manager = position_manager
        self.tracker = tracker
        self.last_balance = 0.0
        self.symbol_filters: Dict[str, Dict[str, float]] = {}

        self._load_exchange_filters()

        logger.info("[Executor] BinanceExecutor iniciado (SAFE COMPAT + FILTERS + REAL SELL BALANCE)")

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _safe_float(self, value, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _pair_to_asset(self, pair: str) -> str:
        if pair.endswith("USDC"):
            return pair[:-4]
        return pair

    def _get_asset_free_balance(self, asset: str) -> float:
        try:
            account = self.client.get_account()

            for balance in account.get("balances", []):
                if balance.get("asset") == asset:
                    return self._safe_float(balance.get("free"))

        except Exception as e:
            logger.error(f"[Executor] Erro ao buscar saldo livre do asset {asset}: {e}")

        return 0.0

    def _load_exchange_filters(self):
        try:
            info = self.client.get_exchange_info()

            filters_map: Dict[str, Dict[str, float]] = {}

            for symbol_info in info.get("symbols", []):
                symbol_name = symbol_info.get("symbol")
                parsed = {
                    "min_qty": 0.0,
                    "max_qty": 0.0,
                    "step_size": 0.0,
                    "min_notional": 0.0,
                }

                for f in symbol_info.get("filters", []):
                    filter_type = f.get("filterType")

                    if filter_type == "LOT_SIZE":
                        parsed["min_qty"] = self._safe_float(f.get("minQty"))
                        parsed["max_qty"] = self._safe_float(f.get("maxQty"))
                        parsed["step_size"] = self._safe_float(f.get("stepSize"))

                    elif filter_type in ("MIN_NOTIONAL", "NOTIONAL"):
                        parsed["min_notional"] = max(
                            self._safe_float(f.get("minNotional")),
                            self._safe_float(f.get("notional")),
                            parsed["min_notional"],
                        )

                filters_map[symbol_name] = parsed

            self.symbol_filters = filters_map
            logger.info("[Executor] Filtros da Binance carregados com sucesso")

        except Exception as e:
            logger.error(f"[Executor] Erro ao carregar filtros da exchange: {e}")
            self.symbol_filters = {}

    def _get_symbol_filter(self, pair: str) -> Dict[str, float]:
        if pair not in self.symbol_filters:
            self._load_exchange_filters()

        return self.symbol_filters.get(
            pair,
            {
                "min_qty": 0.0,
                "max_qty": 0.0,
                "step_size": 0.0,
                "min_notional": 5.0,
            }
        )

    def _round_step_size(self, quantity: float, step_size: float) -> float:
        quantity = self._safe_float(quantity)
        step_size = self._safe_float(step_size)

        if quantity <= 0:
            return 0.0

        if step_size <= 0:
            return quantity

        try:
            qty_dec = Decimal(str(quantity))
            step_dec = Decimal(str(step_size))

            rounded = (qty_dec / step_dec).to_integral_value(rounding=ROUND_DOWN) * step_dec
            return float(rounded)
        except Exception as e:
            logger.warning(f"[Executor] Falha ao arredondar quantity por step_size: {e}")
            return quantity

    def _validate_quantity(self, pair: str, quantity: float, price: float) -> tuple[bool, float, str]:
        filters = self._get_symbol_filter(pair)

        min_qty = self._safe_float(filters.get("min_qty"))
        max_qty = self._safe_float(filters.get("max_qty"))
        step_size = self._safe_float(filters.get("step_size"))
        min_notional = self._safe_float(filters.get("min_notional"), 5.0)

        adjusted_qty = self._round_step_size(quantity, step_size)

        if adjusted_qty <= 0:
            return False, 0.0, f"Quantidade zerada após ajuste de step_size ({step_size})"

        if min_qty > 0 and adjusted_qty < min_qty:
            return False, adjusted_qty, f"Quantidade abaixo do minQty ({adjusted_qty} < {min_qty})"

        if max_qty > 0 and adjusted_qty > max_qty:
            return False, adjusted_qty, f"Quantidade acima do maxQty ({adjusted_qty} > {max_qty})"

        notional = adjusted_qty * price

        if min_notional > 0 and notional < min_notional:
            return False, adjusted_qty, f"Notional abaixo do mínimo ({notional:.8f} < {min_notional})"

        return True, adjusted_qty, "OK"

    def _extract_order_price(self, order: Dict[str, Any]) -> float:
        try:
            fills = order.get("fills", [])
            if fills:
                total_qty = 0.0
                total_cost = 0.0

                for fill in fills:
                    fill_price = self._safe_float(fill.get("price"))
                    fill_qty = self._safe_float(fill.get("qty"))
                    total_qty += fill_qty
                    total_cost += fill_price * fill_qty

                if total_qty > 0:
                    return total_cost / total_qty

            executed_qty = self._safe_float(order.get("executedQty"))
            cummulative_quote_qty = self._safe_float(order.get("cummulativeQuoteQty"))

            if executed_qty > 0 and cummulative_quote_qty > 0:
                return cummulative_quote_qty / executed_qty
        except Exception as e:
            logger.warning(f"[Executor] Falha ao extrair preço da ordem: {e}")

        return 0.0

    def _extract_executed_quantity(self, order: Dict[str, Any], fallback: float = 0.0) -> float:
        try:
            executed_qty = self._safe_float(order.get("executedQty"))
            if executed_qty > 0:
                return executed_qty

            fills = order.get("fills", [])
            if fills:
                total_qty = 0.0
                for fill in fills:
                    total_qty += self._safe_float(fill.get("qty"))
                if total_qty > 0:
                    return total_qty
        except Exception as e:
            logger.warning(f"[Executor] Falha ao extrair quantidade executada: {e}")

        return fallback

    # =========================================================================
    # ACCOUNT / BALANCE
    # =========================================================================

    def get_balance(self, asset: str) -> float:
        try:
            account = self.client.get_account()

            for balance in account.get("balances", []):
                if balance.get("asset") == asset:
                    self.last_balance = self._safe_float(balance.get("free"))
                    return self.last_balance

        except Exception as e:
            logger.error(f"[Executor] Erro ao buscar saldo {asset}: {e}")

        return self.last_balance

    def get_account_balance(self, asset: str) -> float:
        return self.get_balance(asset)

    def get_asset_balance(self, asset: str) -> float:
        return self.get_balance(asset)

    # =========================================================================
    # MARKET DATA / FILTERS
    # =========================================================================

    def get_current_price(self, pair: str) -> Optional[float]:
        try:
            ticker = self.client.get_symbol_ticker(symbol=pair)
            return self._safe_float(ticker.get("price"))
        except Exception as e:
            logger.error(f"[Executor] Erro ao buscar preço atual de {pair}: {e}")
            return None

    def get_min_notional(self, pair: str) -> float:
        filters = self._get_symbol_filter(pair)
        value = self._safe_float(filters.get("min_notional"), 5.0)
        return value if value > 0 else 5.0

    def get_step_size(self, pair: str) -> float:
        filters = self._get_symbol_filter(pair)
        return self._safe_float(filters.get("step_size"))

    def get_min_qty(self, pair: str) -> float:
        filters = self._get_symbol_filter(pair)
        return self._safe_float(filters.get("min_qty"))

    # =========================================================================
    # BUY
    # =========================================================================

    def execute_buy(self, signal: BuySignal):

        pair = signal.pair

        if signal.entry_price is None or signal.entry_price <= 0:
            logger.error(f"[Executor] BUY cancelado — entry_price inválido para {pair}")
            return normalize_external_execution(
                {"symbol": pair, "side": "BUY", "rawSourceReference": "local-validation"}
            )

        allocated_usdc = self._safe_float(signal.allocated_usdc)

        if allocated_usdc <= 0:
            logger.error(f"[Executor] BUY cancelado — allocated_usdc inválido para {pair}")
            return normalize_external_execution(
                {"symbol": pair, "side": "BUY", "rawSourceReference": "local-validation"}
            )

        quantity_estimada = allocated_usdc / signal.entry_price

        ok, quantity_ajustada, reason = self._validate_quantity(
            pair=pair,
            quantity=quantity_estimada,
            price=signal.entry_price,
        )

        logger.info(
            f"[Executor] BUY | {pair} | allocated={allocated_usdc:.8f} | "
            f"entry_ref={signal.entry_price:.8f} | "
            f"qty_est={quantity_estimada:.8f} | qty_adj={quantity_ajustada:.8f}"
        )

        if not ok:
            logger.error(f"[Executor] BUY cancelado | {pair} | {reason}")
            return normalize_external_execution(
                {"symbol": pair, "side": "BUY", "rawSourceReference": "exchange-filter"}
            )

        try:
            order = self.client.order_market_buy(
                symbol=pair,
                quantity=quantity_ajustada
            )

            executed_price = self._extract_order_price(order)
            executed_quantity = self._extract_executed_quantity(order, fallback=quantity_ajustada)
            if executed_price <= 0:
                logger.error(f"[Executor] BUY com preço executado inválido em {pair}")

            logger.info(
                f"[Executor] ✅ BUY EXECUTADO | {pair} | "
                f"price={executed_price:.8f} | qty={executed_quantity:.8f}"
            )
            return normalize_external_execution(
                order,
                symbol=pair,
                side="BUY",
                averagePrice=executed_price,
            )

        except Exception as e:
            logger.error(f"[Executor] ❌ ERRO BUY | {pair} | {e}")
            return normalize_external_execution(
                {
                    "symbol": pair,
                    "side": "BUY",
                    "ambiguous_response": True,
                    "rawSourceReference": "binance-buy-exception",
                }
            )

    # =========================================================================
    # SELL
    # =========================================================================

    def execute_sell(
        self,
        pair: str,
        reason: CloseReason,
    ):

        pos = self.position_manager.get_position(pair)

        if not pos:
            logger.warning(f"[Executor] SELL ignorado — sem posição: {pair}")
            return normalize_external_execution(
                {"symbol": pair, "side": "SELL", "rawSourceReference": "no-local-position"}
            )

        current_price = self.get_current_price(pair)

        if current_price is None or current_price <= 0:
            logger.error(f"[Executor] SELL cancelado — preço atual inválido em {pair}")
            return normalize_external_execution(
                {"symbol": pair, "side": "SELL", "rawSourceReference": "invalid-market-price"}
            )

        asset = self._pair_to_asset(pair)
        free_balance_real = self._get_asset_free_balance(asset)
        quantity_local = self._safe_float(pos.quantity)

        if quantity_local <= 0:
            logger.error(f"[Executor] SELL cancelado — quantidade local inválida em {pair}: {quantity_local}")
            return normalize_external_execution(
                {"symbol": pair, "side": "SELL", "rawSourceReference": "invalid-local-quantity"}
            )

        if free_balance_real <= 0:
            logger.error(f"[Executor] SELL cancelado — saldo livre real zerado em {pair} ({asset})")
            return normalize_external_execution(
                {"symbol": pair, "side": "SELL", "rawSourceReference": "empty-exchange-balance"}
            )

        quantity_to_sell = min(quantity_local, free_balance_real)

        ok, quantity_ajustada, reason_qty = self._validate_quantity(
            pair=pair,
            quantity=quantity_to_sell,
            price=current_price,
        )

        logger.info(
            f"[Executor] SELL | {pair} | "
            f"qty_local={quantity_local:.8f} | "
            f"qty_free={free_balance_real:.8f} | "
            f"qty_used={quantity_to_sell:.8f} | "
            f"qty_adj={quantity_ajustada:.8f}"
        )

        if not ok:
            logger.error(f"[Executor] SELL cancelado | {pair} | {reason_qty}")
            return normalize_external_execution(
                {"symbol": pair, "side": "SELL", "rawSourceReference": "exchange-filter"}
            )

        try:
            order = self.client.order_market_sell(
                symbol=pair,
                quantity=quantity_ajustada
            )

            executed_price = self._extract_order_price(order)
            executed_quantity = self._extract_executed_quantity(order, fallback=quantity_ajustada)

            if executed_price <= 0:
                logger.error(f"[Executor] ❌ SELL com preço inválido | {pair}")
            return normalize_external_execution(
                order,
                symbol=pair,
                side="SELL",
                averagePrice=executed_price,
            )

        except Exception as e:
            logger.error(f"[Executor] ❌ SELL FALHOU | {pair} | {e}")
            return normalize_external_execution(
                {
                    "symbol": pair,
                    "side": "SELL",
                    "ambiguous_response": True,
                    "rawSourceReference": "binance-sell-exception",
                }
            )
