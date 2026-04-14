"""
CoreAdapter — Adaptador passivo de estado para a UI nova

Responsabilidade:
- Ler snapshot do UIStateRegistry
- Traduzir para o formato esperado pela UI
- NÃO executa
- NÃO decide
"""

from typing import List, Dict, Any
from interface.desktop.core.ui_state_registry import ui_state_registry


class CoreAdapter:
    def __init__(self):
        pass

    # ---------------------------------
    # Slots (estado operacional)
    # ---------------------------------
    def get_slots_state(self) -> List[Dict[str, Any]]:
        snapshot = ui_state_registry.get_snapshot()

        slots = []
        for slot_id, data in snapshot.items():
            slots.append({
                "slot_id": data.get("slot_id"),
                "symbol": data.get("extra", {}).get("symbol", "---/USDC"),
                "status": data.get("state", "UNKNOWN"),
                "mode": data.get("extra", {}).get("mode", "OBSERVAÇÃO"),
                "health": "OK",
                "last_event": data.get("state"),
                "updated_at": data.get("updated_at"),
            })

        # garante ordem SLOT-1 ... SLOT-12
        slots.sort(key=lambda s: int(s["slot_id"].split("-")[1]))
        return slots

    # ---------------------------------
    # Risco global (placeholder seguro)
    # ---------------------------------
    def get_global_risk(self) -> Dict[str, Any]:
        return {
            "status": "UNKNOWN",
            "reason": None,
            "last_event": None,
            "updated_at": None
        }



