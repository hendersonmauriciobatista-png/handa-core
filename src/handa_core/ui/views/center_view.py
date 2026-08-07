"""
CenterView
Área central da UI.

Comportamento:
- Estado padrão: exibe logo H&A (marca d’água) + texto calmo
- Ao focar um slot: exibe detalhes por 8 segundos
- Após 8s: retorna automaticamente à logo
- NÃO recebe comandos
"""

import time


class CenterView:
    FOCUS_DURATION = 8  # segundos

    def __init__(self):
        self.focus_slot_id = None
        self.focus_start_time = None

    # =========================
    # Controle de Foco
    # =========================
    def focus_slot(self, slot_id: str):
        """Ativa foco temporário em um slot."""
        self.focus_slot_id = slot_id
        self.focus_start_time = time.time()

    def _focus_expired(self) -> bool:
        if not self.focus_start_time:
            return True
        return (time.time() - self.focus_start_time) >= self.FOCUS_DURATION

    def _clear_focus_if_needed(self):
        if self.focus_slot_id and self._focus_expired():
            self.focus_slot_id = None
            self.focus_start_time = None

    # =========================
    # Renderização
    # =========================
    def render(self, state: dict):
        self._clear_focus_if_needed()

        print("\n" + "=" * 60)
        print(" CENTRO ")
        print("-" * 60)

        if self.focus_slot_id:
            self._render_slot_focus(state)
        else:
            self._render_logo()

        print("=" * 60)

    def _render_logo(self):
        """
        Render padrão: logo H&A (stub textual).
        """
        print("      H&A")
        print("  Interface de Observação")
        print("")
        print(" Sistema operando normalmente")
        print(" Nenhuma ação necessária")

    def _render_slot_focus(self, state: dict):
        """
        Render do foco temporário do slot.
        """
        slots = state.get("slots", {})
        slot = slots.get(self.focus_slot_id)

        if not slot:
            print(" Slot não encontrado")
            return

        remaining = max(
            0,
            self.FOCUS_DURATION - int(time.time() - self.focus_start_time)
        )

        print(f" Slot em foco : {self.focus_slot_id}")
        print(f" Estado       : {slot.get('state', 'UNKNOWN')}")
        print(f" Par          : {slot.get('pair') or '-'}")
        print(f" Última ação  : {slot.get('last_action', '-')}")
        print(f" Última atualização : {time.strftime('%H:%M:%S', time.localtime(slot.get('last_update', 0)))}")
        print("")
        print(f" Retornando à visão geral em {remaining}s")
