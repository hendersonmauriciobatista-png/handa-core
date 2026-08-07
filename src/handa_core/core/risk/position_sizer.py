# ============================================================
# position_sizer.py
# PositionSizer do sistema H&A
# Responsável por dimensionar tamanho da posição
# ============================================================


class PositionSizer:
    """
    PositionSizer do H&A.

    Responsabilidades:
    - Calcular capital permitido para o trade
    - Converter capital em quantidade do ativo
    - Respeitar limites definidos no RiskManager
    """

    def __init__(self, risk_manager):
        self._risk_manager = risk_manager

    # --------------------------------------------------------
    # CAPITAL DISPONÍVEL PARA O TRADE
    # --------------------------------------------------------

    def capital_for_trade(self, available_capital: float) -> float:
        """
        Retorna quanto capital pode ser usado no trade,
        respeitando o limite do RiskManager.
        """

        max_per_trade = self._risk_manager.max_capital_per_trade()

        return min(available_capital, max_per_trade)

    # --------------------------------------------------------
    # QUANTIDADE DO ATIVO
    # --------------------------------------------------------

    def quantity_for_price(
        self,
        price: float,
        available_capital: float
    ) -> float:
        """
        Calcula quantidade de ativo a comprar.
        """

        if price <= 0:
            raise ValueError("INVALID_PRICE")

        capital = self.capital_for_trade(available_capital)

        quantity = capital / price

        return quantity

    # --------------------------------------------------------
    # SNAPSHOT
    # --------------------------------------------------------

    def snapshot(self):
        return {
            "max_capital_per_trade": self._risk_manager.max_capital_per_trade()
        }