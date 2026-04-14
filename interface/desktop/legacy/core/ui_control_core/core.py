# core.py
# ==============================
# UI Control Core — Core Orchestrator
# FASE 1: Controle Humano
# Sistema: H&A / ALFRED IA
# ==============================

from copy import deepcopy

from .state import UIControlState
from .slot_state import SlotControlState
from .control_bus import ControlBus, ControlEvent
from .authority_manager import AuthorityManager, ActionSource
from .pin_manager import PinManager
from .lock_manager import LockManager
from .override_manager import OverrideManager
from .focus_manager import FocusManager
from .conflict_resolver import ConflictResolver
from .exception_handler import ExceptionHandler
from .governance import Governance


class UIControlCore:
    """
    Núcleo central da FASE 1.
    Orquestra controle humano, foco, autoridade, proteção, conflitos e governança.
    """

    def __init__(self):
        # Estado global
        self.ui_state = UIControlState()

        # Estados por slot
        self.slots: dict[str, SlotControlState] = {}

        # Infraestrutura
        self.bus = ControlBus()
        self.authority = AuthorityManager()
        self.conflicts = ConflictResolver()
        self.exceptions = ExceptionHandler()
        self.governance = Governance()

        # Managers
        self.pin_manager = PinManager(self.ui_state)
        self.lock_manager = LockManager()
        self.override_manager = OverrideManager()
        self.focus_manager = FocusManager()

        # Subscreve o core no bus
        self.bus.subscribe(self)

    # ==============================
    # Slots
    # ==============================

    def register_slot(self, slot_id: str):
        if slot_id not in self.slots:
            self.slots[slot_id] = SlotControlState(slot_id)

    def remove_slot(self, slot_id: str):
        if slot_id in self.slots:
            # Remove pin se for o slot pinado
            if self.ui_state.pinned_slot == slot_id:
                self.pin_manager.unpin()
            del self.slots[slot_id]

    # ==============================
    # Event Handler
    # ==============================

    def handle(self, event: ControlEvent):
        """
        Handler central de eventos do ControlBus.
        """

        # Snapshot anterior (auditoria)
        before_state = deepcopy(self.ui_state.to_dict())

        # ------------------------------
        # Governança institucional
        # ------------------------------
        if not self.governance.validate_action(event, self.ui_state):
            return

        # ------------------------------
        # Autoridade
        # ------------------------------
        if not self.authority.allow(event.source, self.ui_state):
            return

        # ------------------------------
        # Resolução de conflitos
        # ------------------------------
        resolved = self.conflicts.resolve(event, self.ui_state)
        if resolved is None:
            # Evento bloqueado
            self.exceptions.handle(None, self.ui_state)
            return

        # ------------------------------
        # Roteamento de eventos
        # ------------------------------
        name = resolved.name
        payload = resolved.payload

        if name == "PIN":
            self.pin_manager.pin(payload.get("slot_id"))

        elif name == "UNPIN":
            self.pin_manager.unpin()

        elif name == "LOCK":
            slot = self.slots.get(payload.get("slot_id"))
            if slot:
                self.lock_manager.lock(slot, reason=payload.get("reason", "manual"))

        elif name == "UNLOCK":
            slot = self.slots.get(payload.get("slot_id"))
            if slot:
                self.lock_manager.unlock(slot)

        elif name == "OVERRIDE_ON":
            self.override_manager.activate(self.ui_state)

        elif name == "OVERRIDE_OFF":
            self.override_manager.deactivate(self.ui_state)

        elif name == "AUTO_FOCUS":
            self.focus_manager.update_focus(
                self.ui_state,
                auto_focus_slot=payload.get("slot_id")
            )

        elif name == "RESET":
            self._reset_control_state()

        # ------------------------------
        # Exceções / Consistência
        # ------------------------------
        self.exceptions.handle(resolved, self.ui_state)

        # ------------------------------
        # Auditoria
        # ------------------------------
        after_state = deepcopy(self.ui_state.to_dict())
        _audit = self.governance.audit(resolved, before_state, after_state)
        # Aqui futuramente: persistir log, enviar para debug, storage, etc.

    # ==============================
    # API Pública (para UI Controller)
    # ==============================

    def dispatch(self, name: str, source: str, payload: dict | None = None):
        """
        API única para envio de eventos ao núcleo.
        """
        event = ControlEvent(name=name, source=source, payload=payload)
        self.bus.dispatch(event)

    # ==============================
    # Utilitários
    # ==============================

    def get_ui_state(self) -> UIControlState:
        return self.ui_state

    def get_slot_state(self, slot_id: str) -> SlotControlState | None:
        return self.slots.get(slot_id)

    def _reset_control_state(self):
        """
        Reset interno de controle (ação humana).
        """
        self.ui_state.focus_mode = "auto"
        self.ui_state.pinned_slot = None
        self.ui_state.operator_override = False
        self.ui_state.active_center = None
