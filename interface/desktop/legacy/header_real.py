# ============================================================
# header_real.py
# Arquitetura base do modo REAL (produção)
# Sistema: H&A + ALFRED IA
# ------------------------------------------------------------
# ❌ sem engine
# ❌ sem lógica
# ❌ sem integração externa
# ❌ sem execução real
# ❌ sem risco
#
# ✅ modular
# ✅ organizado por áreas
# ✅ containers reais
# ✅ compatível com a planta
# ✅ preparado para LIVE MODE
# ============================================================


# ============================================================
# GLOBAL STATE CONTAINER
# ============================================================

class GlobalState:
    def __init__(self):
        self.mode = "REAL"              # REAL | MOCK
        self.connected = False
        self.auto_mode = False
        self.safe_stop = False
        self.engine_loaded = False
        self.integration_loaded = False
        self.system_ready = False
        self.global_lock = False
        self.status = "BOOT"
        self.errors = []
        self.warnings = []

    def snapshot(self):
        return {
            "mode": self.mode,
            "connected": self.connected,
            "auto_mode": self.auto_mode,
            "safe_stop": self.safe_stop,
            "engine_loaded": self.engine_loaded,
            "integration_loaded": self.integration_loaded,
            "system_ready": self.system_ready,
            "global_lock": self.global_lock,
            "status": self.status,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ============================================================
# MODE CONTAINER
# ============================================================

class ModeContainer:
    def __init__(self):
        self.current_mode = "REAL"
        self.allowed_modes = ["REAL", "MOCK"]

    def set_mode(self, mode: str):
        self.current_mode = mode

    def get_mode(self):
        return self.current_mode


# ============================================================
# CONNECTION CONTAINER
# ============================================================

class ConnectionContainer:
    def __init__(self):
        self.api_connected = False
        self.socket_connected = False
        self.last_heartbeat = None
        self.latency = None
        self.status = "DISCONNECTED"

    def snapshot(self):
        return {
            "api": self.api_connected,
            "socket": self.socket_connected,
            "heartbeat": self.last_heartbeat,
            "latency": self.latency,
            "status": self.status
        }


# ============================================================
# BALANCE CONTAINER
# ============================================================

class BalanceContainer:
    def __init__(self):
        self.total_usdc = 0.0
        self.available_usdc = 0.0
        self.locked_usdc = 0.0
        self.positions = {}
        self.last_update = None

    def snapshot(self):
        return {
            "total_usdc": self.total_usdc,
            "available_usdc": self.available_usdc,
            "locked_usdc": self.locked_usdc,
            "positions": self.positions,
            "last_update": self.last_update
        }


# ============================================================
# PROFIT CONTAINER
# ============================================================

class ProfitContainer:
    def __init__(self):
        self.realized_profit = 0.0
        self.unrealized_profit = 0.0
        self.daily_profit = 0.0
        self.weekly_profit = 0.0
        self.monthly_profit = 0.0
        self.history = []

    def snapshot(self):
        return {
            "realized": self.realized_profit,
            "unrealized": self.unrealized_profit,
            "daily": self.daily_profit,
            "weekly": self.weekly_profit,
            "monthly": self.monthly_profit,
            "history": self.history
        }


# ============================================================
# AUTO MODE CONTAINER
# ============================================================

class AutoContainer:
    def __init__(self):
        self.enabled = False
        self.auto_entry = False
        self.auto_exit = False
        self.auto_reinvest = False
        self.auto_pair_selection = False

    def snapshot(self):
        return {
            "enabled": self.enabled,
            "auto_entry": self.auto_entry,
            "auto_exit": self.auto_exit,
            "auto_reinvest": self.auto_reinvest,
            "auto_pair_selection": self.auto_pair_selection
        }


# ============================================================
# SAFE STOP CONTAINER
# ============================================================

class SafeStopContainer:
    def __init__(self):
        self.active = False
        self.mode = "NONE"          # NONE | DRAINING | HARDSTOP | EMERGENCY
        self.lock_trades = False
        self.allow_close_only = False
        self.reason = None
        self.triggered_at = None

    def snapshot(self):
        return {
            "active": self.active,
            "mode": self.mode,
            "lock_trades": self.lock_trades,
            "allow_close_only": self.allow_close_only,
            "reason": self.reason,
            "triggered_at": self.triggered_at
        }


# ============================================================
# STATUS CONTAINER
# ============================================================

class StatusContainer:
    def __init__(self):
        self.system = "INIT"
        self.engine = "OFF"
        self.integration = "OFF"
        self.ui = "OFF"
        self.slots = {}
        self.health = "UNKNOWN"
        self.last_check = None

    def snapshot(self):
        return {
            "system": self.system,
            "engine": self.engine,
            "integration": self.integration,
            "ui": self.ui,
            "slots": self.slots,
            "health": self.health,
            "last_check": self.last_check
        }


# ============================================================
# REAL HEADER ROOT CONTAINER
# ============================================================

class RealHeader:
    """
    Container mestre do modo REAL.
    Nenhuma lógica operacional.
    Nenhuma integração.
    Nenhuma engine.
    Apenas estrutura e estado.
    """

    def __init__(self):
        self.global_state = GlobalState()

        # Core domains
        self.mode = ModeContainer()
        self.connection = ConnectionContainer()
        self.balance = BalanceContainer()
        self.profit = ProfitContainer()
        self.auto = AutoContainer()
        self.safe_stop = SafeStopContainer()
        self.status = StatusContainer()

        # Flags de arquitetura
        self.engine_attached = False
        self.integration_attached = False
        self.live_ready = False

    def snapshot(self):
        return {
            "global": self.global_state.snapshot(),
            "mode": self.mode.get_mode(),
            "connection": self.connection.snapshot(),
            "balance": self.balance.snapshot(),
            "profit": self.profit.snapshot(),
            "auto": self.auto.snapshot(),
            "safe_stop": self.safe_stop.snapshot(),
            "status": self.status.snapshot(),
            "engine_attached": self.engine_attached,
            "integration_attached": self.integration_attached,
            "live_ready": self.live_ready
        }


# ============================================================
# EXPORT ROOT
# ============================================================

REAL_HEADER = RealHeader()
