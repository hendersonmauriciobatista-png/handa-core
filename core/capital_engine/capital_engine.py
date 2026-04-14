from dataclasses import dataclass

from .capital_allocator import CapitalAllocator


@dataclass
class AllocationResult:
    quantity: float
    usdc_to_use: float
    valid: bool
    reason: str | None = None


class CapitalEngine:
    """
    Orquestrador do Capital:
    - Calcula base allocation
    - Valida exposição
    - Aplica step_size
    - Aplica min_notional
    """

    def __init__(self):
        self.allocator = CapitalAllocator()
        

    def calculate_allocation(
        self,
        total_usdc: float,
        asset_price: float,
        asset_score: float,
        score_medio: float,
        current_exposure: float,
        step_size: float,
        min_notional: float
    ) -> AllocationResult:

        # 1️⃣ Base allocation
        usdc_to_use = self.allocator.calculate_base_allocation(
            total_usdc=total_usdc,
            asset_score=asset_score,
            score_medio=score_medio
        )

        capital_utilizavel = total_usdc * self.allocator.UTILIZATION_RATIO

        # 2️⃣ Validação
        quantity, usdc_final, valid, reason = self.validator.validate(
            usdc_to_use=usdc_to_use,
            asset_price=asset_price,
            current_exposure=current_exposure,
            capital_utilizavel=capital_utilizavel,
            step_size=step_size,
            min_notional=min_notional
        )

        if not valid:
            return AllocationResult(
                quantity=0,
                usdc_to_use=0,
                valid=False,
                reason=reason
            )

        return AllocationResult(
            quantity=quantity,
            usdc_to_use=usdc_final,
            valid=True,
            reason=None
        )
