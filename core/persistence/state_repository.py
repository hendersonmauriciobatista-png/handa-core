# =============================================================================
# core/persistence/state_repository.py
# H&A — State Repository Contract
# =============================================================================

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class StateRepository(ABC):
    """
    Contrato oficial de persistência do H&A.

    Objetivo:
    - Remover dependência de mock_state.json em ambiente VPS/Railway
    - Permitir restore seguro de saldo, posições e estado do sistema
    - Preparar o sistema para LIVE com persistência confiável
    """

    @abstractmethod
    def initialize(self) -> None:
        """
        Inicializa estrutura de persistência.
        Exemplo: criar tabelas se não existirem.
        """
        raise NotImplementedError

    @abstractmethod
    def save_system_state(self, key: str, value: Dict[str, Any]) -> None:
        """
        Salva um estado do sistema por chave.
        Exemplo:
        - mock_balance
        - open_positions
        - slot_state
        - runtime_state
        """
        raise NotImplementedError

    @abstractmethod
    def load_system_state(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Carrega um estado salvo por chave.
        Retorna None se não existir.
        """
        raise NotImplementedError

    @abstractmethod
    def delete_system_state(self, key: str) -> None:
        """
        Remove um estado salvo.
        """
        raise NotImplementedError
