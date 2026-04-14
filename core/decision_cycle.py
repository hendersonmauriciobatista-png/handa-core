from core.capital_engine.capital_allocator import CapitalAllocator
from core.capital_engine.capital_validator import CapitalValidator
from core.market_engine.market_engine import MarketEngine


class DecisionCycle:

    DELTA_MINIMO_SWAP = 0.3
    COOLDOWN_SWAP_CYCLES = 2
    HOLD_CYCLES_BEFORE_SELL = 3  # mock simples de saída

    def __init__(self, executor):
        self.market_engine = MarketEngine()
        self.executor = executor

        self.capital_allocator = CapitalAllocator()
        self.capital_validator = CapitalValidator()

        self.current_asset = None
        self.current_score = None
        self.swap_cooldown_counter = 0

        # contador de ciclos segurando posição
        self.hold_cycles = 0

    # =================================================
    # SWAP LOGIC
    # =================================================
    def should_swap(self, new_asset, new_score):

        if self.swap_cooldown_counter > 0:
            self.swap_cooldown_counter -= 1
            return False

        if self.current_asset is None:
            return True

        if new_asset == self.current_asset:
            return True

        if new_score >= self.current_score + self.DELTA_MINIMO_SWAP:
            return True

        return False

    # =================================================
    # MAIN CYCLE
    # =================================================
    def run_cycle(
        self,
        total_usdc: float,
        current_exposure: float,
        market_data: dict,
        asset_price_lookup: dict,
        step_size_lookup: dict,
        min_notional_lookup: dict
    ):

        # -------------------------------------------------
        # 1️⃣ SE JÁ TEM POSIÇÃO → avaliar venda
        # -------------------------------------------------
        if self.executor.has_open_position():

            self.hold_cycles += 1

            if self.hold_cycles >= self.HOLD_CYCLES_BEFORE_SELL:
                sell_price = asset_price_lookup[self.current_asset]

                order_result = self.executor.sell(price=sell_price)

                self.hold_cycles = 0
                self.current_asset = None
                self.current_score = None

                return {
                    "executed": True,
                    "type": "sell",
                    "order": order_result
                }

            return {
                "executed": False,
                "reason": f"Aguardando venda ({self.hold_cycles})"
            }

        # -------------------------------------------------
        # 2️⃣ MARKET ENGINE
        # -------------------------------------------------
        best_asset, best_score, score_medio = self.market_engine.rank_assets(market_data)

        if not self.should_swap(best_asset, best_score):
            return {
                "executed": False,
                "reason": "Swap bloqueado por delta ou cooldown"
            }

        # -------------------------------------------------
        # 3️⃣ CAPITAL ALLOCATION
        # -------------------------------------------------
        usdc_to_use = self.capital_allocator.calculate_base_allocation(
            total_usdc=total_usdc,
            asset_score=best_score,
            score_medio=score_medio
        )

        quantity, usdc_final, valid, reason = self.capital_validator.validate(
            usdc_to_use=usdc_to_use,
            asset_price=asset_price_lookup[best_asset],
            current_exposure=current_exposure,
            capital_utilizavel=total_usdc * self.capital_allocator.UTILIZATION_RATIO,
            step_size=step_size_lookup[best_asset],
            min_notional=min_notional_lookup[best_asset]
        )

        if not valid:
            return {
                "executed": False,
                "reason": reason
            }

        # -------------------------------------------------
        # 4️⃣ EXECUTOR BUY
        # -------------------------------------------------
        order_result = self.executor.buy(
            symbol=best_asset,
            quantity=quantity,
            price=asset_price_lookup[best_asset]
        )

        if order_result["status"] != "ok":
            return {
                "executed": False,
                "reason": order_result.get("message", "Erro execução")
            }

        self.current_asset = best_asset
        self.current_score = best_score
        self.hold_cycles = 0

        return {
            "executed": True,
            "type": "buy",
            "symbol": best_asset,
            "quantity": quantity,
            "usdc_used": usdc_final,
            "order": order_result
        }
