import random
import time
from core_logic.system import SystemState
from core_logic.enums import SystemMode, ConnectionState


PAIRS = ["BTC/USDC", "ETH/USDC", "BNB/USDC", "SOL/USDC"]


def run_simulation(cycles: int = 10, slot_count: int = 3, delay: float = 0.2):
    system = SystemState(slot_count=slot_count)
    system.set_mode(SystemMode.MOCK)
    system.set_connection(ConnectionState.CONNECTED)

    print("=== SIMULAÇÃO INICIADA ===")
    print(system.snapshot())
    print()

    for i in range(1, cycles + 1):
        slot_id = random.randint(1, slot_count)
        slot = system.get_slot(slot_id)
        pair = random.choice(PAIRS)

        print(f"[CICLO {i}] Slot {slot_id} | Par {pair}")

        try:
            slot.start_analysis(pair)
            print("  - Análise iniciada")

            # 70% chance de sinal
            if random.random() < 0.7:
                slot.analysis_signal_found()
                print("  - Sinal encontrado")

                slot.start_trading()
                print("  - Trading iniciado")

                # 85% chance de sucesso
                if random.random() < 0.85:
                    slot.trading_completed()
                    print("  - Trading COMPLETO")
                else:
                    slot.trading_aborted()
                    print("  - Trading ABORTADO")
            else:
                slot.analysis_rejected()
                print("  - Análise rejeitada")

        except Exception as e:
            print("  ! ERRO:", e)

        print("  Snapshot:", slot.snapshot())
        print()
        time.sleep(delay)

    print("=== SIMULAÇÃO FINALIZADA ===")
    print(system.snapshot())


if __name__ == "__main__":
    run_simulation(cycles=12, slot_count=3, delay=0.1)
