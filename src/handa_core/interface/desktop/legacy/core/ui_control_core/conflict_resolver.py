# conflict_resolver.py
# ==============================
# UI Control Core — Conflict Resolver
# FASE 1: Controle Humano
# Sistema: H&A / ALFRED IA
# ==============================

from .authority_manager import ActionSource
from .state import UIControlState
from .control_bus import ControlEvent


class ConflictResolver:
    """
    Resolve conflitos entre eventos concorrentes.
    Garante determinismo, prioridade e previsibilidade do sistema.
    """

    # ==============================
    # Resolução principal
    # ==============================

    def resolve(self, event: ControlEvent, ui_state: UIControlState) -> ControlEvent:
        """
        Aplica regras de resolução de conflito antes da execução do evento.
        Retorna o evento resolvido (ou None se for bloqueado).
        """

        # ------------------------------
        # Regra 1 — Override humano
        # ------------------------------
        if ui_state.operator_override:
            if event.source != ActionSource.OPERATOR:
                # Sistema/Policy não podem atuar
                return None

        # ------------------------------
        # Regra 2 — Foco manual ativo
        # ------------------------------
        if ui_state.focus_mode == "manual":
            # Bloqueia eventos automáticos de foco
            if event.name in ["AUTO_FOCUS", "SYSTEM_FOCUS"]:
                return None

        # ------------------------------
        # Regra 3 — Pin soberano
        # ------------------------------
        if ui_state.pinned_slot:
            if event.name in ["AUTO_CENTER", "AUTO_SELECT"]:
                return None

        # ------------------------------
        # Regra 4 — Eventos inválidos
        # ------------------------------
        if not event.name or not event.source:
            return None

        # ------------------------------
        # Regra 5 — Evento válido
        # ------------------------------
        return event

    # ==============================
    # Utilitário
    # ==============================

    def is_blocked(self, event: ControlEvent, ui_state: UIControlState) -> bool:
        """
        Retorna True se o evento deve ser bloqueado.
        """
        return self.resolve(event, ui_state) is None
