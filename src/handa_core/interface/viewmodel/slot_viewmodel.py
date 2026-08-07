# interface/viewmodel/slot_viewmodel.py

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class SlotViewData:
    """
    Estrutura imutável com dados PRONTOS para a UI.
    A UI apenas lê — nunca decide.
    """
    slot_id: int
    status_text: str
    progress: int
    is_locked: bool
    color: str


class SlotViewModel:
    """
    Traduz snapshot técnico do SLOT em dados visuais.
    ZERO lógica de trading.
    ZERO acesso a executor.
    Linguagem de produto (não debug).
    """

    # =========================
    # Paleta premium (institucional)
    # =========================
    COLOR_IDLE = "#5F6368"        # cinza grafite suave
    COLOR_ANALYSIS = "#2F5D8C"    # azul aço
    COLOR_READY = "#4A3F6D"       # roxo fechado
    COLOR_PLANNED = "#2F6F68"     # verde petróleo
    COLOR_RUNNING = "#8A6D3B"     # âmbar fechado
    COLOR_DONE = "#2E5F3E"        # verde escuro institucional
    COLOR_ERROR = "#7A2E2E"       # vermelho escuro fechado

    def __init__(self, snapshot: Dict[str, Any]):
        """
        snapshot esperado (SlotController.snapshot_all):

        {
            "slot_id": int,
            "analysis_state": str,
            "analysis_strength": float | None,
            "trade_state": str,
            "symbol": str
        }
        """
        self.snapshot = snapshot

    # =====================================================
    # API PRINCIPAL
    # =====================================================

    def build(self) -> SlotViewData:
        """
        Constrói o objeto final que a UI consome.
        """
        slot_id = self.snapshot.get("slot_id", -1)
        state = self.snapshot.get("analysis_state", "UNKNOWN")
        is_locked = bool(self.snapshot.get("locked", False))

        status_text, progress, color = self._map_state(state)

        return SlotViewData(
            slot_id=slot_id,
            status_text=status_text,
            progress=progress,
            is_locked=is_locked,
            color=color
        )

    # =====================================================
    # MAPEAMENTO DE ESTADO (PADRÃO OFICIAL H&A)
    # =====================================================

    def _map_state(self, state: str):
        """
        Converte estado técnico em:
        - Texto institucional (produto)
        - Progresso (0–100)
        - Cor premium
        """

        # -------------------------
        # OCIOSO
        # -------------------------
        if state == "IDLE":
            return (
                "Aguardando oportunidade",
                0,
                self.COLOR_IDLE
            )

        # -------------------------
        # ANALISANDO
        # -------------------------
        if state == "ANALYZING":
            return (
                "Analisando mercado",
                30,
                self.COLOR_ANALYSIS
            )

        # -------------------------
        # ANALISADO
        # -------------------------
        if state == "ANALYZED":
            return (
                "Análise concluída",
                50,
                self.COLOR_READY
            )

        # -------------------------
        # PLANEJAMENTO
        # -------------------------
        if state == "TRADE_PLANNED":
            return (
                "Estratégia definida",
                65,
                self.COLOR_PLANNED
            )

        # -------------------------
        # EXECUÇÃO
        # -------------------------
        if state == "TRADING":
            return (
                "Operação em execução",
                85,
                self.COLOR_RUNNING
            )

        # -------------------------
        # FINALIZADO
        # -------------------------
        if state == "DONE":
            return (
                "Ciclo concluído",
                100,
                self.COLOR_DONE
            )

        # -------------------------
        # DESCONHECIDO / ERRO
        # -------------------------
        return (
            "Estado indefinido",
            0,
            self.COLOR_ERROR
        )
