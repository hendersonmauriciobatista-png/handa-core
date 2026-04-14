import time
from core.slot_controller import SlotController

controller = SlotController(slot_ids=list(range(1, 13)))

controller.start_all()

print("Iniciando teste isolado...\n")

for i in range(15):
    controller.tick()
    snapshot = controller.snapshot_all()

    running = [
        sid for sid, s in snapshot.items()
        if s["analysis_state"] == "RUNNING"
    ]

    print(f"Ciclo {i+1} | RUNNING: {running}")

    time.sleep(1)

print("\nTeste finalizado.")
