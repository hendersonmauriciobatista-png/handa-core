from core_logic.enums import AnalysisState


class AnalysisStateMachine:
    """
    Máquina de estados da ANÁLISE.
    Responsável apenas por validar e executar transições.
    Não conhece UI, trading ou sistema.
    """

    def __init__(self):
        self.state = AnalysisState.IDLE

    # =========================
    # TRANSIÇÕES
    # =========================

    def start(self):
        if self.state != AnalysisState.IDLE:
            raise RuntimeError("Análise só pode iniciar a partir de IDLE")
        self.state = AnalysisState.ANALYSING

    def signal_found(self):
        if self.state != AnalysisState.ANALYSING:
            raise RuntimeError("Sinal só pode ocorrer durante ANALYSING")
        self.state = AnalysisState.SIGNAL_FOUND

    def reject(self):
        if self.state != AnalysisState.ANALYSING:
            raise RuntimeError("Rejeição só pode ocorrer durante ANALYSING")
        self.state = AnalysisState.REJECTED

    def finalize(self):
        if self.state not in (
            AnalysisState.SIGNAL_FOUND,
            AnalysisState.REJECTED,
        ):
            raise RuntimeError("Finalize só permitido após SIGNAL_FOUND ou REJECTED")
        self.state = AnalysisState.FINALIZED

    def reset(self):
        if self.state != AnalysisState.FINALIZED:
            raise RuntimeError("Reset só permitido após FINALIZED")
        self.state = AnalysisState.IDLE

    # =========================
    # UTILITÁRIOS
    # =========================

    def snapshot(self) -> str:
        return self.state.name
