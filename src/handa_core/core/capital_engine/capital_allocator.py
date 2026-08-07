# ============================================================
# core/capital_engine/capital_allocator.py
# Capital Allocator - versão H&A evoluída SAFE COMPAT
# COM request_allocation PARA DecisionEngine
# ============================================================

from dataclasses import dataclass


@dataclass
class AllocationDecision:
    approved: bool
    allocated_usdc: float = 0.0
    reason: str = ""


class CapitalAllocator:

    TOTAL_SLOTS = 2
    UTILIZATION_RATIO = 0.80

    MIN_ADJUST = 0.85
    MAX_ADJUST = 1.15

    RISK_PER_TRADE = 0.10
    BALANCE_BUFFER = 0.95

    FALLBACK_MIN_NOTIONAL = 5.0
    MIN_NOTIONAL_BUFFER_MULTIPLIER = 1.05

    def __init__(self, executor):
        self.executor = executor

    # ========================================================
    # HELPERS
    # ========================================================

    def _get_min_notional_safe(self, symbol: str) -> float:
        try:
            if self.executor and hasattr(self.executor, "get_min_notional"):
                value = self.executor.get_min_notional(symbol)
                if value is not None and float(value) > 0:
                    return float(value)
        except Exception as e:
            print(f"[ALLOCATOR] erro ao buscar min_notional de {symbol}: {e}")

        return float(self.FALLBACK_MIN_NOTIONAL)

    def _get_total_usdc_safe(self) -> float:
        try:
            if self.executor and hasattr(self.executor, "get_balance"):
                value = self.executor.get_balance("USDC")
                if value is not None:
                    return float(value)
        except Exception as e:
            print(f"[ALLOCATOR] erro ao buscar saldo USDC: {e}")

        return 0.0

    # ========================================================
    # CÁLCULO COMPLETO DE CAPITAL
    # ========================================================

    def calculate_capital(
        self,
        symbol: str,
        total_usdc: float,
        asset_score: float,
        score_medio: float
    ) -> float:

        try:
            total_usdc = float(total_usdc or 0.0)
            asset_score = float(asset_score or 0.0)
            score_medio = float(score_medio or 0.0)

            if total_usdc <= 0:
                print(f"[ALLOCATOR] saldo inválido para {symbol}: {total_usdc}")
                return 0.0

            capital_utilizavel = total_usdc * self.UTILIZATION_RATIO
            capital_base = capital_utilizavel / self.TOTAL_SLOTS

            ajuste = 1 + ((asset_score - score_medio) / 10)
            ajuste = max(self.MIN_ADJUST, min(self.MAX_ADJUST, ajuste))

            capital_score = capital_base * ajuste
            capital_risco = total_usdc * self.RISK_PER_TRADE

            min_notional = self._get_min_notional_safe(symbol)
            min_notional_buffer = min_notional * self.MIN_NOTIONAL_BUFFER_MULTIPLIER

            capital_final = max(
                capital_score,
                capital_risco,
                min_notional_buffer
            )

            if capital_final > total_usdc:
                capital_final = total_usdc * self.BALANCE_BUFFER

            capital_final = float(max(0.0, capital_final))

            print(
                f"[ALLOCATOR] {symbol} | "
                f"Score: {capital_score:.2f} | "
                f"Risco: {capital_risco:.2f} | "
                f"Min: {min_notional:.2f} | "
                f"Min+Buffer: {min_notional_buffer:.2f} | "
                f"Final: {capital_final:.2f}"
            )

            return capital_final

        except Exception as e:
            print(f"[ALLOCATOR ERRO] {e}")
            return 0.0

    # ========================================================
    # COMPAT COM DECISION ENGINE
    # ========================================================

    def request_allocation(self, symbol: str) -> AllocationDecision:
        try:
            total_usdc = self._get_total_usdc_safe()

            if total_usdc <= 0:
                return AllocationDecision(
                    approved=False,
                    allocated_usdc=0.0,
                    reason="Saldo USDC indisponível ou zerado",
                )

            # enquanto o score real não estiver plugado, usa neutro
            asset_score = 5.0
            score_medio = 5.0

            allocated = self.calculate_capital(
                symbol=symbol,
                total_usdc=total_usdc,
                asset_score=asset_score,
                score_medio=score_medio,
            )

            if allocated <= 0:
                return AllocationDecision(
                    approved=False,
                    allocated_usdc=0.0,
                    reason="Capital calculado inválido",
                )

            return AllocationDecision(
                approved=True,
                allocated_usdc=float(allocated),
                reason="Capital aprovado",
            )

        except Exception as e:
            return AllocationDecision(
                approved=False,
                allocated_usdc=0.0,
                reason=f"Erro no allocator: {e}",
            )