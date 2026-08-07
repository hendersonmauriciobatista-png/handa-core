"""
UIAdvisor — Bridge LIVE definitiva da Interface Desktop

Responsabilidade:
- Receber eventos da UI e/ou do CORE
- Atualizar a fonte de verdade da UI (UIStateRegistry)
- Encaminhar eventos ao CORE quando disponível
- FAIL-SAFE: nunca quebrar a UI

Regras:
- NÃO decide
- NÃO executa
- NÃO cria estado falso
"""

from typing import Any, Dict, Optional
import traceback

# -----------------------------------------
# Logger (silencioso e seguro)
# -----------------------------------------
def _get_logger():
    try:
        from core.logger import get_logger
        return get_logger("UIAdvisor")
    except Exception:
        class _PrintLogger:
            def info(self, msg): pass
            def warn(self, msg): pass
            def error(self, msg): print(f"[UIAdvisor][ERROR] {msg}")
        return _PrintLogger()

logger = _get_logger()

# -----------------------------------------
# Fonte de verdade da UI
# -----------------------------------------
from interface.desktop.core.ui_state_registry import ui_state_registry

# -----------------------------------------
# Loader do Alfred Advisor (CORE) — opcional
# -----------------------------------------
def _load_core_advisor():
    try:
        from core.alfred_advisor.advisor import AlfredAdvisor
        return AlfredAdvisor()
    except Exception:
        return None


class UIAdvisor:
    """
    Bridge LIVE passiva entre UI Desktop e CORE.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.core_advisor = _load_core_advisor()

    # -------------------------------------
    # Envio seguro ao CORE
    # -------------------------------------
    def _safe_send(self, event: str, payload: Dict[str, Any]):
        if not self.enabled or not self.core_advisor:
            return
        try:
            if hasattr(self.core_advisor, "observe"):
                self.core_advisor.observe(event=event, data=payload)
        except Exception:
            logger.error(traceback.format_exc())

    # -------------------------------------
    # Eventos públicos (LIVE)
    # -------------------------------------
    def on_ui_init(self, context: Dict[str, Any]):
        self._safe_send("ui_init", context)

    def on_theme_applied(self, theme_snapshot: Dict[str, Any]):
        self._safe_send("theme_applied", theme_snapshot)

    def on_slot_state(
        self,
        slot_id: int,
        state: str,
        extra: Optional[Dict[str, Any]] = None
    ):
        """
        Evento LIVE de estado do slot.
        Este é o ponto único de entrada.
        """

        payload = {
            "slot_id": slot_id,
            "state": state,
            "extra": extra or {}
        }

        # Atualiza a UI (fonte de verdade)
        ui_state_registry.update_slot_state(
            slot_id=slot_id,
            state=state,
            extra=extra
        )

        # Encaminha ao CORE (se existir)
        self._safe_send("slot_state", payload)

    def on_ui_error(self, err: Exception, context: Optional[Dict[str, Any]] = None):
        payload = {
            "error": repr(err),
            "traceback": traceback.format_exc(),
            "context": context or {}
        }
        self._safe_send("ui_error", payload)
