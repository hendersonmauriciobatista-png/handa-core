# run_live.py
import threading
import time

from core.slot_controller import SlotController
from interface.desktop.app_layout import AppLayout


def start_core(slot_controller: SlotController):
    slot_controller.start_all()
    while True:
        slot_controller.tick()
        time.sleep(1)


def main():
    # CORE
    slot_controller = SlotController(
        slot_ids=[1,2,3,4,5,6,7,8,9,10,11,12]
    )

    core_thread = threading.Thread(
        target=start_core,
        args=(slot_controller,),
        daemon=True
    )
    core_thread.start()

    # UI
    app = AppLayout()
    app.mainloop()


if __name__ == "__main__":
    main()
