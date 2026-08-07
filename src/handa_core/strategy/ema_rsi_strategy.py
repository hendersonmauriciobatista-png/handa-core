from .base_strategy import BaseStrategy


class EMARsiStrategy(BaseStrategy):
    """
    Estratégia real EMA + RSI.
    Usada pelo Slot em modo Mock / Real.
    """

    def __init__(self, rsi_limit_enter=70, rsi_limit_exit=70):
        self.rsi_limit_enter = rsi_limit_enter
        self.rsi_limit_exit = rsi_limit_exit

    # ==================================================
    # MÉTODO ABSTRATO (CONTRATO)
    # ==================================================

    def analyze(self, market_data: dict) -> dict:
        """
        Análise completa do mercado.
        Retorna decisão estruturada.
        """
        return {
            "should_enter": self.should_enter(market_data),
            "should_exit": self.should_exit(market_data),
        }

    # ==================================================
    # REGRAS DE ENTRADA / SAÍDA
    # ==================================================

    def should_enter(self, market_data: dict) -> bool:
        ema_fast = market_data.get("ema_fast")
        ema_slow = market_data.get("ema_slow")
        rsi = market_data.get("rsi")

        if ema_fast is None or ema_slow is None or rsi is None:
            return False

        return ema_fast > ema_slow and rsi < self.rsi_limit_enter

    def should_exit(self, market_data: dict) -> bool:
        ema_fast = market_data.get("ema_fast")
        ema_slow = market_data.get("ema_slow")
        rsi = market_data.get("rsi")

        if ema_fast is None or ema_slow is None or rsi is None:
            return False

        return ema_fast < ema_slow or rsi > self.rsi_limit_exit
