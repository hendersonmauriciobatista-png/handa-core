# governance.py
# ==============================
# UI Control Core — Governance
# FASE 1: Controle Humano
# Sistema: H&A / ALFRED IA
# ==============================

from datetime import datetime
from typing import Dict, Any
from .control_bus import ControlEvent
from .state import UIControlState


class Governance:
    """
    Camada de governança do sistema.
    Responsável por:
    - auditoria
    - rastreabilidade
    - responsabilidade
    - reversibilidade
    - institucionalização das ações
    """

    # ==============================
    # Auditoria
    # ==============================

    def audit(
        self,
        event: ControlEvent,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Gera registro auditável de uma ação de controle.
        """

        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "actor": event.source,
            "action": event.name,
            "payload": event.payload,
            "before": before_state,
            "after": after_state,
        }

        return record

    # ==============================
    # Validação institucional
    # ==============================

    def validate_action(self, event: ControlEvent, ui_state: UIControlState) -> bool:
        """
        Valida ação sob regras institucionais.
        """

        # Exemplo de regra institucional:
        # nunca permitir reset automático sem operador
        if event.name == "RESET" and event.source != "operator":
            return False

        return True

    # ==============================
    # Reversibilidade
    # ==============================

    def reversible(self, event: ControlEvent) -> bool:
        """
        Indica se ação é reversível.
        """
        non_reversible = {"DESTROY_SLOT", "HARD_RESET"}
        return event.name not in non_reversible
