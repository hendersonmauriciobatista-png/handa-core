from typing import List

from state.slot_states import AnalysisState, TradingState
from state.slot_events import SlotEvent


class SlotStateMachine:
    """
    Máquina de estados independente por slot.
    Contém SOMENTE regras de transição e snapshot.
    """

    def __init__(self, slot_id: int):
        self.slot_id = slot_id
        self.analysis_state = AnalysisState.ANALYSIS_IDLE
        self.trading_state = TradingState.TRADING_WAITING_ANALYSIS

    # =====================================================
    # RESET TOTAL DO SLOT
    # =====================================================

    def reset(self):
        """
        Retorna o slot para o estado inicial.
        Usado em reset global (ex: troca de MODE).
        """
        self.analysis_state = AnalysisState.ANALYSIS_IDLE
        self.trading_state = TradingState.TRADING_WAITING_ANALYSIS

    # =====================================================
    # PROCESSAMENTO DE EVENTOS
    # =====================================================

    def handle_event(self, event: SlotEvent) -> List[SlotEvent]:
        emitted_events: List[SlotEvent] = []

        # -------------------------
        # ANÁLISE
        # -------------------------
        if self.analysis_state == AnalysisState.ANALYSIS_IDLE:
            if event == SlotEvent.EV_ANALYSIS_START:
                self.analysis_state = AnalysisState.ANALYSIS_RUNNING

        elif self.analysis_state == AnalysisState.ANALYSIS_RUNNING:
            if event == SlotEvent.EV_ANALYSIS_APPROVED:
                self.analysis_state = AnalysisState.ANALYSIS_FINALIZED
                emitted_events.append(SlotEvent.EV_TRADING_START)

            elif event == SlotEvent.EV_RESET_PAIR:
                self.reset()

        # -------------------------
        # TRADING
        # -------------------------
        if self.trading_state == TradingState.TRADING_WAITING_ANALYSIS:
            if event == SlotEvent.EV_TRADING_START:
                self.trading_state = TradingState.TRADING_RUNNING

        elif self.trading_state == TradingState.TRADING_RUNNING:
            if event == SlotEvent.EV_TRADING_FINISH:
                self.trading_state = TradingState.TRADING_FINISHED  # ✅ CORRETO

            elif event == SlotEvent.EV_RESET_PAIR:
                self.reset()

        return emitted_events

    # =====================================================
    # SNAPSHOT
    # =====================================================

    def snapshot(self) -> dict:
        return {
            "slot_id": self.slot_id,
            "analysis_state": self.analysis_state.name,
            "trading_state": self.trading_state.name,
        }
