from core.slot_engine.slot_controller import SlotController
from core.slot_engine.slot_state_machine import CooldownType


def run_slot_test():
    slot = SlotController(slot_id=1)

    print("Estado inicial:", slot.get_state())

    # Atribuir ativo
    slot.assign_asset("BTCUSDC")
    print("Após assign:", slot.get_state())

    # Armar
    slot.arm()
    print("Após arm:", slot.get_state())

    # Simular ciclos ARMED
    for i in range(4):
        slot.register_armed_cycle()
        print(f"Ciclo ARMED {i+1}:", slot.get_state())

    # Armar novamente
    slot.arm()
    print("Rearmado:", slot.get_state())

    # Executar trade
    slot.execute_trade()
    print("Após execução:", slot.get_state())

    # Ativar protecting
    slot.activate_protecting()
    print("Modo trading:", slot.trading_mode)

    # Encerrar trade
    slot.exit_trade()
    print("Modo após exit:", slot.trading_mode)

    # Entrar em cooldown
    slot.enter_cooldown(CooldownType.DEFENSIVE)
    print("Entrou em cooldown:", slot.get_state())

    # Reset cooldown
    slot.reset_after_cooldown()
    print("Após reset cooldown:", slot.get_state())


if __name__ == "__main__":
    run_slot_test()
