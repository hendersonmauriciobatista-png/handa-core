from core_logic.enums import TradingState


class TradingStateMachine:
    """
    Máquina de estados do TRADING.
    Controla apenas o ciclo de execução do trade.
    """

    def __init__(self):
        self.state = TradingState.WAITING_ANALYSIS

    # =========================
    # TRANSIÇÕES
    # =========================

    def ready(self):
        if self.state != TradingState.WAITING_ANALYSIS:
            raise RuntimeError("READY só permitido a partir de WAITING_ANALYSIS")
        self.state = TradingState.READY

    def start(self):
        if self.state != TradingState.READY:
            raise RuntimeError("START só permitido a partir de READY")
        self.state = TradingState.RUNNING

    def complete(self):
        if self.state != TradingState.RUNNING:
            raise RuntimeError("COMPLETE só permitido a partir de RUNNING")
        self.state = TradingState.COMPLETED

    def abort(self):
        if self.state != TradingState.RUNNING:
            raise RuntimeError("ABORT só permitido a partir de RUNNING")
        self.state = TradingState.ABORTED

    def reset(self):
        if self.state not in (TradingState.COMPLETED, TradingState.ABORTED):
            raise RuntimeError("RESET só permitido após COMPLETE ou ABORT")
        self.state = TradingState.WAITING_ANALYSIS

    # =========================
    # UTILITÁRIOS
    # =========================

    def snapshot(self) -> str:
        return self.state.name
