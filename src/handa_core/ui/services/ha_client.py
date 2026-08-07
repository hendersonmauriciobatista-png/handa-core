"""
HAClient — API Local (UI ↔ H&A)
Cliente HTTP somente leitura por padrão.

Regras:
- UI NÃO fala com a exchange
- UI NÃO decide
- UI consome estado REAL do H&A via API local
"""

import requests
from typing import Dict, Any


class HAClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.timeout = 1.5

    # =========================
    # Interno
    # =========================
    def _get(self, path: str) -> Dict[str, Any]:
        r = requests.get(f"{self.base_url}{path}", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = requests.post(
            f"{self.base_url}{path}",
            json=payload,
            timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()

    # =========================
    # Saúde / Conexão
    # =========================
    def connect(self) -> bool:
        # handshake simples
        self._get("/health")
        return True

    # =========================
    # Estados (READ-ONLY)
    # =========================
    def fetch_system_state(self) -> Dict[str, Any]:
        return self._get("/state/system")

    def fetch_slots_state(self) -> Dict[str, Any]:
        return self._get("/state/slots")

    def fetch_activity_state(self) -> Dict[str, Any]:
        return self._get("/state/activity")

    def fetch_connectivity_state(self) -> Dict[str, Any]:
        return self._get("/state/connectivity")

    # =========================
    # Comandos Globais
    # =========================
    def send_global_command(self, command: str) -> Dict[str, Any]:
        # Em MOCK, o backend REJEITA — a UI apenas exibe
        return self._post("/command", {"command": command})
