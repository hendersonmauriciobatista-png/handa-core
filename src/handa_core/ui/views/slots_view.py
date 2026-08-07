"""
SlotsView
Exibe os 12 slots como cartões-resumo (leitura apenas).

Responsabilidades:
- Mostrar Slot ID
- Mostrar estado atual
- Mostrar par (se houver)
- Mostrar última ação
- Mostrar timestamp curto
- NÃO recebe comandos
"""

from datetime import datetime


class SlotsView:
    def __init__(self):
        pass

    def render(self, state: dict):
        slots = state.get("slots", {})

        print("\n" + "-" * 60)
        print(" SLOTS ")
        print("-" * 60)

        if not slots:
            print(" Nenhum slot disponível")
            print("-" * 60)
            return

        # Renderiza em linhas compactas
        for slot_id, slot in slots.items():
            slot_state = slot.get("state", "UNKNOWN")
            pair = slot.get("pair") or "-"
            last_action = slot.get("last_action", "-")
            last_update = slot.get("last_update")

            time_str = (
                datetime.fromtimestamp(last_update).strftime("%H:%M:%S")
                if last_update else "--:--:--"
            )

            print(
                f" {slot_id:<8} | "
                f"Estado: {slot_state:<12} | "
                f"Par: {pair:<10} | "
                f"Ação: {last_action:<20} | "
                f"{time_str}"
            )

        print("-" * 60)
