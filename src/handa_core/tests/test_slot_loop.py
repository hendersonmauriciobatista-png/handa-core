import time

from h_a.core.slot import Slot
from h_a.core.event_bus import EventBus


def on_state_changed(event: dict):
    """
    Callback padrão para eventos de mudança de estado do Slot.
    O EventBus entrega SEMPRE um único argumento: dict.
    """
    slot_id = event.get("entity_id")
    state = event.get("state")
    payload = event.get("payload", {})

    print(
        f"[EVENT] Slot {slot_id} → {state} | payload={payload}"
    )


def main():
    print("▶ Iniciando loop de teste do Slot...\n")

    bus = EventBus()
    bus.subscribe("STATE_CHANGED", on_state_changed)

    slot = Slot(slot_id=1, event_bus=bus)

    while True:
        slot.step()
        time.sleep(1)


if __name__ == "__main__":
    main()
