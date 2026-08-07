from dataclasses import dataclass
from .capital_allocator import CapitalAllocator
from .capital_validator import CapitalValidator
from .capital_engine import CapitalEngine


@dataclass
class AllocationResult:
    usdc_to_use: float
    quantity: float
    exposure_after: float
    valid: bool
    reason: str | None = None


class CapitalEngine:

    def __init__(self):
        self.allocator = CapitalAllocator()
        self.validator = CapitalValidator()

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

        capital_utilizavel = total_usdc * self.allocator.UTILIZATION_RATIO

        usdc_to_use = self.allocator.calculate_base_allocation(
            total_usdc,
            asset_score,
            score_medio
        )

        quantity, usdc_final, valid, reason = self.validator.validate(
            usdc_to_use,
            asset_price,
            current_exposure,
            capital_utilizavel,
            step_size,
            min_notional
        )

        if not valid:
            return AllocationResult(
                usdc_to_use=0,
                quantity=0,
                exposure_after=current_exposure,
                valid=False,
                reason=reason
            )

        return AllocationResult(
            usdc_to_use=usdc_final,
            quantity=quantity,
            exposure_after=current_exposure + usdc_final,
            valid=True,
            reason=None
        )
