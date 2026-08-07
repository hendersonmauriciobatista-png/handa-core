from math import floor


class CapitalValidator:

    def validate(
        self,
        usdc_to_use: float,
        asset_price: float,
        current_exposure: float,
        capital_utilizavel: float,
        step_size: float,
        min_notional: float
    ):

        exposure_after = current_exposure + usdc_to_use

        if exposure_after > capital_utilizavel:
            return None, None, False, "Exposição máxima atingida"

        quantity = usdc_to_use / asset_price
        quantity = floor(quantity / step_size) * step_size
        usdc_final = quantity * asset_price

        if usdc_final < min_notional:
            return None, None, False, "Abaixo do minNotional"

        return quantity, usdc_final, True, None
