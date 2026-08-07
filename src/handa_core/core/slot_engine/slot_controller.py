from .slot_state_machine import SlotState, TradingMode, CooldownType
from .cooldown_manager import CooldownManager
from .armed_validator import ArmedValidator


class SlotController:

    def __init__(self, slot_id: int):
        self.slot_id = slot_id
        self.state = SlotState.IDLE
        self.trading_mode = None
        self.current_asset = None

        self.cooldown_manager = CooldownManager()
        self.armed_validator = ArmedValidator()

    # -------------------------
    # Asset Management
    # -------------------------

    def assign_asset(self, asset: str):
        self.current_asset = asset
        self.state = SlotState.ANALYZING

    def get_current_asset(self):
        return self.current_asset

    def get_state(self):
        return self.state

    # -------------------------
    # State Transitions
    # -------------------------

    def arm(self):
        if self.state == SlotState.ANALYZING:
            self.state = SlotState.ARMED
            self.armed_validator.reset()

    def register_armed_cycle(self):
        if self.state == SlotState.ARMED:
            self.armed_validator.register_cycle()
            if not self.armed_validator.is_valid():
                self.state = SlotState.ANALYZING

    def execute_trade(self):
        if self.state == SlotState.ARMED:
            self.state = SlotState.TRADING
            self.trading_mode = TradingMode.NORMAL

    def activate_protecting(self):
        if self.state == SlotState.TRADING:
            self.trading_mode = TradingMode.PROTECTING

    def exit_trade(self):
        if self.state == SlotState.TRADING:
            self.trading_mode = TradingMode.EXITING

    def enter_cooldown(self, cooldown_type: CooldownType):
        self.state = SlotState.COOLDOWN
        self.cooldown_manager.activate(cooldown_type)

    def reset_after_cooldown(self):
        if self.state == SlotState.COOLDOWN:
            self.cooldown_manager.reset()
            self.state = SlotState.ANALYZING

    def pause(self):
        self.state = SlotState.PAUSED

    def error(self):
        self.state = SlotState.ERROR
