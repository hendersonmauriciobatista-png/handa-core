# =============================================================================
# core/risk/risk_manager.py
# H&A — RISK MANAGER (PRO + DYNAMIC POLICY INTEGRATION)
# =============================================================================

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# RESULTADO
# =============================================================================

@dataclass
class RiskEvaluation:
    approved: bool
    reason: str
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    risk_reward_ratio: float = 0.0
    expected_profit_pct: float = 0.0


# =============================================================================
# RISK MANAGER
# =============================================================================

class RiskManager:

    def __init__(self, executor: Optional[object] = None):
        self.executor = executor
        self.max_trades = 4
        self.risk_per_trade = 0.10

        logger.info("[RiskManager] Versão PRO + Dynamic inicializada")

    # -------------------------------------------------------------------------
    # COMPATIBILIDADE
    # -------------------------------------------------------------------------

    def get_available_capital(self) -> float:
        try:
            if self.executor and hasattr(self.executor, "get_balance"):
                return float(self.executor.get_balance("USDC"))
        except Exception as e:
            logger.warning(f"[RiskManager] erro ao consultar capital disponível: {e}")

        return 0.0

    def calculate_trade_capital(self) -> float:
        balance = self.get_available_capital()
        return balance * self.risk_per_trade

    def can_open_trade(self, active_slots: int) -> bool:
        if active_slots >= self.max_trades:
            logger.info("[RiskManager] máximo de trades ativos atingido")
            return False

        available = self.get_available_capital()

        if self.executor is not None and available <= 0:
            logger.info("[RiskManager] sem capital disponível")
            return False

        return True

    # -------------------------------------------------------------------------
    # ENTRY
    # -------------------------------------------------------------------------

    def evaluate_entry(
        self,
        pair: str,
        entry_price: float,
        capital_to_use: float,
        expected_profit_pct: float,
        atr: float,
        min_rr: float = 1.20,
        stop_loss_pct: float = 0.0035,
    ):

        pair = str(pair).strip().upper()

        # -----------------------------------------------------
        # 1. VALIDAÇÕES BÁSICAS
        # -----------------------------------------------------
        if entry_price <= 0:
            return RiskEvaluation(
                approved=False,
                reason="Preço de entrada inválido",
            )

        if atr <= 0:
            return RiskEvaluation(
                approved=False,
                reason="ATR inválido",
            )

        if capital_to_use < 5:
            return RiskEvaluation(
                approved=False,
                reason="Capital muito baixo",
            )

        # -----------------------------------------------------
        # 2. FILTRO DE LUCRO REAL
        # -----------------------------------------------------
        min_edge = 0.0040
        max_edge = 0.0100

        if expected_profit_pct < min_edge:
            return RiskEvaluation(
                approved=False,
                reason=f"Lucro baixo demais ({expected_profit_pct:.4%})",
            )

        expected_profit_pct = min(float(expected_profit_pct), max_edge)

        # -----------------------------------------------------
        # 3. STOP DINÂMICO COM GUARDRAIL
        # -----------------------------------------------------
        atr_pct = atr / entry_price if entry_price > 0 else 0.0

        stop_loss_pct = float(stop_loss_pct)
        stop_loss_pct = max(0.0030, min(stop_loss_pct, 0.0060))

        # ajuste leve por volatilidade, sem destruir a política recebida
        if atr_pct >= 0.0060:
            stop_loss_pct = min(stop_loss_pct + 0.0003, 0.0060)
        elif atr_pct >= 0.0030:
            stop_loss_pct = min(stop_loss_pct + 0.0001, 0.0060)

        # -----------------------------------------------------
        # 4. TAKE PROFIT DINÂMICO
        # -----------------------------------------------------
        take_profit_pct = float(expected_profit_pct)

        # -----------------------------------------------------
        # 5. PREÇOS
        # -----------------------------------------------------
        stop_price = entry_price * (1 - stop_loss_pct)
        take_price = entry_price * (1 + take_profit_pct)

        # -----------------------------------------------------
        # 6. RISK / REWARD DINÂMICO
        # -----------------------------------------------------
        risk = entry_price - stop_price
        reward = take_price - entry_price
        rr = reward / risk if risk > 0 else 0.0

        min_rr = float(min_rr)
        min_rr = max(1.05, min(min_rr, 2.50))

        if rr < min_rr:
            return RiskEvaluation(
                approved=False,
                reason=f"RR ruim ({rr:.2f} < {min_rr:.2f})",
                stop_loss_price=round(stop_price, 8),
                take_profit_price=round(take_price, 8),
                risk_reward_ratio=round(rr, 2),
                expected_profit_pct=expected_profit_pct,
            )

        logger.info(
            f"[Risk] ✅ {pair} | "
            f"RR={rr:.2f} | "
            f"min_rr={min_rr:.2f} | "
            f"exp_profit={expected_profit_pct:.4%} | "
            f"SL={stop_price:.8f} | "
            f"TP={take_price:.8f}"
        )

        return RiskEvaluation(
            approved=True,
            reason="Trade aprovado",
            stop_loss_price=round(stop_price, 8),
            take_profit_price=round(take_price, 8),
            risk_reward_ratio=round(rr, 2),
            expected_profit_pct=expected_profit_pct,
        )

    # -------------------------------------------------------------------------
    # EXIT
    # -------------------------------------------------------------------------

    def evaluate_exit(
        self,
        pair: str,
        entry_price: float,
        current_price: float,
        capital_invested: float,
    ):
        return RiskEvaluation(
            approved=True,
            reason="Exit liberado",
        )

    # -------------------------------------------------------------------------
    # PLACEHOLDERS
    # -------------------------------------------------------------------------

    def register_position_opened(self, capital):
        pass

    def register_trade_result(self, capital, profit):
        pass

    def get_status(self):
        return {"mode": "PRO_DYNAMIC"}