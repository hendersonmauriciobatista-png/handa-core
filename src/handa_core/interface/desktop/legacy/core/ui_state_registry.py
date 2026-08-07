"""
UIStateRegistry — Registry passivo de estado da UI

Responsabilidade:
- Manter snapshot do último estado conhecido de cada slot
- Ser atualizado por eventos (ex: slot_state)
- Expor leitura segura para a UI nova

NÃO executa lógica
NÃO decide
NÃO chama core
"""

from typing import Dict, Any
from threading import Lock
from datetime import datetime


class UIStateRegistry:
    def __init__(self):
        self._lock = Lock()
        self._slots: Dict[int, Dict[str, Any]] = {}

    # ---------------------------------
    # Atualização por evento (entrada)
    # ---------------------------------
    def update_slot_state(
        self,
        slot_id: int,
        state: str,
        extra: Dict[str, Any] | None = None
    ):
        with self._lock:
            self._slots[slot_id] = {
                "slot_id": f"SLOT-{slot_id}",
                "state": state,
                "extra": extra or {},
                "updated_at": datetime.utcnow().isoformat()
            }

    # ---------------------------------
    # Leitura segura (UI nova)
    # ---------------------------------
    def get_snapshot(self) -> Dict[int, Dict[str, Any]]:
        with self._lock:
            # cópia defensiva para evitar mutação externa
            return dict(self._slots)


# -------------------------------------------------
# Singleton global (uso padrão)
# -------------------------------------------------
ui_state_registry = UIStateRegistry()
