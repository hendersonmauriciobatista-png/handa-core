from ..core_logic.analysis_sm import AnalysisStateMachine
from ..core_logic.trading_sm import TradingStateMachine
from ..core_logic.enums import AnalysisState, TradingState


class Slot:
    """
    Entidade central do H&A.
    Orquestra ANÁLISE e TRADING via máquinas de estado.
    Core lógico definitivo (sem UI).
    """

    def __init__(self, slot_id: int):
        self.slot_id = slot_id

        # Máquinas de estado
        self.analysis_sm = AnalysisStateMachine()
        self.trading_sm = TradingStateMachine()

        # Ativo atual (ex: BTC/USDC)
        self.active_pair = None

        # Cadeado lógico (exposto para UI)
        self.locked = False

    # =========================
    # ANÁLISE
    # =========================

    def start_analysis(self, pair: str):
        """
        Inicia uma nova análise.
        Só permitido quando o slot está IDLE.
        """
        self.analysis_sm.start()
        self.active_pair = pair
        self.locked = True

    def analysis_signal_found(self):
        """
        Análise encontrou sinal válido.
        Habilita o trading.
        """
        self.analysis_sm.signal_found()
        self.trading_sm.ready()

    def analysis_rejected(self):
        """
        Análise rejeitada.
        Encerra o ciclo completo e libera o slot.
        """
        self.analysis_sm.reject()
        self.analysis_sm.finalize()
        self.analysis_sm.reset()

        self.active_pair = None
        self.locked = False

    def finalize_analysis(self):
        """
        Finalização explícita (caso futuro).
        """
        self.analysis_sm.finalize()
        self.locked = False

    # =========================
    # TRADING
    # =========================

    def start_trading(self):
        """
        Inicia o trading após READY.
        """
        self.trading_sm.start()

    def trading_completed(self):
        """
        Trade finalizado com sucesso.
        Encerra o ciclo completo.
        """
        self.trading_sm.complete()
        self._reset_after_trade()

    def trading_aborted(self):
        """
        Trade abortado.
        Encerra o ciclo completo.
        """
        self.trading_sm.abort()
        self._reset_after_trade()

    # =========================
    # RESET
    # =========================

    def _reset_after_trade(self):
        """
        Após o trade, a análise do sinal é considerada FINALIZADA
        e o slot retorna ao estado inicial.
        """
        if self.analysis_sm.state == AnalysisState.SIGNAL_FOUND:
            self.analysis_sm.finalize()

        self.analysis_sm.reset()
        self.trading_sm.reset()

        self.active_pair = None
        self.locked = False

    # =========================
    # SNAPSHOT (UI / LOG)
    # =========================

    def snapshot(self) -> dict:
        """
        Estado atual do slot para UI, logs ou monitoramento.
        """
        return {
            "slot_id": self.slot_id,
            "pair": self.active_pair,
            "analysis_state": self.analysis_sm.state.name,
            "trading_state": self.trading_sm.state.name,
            "locked": self.locked,
        }
