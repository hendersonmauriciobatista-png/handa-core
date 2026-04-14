from core.slot_controller import SlotController


def test_1000_cycles_stability():

    controller = SlotController(slot_ids=[1], cooldown=0)
    controller.start_all()

    for _ in range(1000):
        controller.tick()

    snapshot = controller.snapshot_all()
    state = snapshot[1]["slot_state"]

    assert state in ("IDLE", "RUNNING", "DONE")
