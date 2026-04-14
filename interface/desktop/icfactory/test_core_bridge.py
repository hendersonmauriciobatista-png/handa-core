# test_core_bridge.py

from core_bridge.reader import CoreReader
from core_bridge.commands import CoreCommands
from core_bridge.events import CoreEvents


# Mock simples do Core
class MockCoreAdapter:
    def read_system_state(self):
        return {"system_state": "SYSTEM_READY"}

    def read_active_slot(self):
        return {"slot_id": "S1", "slot_state": "IDLE"}

    def read_metadata(self):
        return {"last_event_origin": "SYSTEM"}

    def send_command(self, cmd, payload=None):
        return {
            "accepted": True,
            "command": cmd,
            "payload": payload,
            "current_state": "OK",
        }


adapter = MockCoreAdapter()

reader = CoreReader(adapter)
commands = CoreCommands(adapter)

assert reader.get_system_state()["system_state"] == "SYSTEM_READY"
assert reader.get_active_slot_state()["slot_state"] == "IDLE"

resp = commands.start_system()
assert resp["accepted"] is True

print("✔ CoreReader OK")
print("✔ CoreCommands OK")

# Teste de eventos
events = CoreEvents()

def on_event(evt):
    print("Evento recebido:", evt)

events.subscribe(on_event)
events.emit({"type": "STATE_CHANGED", "state": "SYSTEM_RUNNING"})

print("🎉 BLOCO 2 VALIDADO COM SUCESSO")
