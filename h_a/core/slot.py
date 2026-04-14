from enum import Enum, auto
from ..strategy.ema_rsi_strategy import EMARsiStrategy



class SlotState(Enum):
    IDLE = auto()
    ANALYZING = auto()
    READY = auto()
    ENTERING = auto()
    TRADING = auto()
    EXITING = auto()
    FINALIZING = auto()
    STOPPED = auto()
    ERROR = auto()


class Slot:
    """
    Slot real com Strategy real (EMA + RSI).
    Máquina de estados determinística.
    """

    def __init__(self, slot_id: int, event_bus):
        self.slot_id = slot_id
        self.event_bus = event_bus
        self.state = SlotState.IDLE

        # Strategy plugável
        self.strategy = EMARsiStrategy()

        # dados internos (mock de market data)
        self.market_data = {
            "ema_fast": 105,
            "ema_slow": 100,
            "rsi": 55,
        }

        self.price = None
        self.pnl = 0.0

    # ==================================================
    # API PÚBLICA
    # ==================================================

    def step(self):
        try:
            if self.state == SlotState.IDLE:
                self._to_analyzing()

            elif self.state == SlotState.ANALYZING:
                self._analyze()

            elif self.state == SlotState.READY:
                self._enter()

            elif self.state == SlotState.ENTERING:
                self._confirm_entry()

            elif self.state == SlotState.TRADING:
                self._monitor()

            elif self.state == SlotState.EXITING:
                self._exit()

            elif self.state == SlotState.FINALIZING:
                self._finalize()

            elif self.state in (SlotState.STOPPED, SlotState.ERROR):
                return

        except Exception:
            self._set_state(SlotState.ERROR)

    # ==================================================
    # TRANSIÇÕES (COM STRATEGY)
    # ==================================================

    def _to_analyzing(self):
        self._set_state(SlotState.ANALYZING)

    def _analyze(self):
        if self.strategy.should_enter(self.market_data):
            self._set_state(SlotState.READY)
        else:
            self._set_state(SlotState.IDLE)

    def _enter(self):
        self._set_state(SlotState.ENTERING)

    def _confirm_entry(self):
        success = True
        if success:
            self._set_state(SlotState.TRADING)
        else:
            self._set_state(SlotState.ANALYZING)

    def _monitor(self):
        if self.strategy.should_exit(self.market_data):
            self._set_state(SlotState.EXITING)

    def _exit(self):
        success = True
        if success:
            self._set_state(SlotState.FINALIZING)
        else:
            self._set_state(SlotState.TRADING)

    def _finalize(self):
        self._reset_trade_data()
        self._set_state(SlotState.IDLE)

    # ==================================================
    # HELPERS
    # ==================================================

    def _reset_trade_data(self):
        self.price = None
        self.pnl = 0.0

    # ==================================================
    # EVENTOS
    # ==================================================

    def _set_state(self, new_state: SlotState):
        self.state = new_state
        self._emit_state()

    def _emit_state(self):
        self.event_bus.emit(
            "STATE_CHANGED",
            entity_type="Slot",
            entity_id=self.slot_id,
            state=self.state.name,
            payload={
                "price": self.price,
                "pnl": self.pnl,
            },
        )
