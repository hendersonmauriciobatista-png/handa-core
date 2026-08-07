# core_bridge/commands.py
from typing import Dict, Any


class CoreCommands:
    """
    Envia comandos humanos ao Core.
    Todo comando pode ser NEGADO.
    """

    def __init__(self, core_adapter):
        self._adapter = core_adapter

    # ---------
    # SISTEMA
    # ---------
    def start_system(self) -> Dict[str, Any]:
        return self._adapter.send_command("CMD_SYSTEM_START")

    def pause_system(self) -> Dict[str, Any]:
        return self._adapter.send_command("CMD_SYSTEM_PAUSE")

    def resume_system(self) -> Dict[str, Any]:
        return self._adapter.send_command("CMD_SYSTEM_RESUME")

    def stop_system(self) -> Dict[str, Any]:
        return self._adapter.send_command("CMD_SYSTEM_STOP")

    # ---------
    # SLOT
    # ---------
    def stop_slot(self, slot_id: str) -> Dict[str, Any]:
        return self._adapter.send_command(
            "CMD_SLOT_STOP",
            payload={"slot_id": slot_id},
        )

    def reset_slot(self, slot_id: str) -> Dict[str, Any]:
        return self._adapter.send_command(
            "CMD_SLOT_RESET",
            payload={"slot_id": slot_id},
        )
