# core_bridge/reader.py
from typing import Dict, Any


class CoreReader:
    """
    Leitor READ-ONLY do estado do Core.
    A UI nunca calcula, nunca altera, nunca decide.
    """

    def __init__(self, core_adapter):
        self._adapter = core_adapter

    def get_system_state(self) -> Dict[str, Any]:
        return self._adapter.read_system_state()

    def get_active_slot_state(self) -> Dict[str, Any]:
        return self._adapter.read_active_slot()

    def get_metadata(self) -> Dict[str, Any]:
        return self._adapter.read_metadata()
