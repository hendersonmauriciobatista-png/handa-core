from core.event_bridge import EventBridge
from core.slot_manager import SlotManager
import time

event_bridge = EventBridge()

def debug_listener(payload):
    print(
        f"[SLOT {payload['slot_id']}] "
        f"{payload['state']} | PnL={payload['pnl']}"
    )

event_bridge.subscribe("slot_update", debug_listener)

manager = SlotManager(event_bridge=event_bridge, num_slots=3)
manager.start()

try:
    time.sleep(10)
finally:
    manager.stop_all()
    print("STOPPED")
