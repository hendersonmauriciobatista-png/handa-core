# =====================================================
# interface/desktop/ui_control.py
# UI Control — Camada Visual (ANSI + Animações)
# FASE 2 — READ-ONLY (STATE-DRIVEN)
# =====================================================

import sys
import time


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"

    GRAY = "\033[90m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    ORANGE = "\033[33m"
    PURPLE = "\033[95m"
    RED = "\033[91m"
    DARK = "\033[37m"


SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

# =====================================================
# MAPA DE ESTADO (CORE) -> EVENTO VISUAL (UI)
# =====================================================

SLOT_STATUS_TO_EVENT = {
    "IDLE": "SLOT_IDLE",
    "TRADING": "SLOT_TRADING",
    "STOPPED": "SLOT_STOPPED",
    "ERROR": "SLOT_ERROR",
}

# =====================================================
# CORE VISUAL (INALTERADO)
# =====================================================

class UIControlCore:
    """
    UI Console avançada:
    - cores ANSI
    - spinner por estado
    - slots renderizados em linhas fixas
    """

    def __init__(self):
        self.slots = {}
        self._tick = 0

        self.state_style = {
            "SLOT_IDLE":        {"color": ANSI.GRAY,   "anim": None},
            "SLOT_ANALYZING":   {"color": ANSI.BLUE,   "anim": "spin"},
            "SLOT_READY":       {"color": ANSI.GREEN,  "anim": None},
            "SLOT_ENTERING":    {"color": ANSI.YELLOW, "anim": "blink"},
            "SLOT_TRADING":     {"color": ANSI.GREEN,  "anim": "spin"},
            "SLOT_EXITING":     {"color": ANSI.ORANGE, "anim": "spin"},
            "SLOT_FINALIZING":  {"color": ANSI.PURPLE, "anim": "fade"},
            "SLOT_STOPPED":     {"color": ANSI.DARK,   "anim": None},
            "SLOT_ERROR":       {"color": ANSI.RED,    "anim": "blink"},
        }

    # -------------------------------------------------
    # DISPATCH (EVENTO VISUAL)
    # -------------------------------------------------

    def dispatch(self, name: str, payload: dict):
        slot_id = payload.get("slot_id")
        if slot_id is None:
            return

        self.slots[str(slot_id)] = {
            "state": name,
            "style": self.state_style.get(name, {}),
        }

        self.render_all()

    # -------------------------------------------------
    # RENDER FIXO
    # -------------------------------------------------

    def render_all(self):
        self._tick += 1
        sys.stdout.write("\033[H")  # move cursor para o topo

        for slot_id in sorted(self.slots.keys(), key=lambda x: int(x)):
            self._render_slot(slot_id)

        sys.stdout.flush()

    def _render_slot(self, slot_id: str):
        slot = self.slots[slot_id]
        state = slot["state"].replace("SLOT_", "")
        style = slot["style"]

        color = style.get("color", "")
        anim = style.get("anim")

        spinner = ""
        if anim == "spin":
            spinner = SPINNER[self._tick % len(SPINNER)]
        elif anim == "blink":
            spinner = "●" if self._tick % 2 == 0 else " "
        elif anim == "fade":
            spinner = "…"

        line = (
            f"{color}{ANSI.BOLD}"
            f"Slot {slot_id:<2} | {spinner} {state:<11}"
            f"{ANSI.RESET}"
        )

        print(line)


# =====================================================
# CONTROLLER (READ-ONLY / STATE-DRIVEN)
# =====================================================

class UIControl:
    """
    Controlador da UI (FASE 2):
    - Consome snapshot READ-ONLY
    - Traduz estado -> evento visual
    - Não executa comandos
    """

    def __init__(self):
        self.core = UIControlCore()

    def start(self):
        # limpa tela e posiciona cursor
        print("\033[2J\033[H", end="")
        print("[UI CONTROL] UI iniciada (READ-ONLY / STATE-DRIVEN)")

    def update_from_snapshot(self, snapshot: dict):
        """
        Espera:
        snapshot = {
            "slots": [
                {"slot_id": "1", "status": "IDLE"},
                {"slot_id": "2", "status": "TRADING"},
                ...
            ]
        }
        """
        slots = snapshot.get("slots", [])
        if not isinstance(slots, list):
            return

        for slot in slots:
            slot_id = slot.get("slot_id")
            status = slot.get("status")

            if slot_id is None or status is None:
                continue

            event = SLOT_STATUS_TO_EVENT.get(str(status), "SLOT_IDLE")
            self.core.dispatch(event, {"slot_id": str(slot_id)})


# =====================================================
# SINGLETON
# =====================================================

ui_control = UIControl()
