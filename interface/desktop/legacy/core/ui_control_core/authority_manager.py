# authority_manager.py
# ==============================
# UI Control Core — Authority Manager
# FASE 1: Controle Humano
# Sistema: H&A / ALFRED IA
# ==============================

from typing import Dict
from .state import UIControlState


class ActionSource:
    OPERATOR = "operator"
    POLICY = "policy"
    SYSTEM = "system"


class AuthorityManager:
    """
    Gerencia hierarquia de poder e valida permissões de ação.
    Implementa a soberania humana:
    operator > policy > system
    """

    PRIORITY: Dict[str, int] = {
        ActionSource.OPERATOR: 3,
        ActionSource.POLICY: 2,
        ActionSource.SYSTEM: 1,
    }

    def allow(self, source: str, ui_state: UIControlState) -> bool:
        """
        Verifica se a fonte da ação pode atuar no estado atual.
        """

        # Operador sempre pode
        if source == ActionSource.OPERATOR:
            return True

        # Se operador está em override, ninguém mais pode
        if ui_state.operator_override:
            return False

        # Policy pode atuar se não houver override
        if source == ActionSource.POLICY:
            return True

        # System só atua se não houver override
        if source == ActionSource.SYSTEM:
            return True

        # Fonte desconhecida
        return False

    def compare_priority(self, source_a: str, source_b: str) -> str:
        """
        Retorna qual fonte tem maior prioridade.
        """
        pa = self.PRIORITY.get(source_a, 0)
        pb = self.PRIORITY.get(source_b, 0)

        if pa > pb:
            return source_a
        elif pb > pa:
            return source_b
        else:
            return source_a
