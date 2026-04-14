"""
StateListener — versão definitiva
Responsável por:
- conectar na API local do H&A
- buscar estados reais
- manter snapshot thread-safe para a UI

Sem decisões. Sem lógica de negócio.
"""

import threading
import time
from typing import Dict, Any


class StateListener:
    def __init__(self, ha_client):
        self.ha_client = ha_client
        self.running = False
        self.lock = threading.Lock()

        # Estado inicial explícito (boot)
        self.state: Dict[str, Any] = {
            "system": {
                "system_status": "BOOTING",
                "mode": "MOCK",
                "risk": "UNKNOWN",
                "heartbeat": None
            },
            "slots": {},
            "activity": {
                "summary": "Inicializando UI",
                "last_event": "-"
            },
            "connectivity": {
                "status": "CONNECTING",
                "last_update": None
            }
        }

    # =========================
    # Ciclo principal
    # =========================
    def run(self):
        print("[StateListener] START")
        self.running = True

        # Handshake
        try:
            self.ha_client.connect()
            print("[StateListener] CONNECTED")
        except Exception as e:
            print("[StateListener] CONNECT FAILED:", repr(e))
            with self.lock:
                self.state["connectivity"] = {
                    "status": "NO_FEED",
                    "last_update": int(time.time()),
                    "error": str(e)
                }
            return

        while self.running:
            self._update_state()
            time.sleep(0.5)

    def stop(self):
        self.running = False

    # =========================
    # Atualização de estado
    # =========================
    def _update_state(self):
        try:
            system_state = self.ha_client.fetch_system_state()
            slots_state = self.ha_client.fetch_slots_state()
            activity_state = self.ha_client.fetch_activity_state()
            connectivity_state = self.ha_client.fetch_connectivity_state()

            print("[StateListener] SYSTEM:", system_state)
            print("[StateListener] SLOTS:", list(slots_state.keys()))

            with self.lock:
                self.state["system"] = system_state
                self.state["slots"] = slots_state
                self.state["activity"] = activity_state
                self.state["connectivity"] = connectivity_state

        except Exception as e:
            print("[StateListener] FETCH ERROR:", repr(e))
            with self.lock:
                self.state["connectivity"] = {
                    "status": "NO_FEED",
                    "last_update": int(time.time()),
                    "error": str(e)
                }

    # =========================
    # Snapshot para a UI
    # =========================
    def get_state_snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "system": dict(self.state.get("system", {})),
                "slots": dict(self.state.get("slots", {})),
                "activity": dict(self.state.get("activity", {})),
                "connectivity": dict(self.state.get("connectivity", {})),
            }
