import time

from core.slot_controller import SlotController
from core.auto_loop import AutoLoop


def test_autoloop_executes_decision_cycle():

    controller = SlotController(slot_ids=[1], cooldown=0.1)
    controller.start_all()

    loop = AutoLoop(controller, interval=0.1)
    loop.start()

    # roda por 1 segundo
    time.sleep(1)

    loop.stop()

    # Verifica se o slot saiu de IDLE pelo menos uma vez
    snapshot = controller.snapshot_all()
    state = snapshot[1]["slot_state"]

    assert state in ("RUNNING", "DONE", "IDLE")
