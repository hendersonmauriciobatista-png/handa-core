# core/execution_mode.py

from enum import Enum


class ExecutionMode(Enum):
    """
    Modo de execução global do sistema.
    """
    MOCK = "MOCK"
    LIVE = "LIVE"


# =====================================================
# ESTADO GLOBAL
# =====================================================

_current_execution_mode: ExecutionMode = ExecutionMode.MOCK


# =====================================================
# GETTERS / SETTERS
# =====================================================

def get_execution_mode() -> ExecutionMode:
    """
    Retorna o modo de execução atual.
    """
    return _current_execution_mode


def set_execution_mode(mode: ExecutionMode) -> None:
    """
    Define o modo de execução global.
    """
    global _current_execution_mode
    if not isinstance(mode, ExecutionMode):
        raise ValueError("Modo inválido. Use ExecutionMode.MOCK ou ExecutionMode.LIVE.")
    _current_execution_mode = mode


def is_mock() -> bool:
    """
    True se o sistema estiver em MOCK.
    """
    return _current_execution_mode == ExecutionMode.MOCK


def is_live() -> bool:
    """
    True se o sistema estiver em LIVE.
    """
    return _current_execution_mode == ExecutionMode.LIVE
