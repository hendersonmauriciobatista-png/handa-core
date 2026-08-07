from h_a.core.event_bus import event_bus
from h_a.core.engine_mock import EngineMock


def run():
    engine = EngineMock(event_bus=event_bus)
    engine.create_slot(slot_id=1)

    engine.tick_n(8)


if __name__ == "__main__":
    run()
