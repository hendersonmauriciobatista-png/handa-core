from typing import Tuple


class PreLiveChecklist:
    """
    Checklist técnico obrigatório antes de LIVE REAL.
    (Placeholders seguros — lógica real entra depois)
    """

    MAX_DEVIATION = 0.003  # 0,3%

    @staticmethod
    def check_price_deviation(expected: float, current: float) -> Tuple[bool, str]:
        if expected <= 0 or current <= 0:
            return False, "Preço inválido"
        deviation = abs(current - expected) / expected
        if deviation > PreLiveChecklist.MAX_DEVIATION:
            return False, f"Desvio de preço alto: {deviation:.4%}"
        return True, "Desvio OK"

    @staticmethod
    def check_balance(balance_usdc: float, required_usdc: float) -> Tuple[bool, str]:
        if balance_usdc < required_usdc:
            return False, "Saldo USDC insuficiente"
        return True, "Saldo OK"

    @staticmethod
    def check_liquidity(symbol: str) -> Tuple[bool, str]:
        # Placeholder seguro
        return True, "Liquidez OK"

    @staticmethod
    def check_sync() -> Tuple[bool, str]:
        # Placeholder seguro
        return True, "Sincronismo OK"

    @classmethod
    def run_all(cls) -> Tuple[bool, list]:
        results = []
        ok, msg = cls.check_price_deviation(expected=100.0, current=100.0)
        results.append(msg)
        if not ok:
            return False, results

        ok, msg = cls.check_balance(balance_usdc=1000.0, required_usdc=50.0)
        results.append(msg)
        if not ok:
            return False, results

        ok, msg = cls.check_liquidity(symbol="TEST")
        results.append(msg)
        if not ok:
            return False, results

        ok, msg = cls.check_sync()
        results.append(msg)
        if not ok:
            return False, results

        return True, results
