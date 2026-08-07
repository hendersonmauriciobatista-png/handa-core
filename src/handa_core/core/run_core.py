# core/run_core.py
import time

from core.slot_controller import SlotController


def main():
    slot_controller = SlotController(
        slot_ids=[1,2,3,4,5,6,7,8,9,10,11,12]
    )

    # LIGA O SISTEMA
    slot_controller.start_all()

    print("[CORE] SlotController LIVE iniciado")

    # LOOP CENTRAL
    while True:
        slot_controller.tick()
        time.sleep(1)


if __name__ == "__main__":
    main()
