from datetime import datetime
from typing import Dict, Any
import json
import urllib.request

from core.logger import HALogger


class ExecutorLiveReal:
    """
    Executor LIVE REAL — SHADOW MODE AUDITÁVEL
    Passo 3: Preço real via Binance Spot (ticker público).
    - Sem API key
    - Sem envio de ordens
    - Apenas leitura de preço
    """

    # ===============================
    # Parâmetros de Trade
    # ===============================
    
    SIDE = "BUY"
    ORDER_TYPE = "MARKET"     # MARKET | LIMIT
    TIME_IN_FORCE = "IOC"

    # ===============================
    # Regras de Sizing
    # ===============================
    RISK_PERCENT = 0.05
    MIN_USDC = 20.0
    MAX_USDC = 200.0
    ROUND_DECIMALS = 2

    # ===============================
    # Validação de preço
    # ===============================
    MAX_DEVIATION = 0.003     # 0,3%

    def __init__(self):
        self.exchange = "BINANCE_SPOT"
        self.quote_asset = "USDC"
        self.shadow_mode = True

    # ======================================================
    # Contrato padrão
    # ======================================================
    def run_trade_cycle(self, symbol: str) -> Dict[str, Any]:

        timestamp = datetime.utcnow().isoformat()

        HALogger.warn(
            "SHADOW MODE — auditoria ativa (nenhuma ordem será enviada)"
        )

        balance_usdc = self._get_balance_usdc()
        amount_usdc = self._calculate_dynamic_size(balance_usdc)

        market_price = self._fetch_market_price(symbol)

        trade_plan = self._build_trade_plan(symbol, amount_usdc, market_price)


        self._audit_trade_plan(trade_plan, balance_usdc)
        execution = self._execute_shadow(trade_plan)
        self._audit_execution(execution)

        return {
            "mode": "LIVE_REAL",
            "status": "shadow",
            "exchange": self.exchange,
            "quote": self.quote_asset,
            "balance_usdc": balance_usdc,
            "market_price": market_price,
            "trade_plan": trade_plan,
            "execution": execution,
            "timestamp": timestamp
        }

    # ======================================================
    # Saldo (placeholder)
    # ======================================================
    def _get_balance_usdc(self) -> float:
        simulated_balance = 1000.0
        HALogger.info(f"SALDO (SHADOW): {simulated_balance} USDC")
        return simulated_balance

    # ======================================================
    # Sizing dinâmico
    # ======================================================
    def _calculate_dynamic_size(self, balance_usdc: float) -> float:
        raw_size = balance_usdc * self.RISK_PERCENT
        size = max(self.MIN_USDC, min(raw_size, self.MAX_USDC))
        size = round(size, self.ROUND_DECIMALS)

        HALogger.info(
            "SIZING DINÂMICO — "
            f"risco={self.RISK_PERCENT:.0%} | "
            f"raw={raw_size:.2f} | "
            f"final={size:.2f}"
        )

        if size <= 0:
            raise ValueError("SIZING FALHOU — valor inválido")

        return size

    # ======================================================
    # Preço real (Binance Spot - endpoint público)
    # ======================================================
    def _fetch_market_price(self, symbol: str) -> float:
        url = (
            "https://api.binance.com/api/v3/ticker/price"
            f"?symbol={symbol}"
        )

        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                price = float(data["price"])
                HALogger.info(
                    f"PREÇO MERCADO (SPOT): {symbol} = {price}"
                )
                return price
        except Exception as e:
            raise RuntimeError(
                f"FALHA AO OBTER PREÇO DE MERCADO: {e}"
            )

    # ======================================================
    # Construção do plano
    # ======================================================
    def _build_trade_plan(
    self, symbol: str, amount_usdc: float, market_price: float
) -> Dict[str, Any]:

        return {
            "symbol": symbol,
            "side": self.SIDE,
            "order_type": self.ORDER_TYPE,
            "amount_usdc": amount_usdc,
            "market_price": market_price,
            "time_in_force": self.TIME_IN_FORCE
        }

    # ======================================================
    # Auditoria do plano
    # ======================================================
    def _audit_trade_plan(
        self, plan: Dict[str, Any], balance_usdc: float
    ) -> None:
        HALogger.info("AUDITORIA — PLANO DE TRADE")

        for k, v in plan.items():
            HALogger.info(f"  {k}: {v}")

        if plan["amount_usdc"] > balance_usdc:
            raise ValueError(
                "AUDITORIA FALHOU — amount_usdc maior que saldo"
            )

        if plan["order_type"] not in ("MARKET", "LIMIT"):
            raise ValueError(
                "AUDITORIA FALHOU — order_type inválido"
            )

    # ======================================================
    # Execução SHADOW
    # ======================================================
    def _execute_shadow(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "sent": False,
            "reason": "SHADOW MODE ativo — envio bloqueado",
            "order_payload": {
                "symbol": plan["symbol"],
                "side": plan["side"],
                "type": plan["order_type"],
                "quoteOrderQty": plan["amount_usdc"],
                "market_price": plan["market_price"]
            }
        }

    # ======================================================
    # Auditoria da execução
    # ======================================================
    def _audit_execution(self, execution: Dict[str, Any]) -> None:
        HALogger.info("AUDITORIA — EXECUÇÃO (SHADOW)")

        for k, v in execution.items():
            HALogger.info(f"  {k}: {v}")
