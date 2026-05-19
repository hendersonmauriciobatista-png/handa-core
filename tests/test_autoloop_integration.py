import threading
import time

from core.slot_controller import SlotController
from core.loop.auto_loop import AutoLoop


def test_autoloop_executes_decision_cycle():

    controller = SlotController(slot_ids=[1], cooldown=0.1)

    loop = AutoLoop(
        slot_controller=controller,
        interval_seconds=0.1,
    )

    thread = threading.Thread(target=loop.start, daemon=True)
    thread.start()

    time.sleep(0.3)

    loop.stop()
    thread.join(timeout=1)

    assert loop.cycle >= 1
    assert loop.running is False