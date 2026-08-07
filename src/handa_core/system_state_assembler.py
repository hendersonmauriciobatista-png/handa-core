"""
SystemStateAssembler
Responsável por montar o state dict global consumido pela UI.

Regras:
- Não decide transições
- Apenas traduz estado interno
- Contém o modo operacional (MOCK / LIVE)
"""

import time
from h_a.execution_mode import ExecutionMode


class SystemStateAssembler:

    def __init__(self, state_controller):
        self._controller = state_controller
        self._mode = ExecutionMode.MOCK
        self._risk = "LOW"

    # ==========================================================
    # MODE
    # ==========================================================

    @property
    def mode(self):
        return self._mode

    def set_mode(self, mode: ExecutionMode):
        self._mode = mode

    # ==========================================================
    # RISK
    # ==========================================================

    def set_risk(self, risk: str):
        self._risk = risk

    # ==========================================================
    # BUILD
    # ==========================================================

    def build(self) -> dict:

        return {
            "system": {
                "system_status": self._controller.state.value,
                "mode": self._mode.value,
                "risk": self._risk,
                "heartbeat": time.time(),
            }
        }
