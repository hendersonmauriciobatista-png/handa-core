# core/credentials/api_keys.py

import os
from typing import Optional
from core.execution_mode import ExecutionMode, get_execution_mode


# =====================================================
# MODELOS DE CHAVES SUPORTADOS
# =====================================================

class ApiKeyName:
    """
    Nomes padronizados de chaves externas.
    Evita strings soltas espalhadas pelo código.
    """
    BINANCE_API_KEY = "BINANCE_API_KEY"
    BINANCE_API_SECRET = "BINANCE_API_SECRET"


# =====================================================
# LEITURA DE CREDENCIAIS
# =====================================================

def _read_env(key_name: str) -> Optional[str]:
    """
    Leitura direta de variável de ambiente.
    Nunca levanta exceção.
    """
    return os.getenv(key_name)


def get_api_key(key_name: str, *, required: bool = False) -> Optional[str]:
    """
    Retorna uma chave de API conforme o modo de execução.

    - Em MOCK: retorna None sempre
    - Em LIVE: lê do ambiente
    - Se required=True e LIVE sem chave → exceção
    """

    mode = get_execution_mode()

    # -------------------------
    # MOCK → nunca usa chave
    # -------------------------
    value = _read_env(key_name)
    return value
    # -------------------------
    # LIVE → lê do ambiente
    # -------------------------
    value = _read_env(key_name)

    if required and not value:
        raise RuntimeError(
            f"Chave obrigatória ausente em LIVE: {key_name}"
        )

    return value


# =====================================================
# ATALHOS ESPECÍFICOS (BINANCE)
# =====================================================

def get_binance_api_key(*, required: bool = True) -> Optional[str]:
    return get_api_key(ApiKeyName.BINANCE_API_KEY, required=required)


def get_binance_api_secret(*, required: bool = True) -> Optional[str]:
    return get_api_key(ApiKeyName.BINANCE_API_SECRET, required=required)


# =====================================================
# DIAGNÓSTICO CONTROLADO
# =====================================================

def has_required_keys() -> bool:
    """
    Retorna True se todas as chaves obrigatórias
    para LIVE estiverem presentes.
    """
    if get_execution_mode() != ExecutionMode.LIVE:
        return True

    return all([
        _read_env(ApiKeyName.BINANCE_API_KEY),
        _read_env(ApiKeyName.BINANCE_API_SECRET),
    ])
