# ============================================================
# router_real.py
# Roteador estrutural do modo REAL
# Sistema: H&A + ALFRED IA
# ------------------------------------------------------------
# ❌ sem engine
# ❌ sem execução
# ❌ sem integração externa
# ❌ sem lógica de trade
# ❌ sem risco
#
# ✅ roteamento de estado
# ✅ organização de fluxos
# ✅ compatível com header_real.py
# ✅ preparado para LIVE MODE
# ============================================================

from .header_real import REAL_HEADER





# ============================================================
# ROUTER CORE
# ============================================================

class RealRouter:
    """
    Router estrutural do modo REAL.
    Atua apenas como organizador de estado e fluxo.
    Nenhuma decisão.
    Nenhuma execução.
    Nenhuma integração.
    """

    def __init__(self, header):
        self.header = header
        self.routes = {}

    # ========================================================
    # REGISTRO DE ROTAS
    # ========================================================

    def register_route(self, name: str, handler):
        self.routes[name] = handler

    def unregister_route(self, name: str):
        if name in self.routes:
            del self.routes[name]

    # ========================================================
    # DISPATCH
    # ========================================================

    def dispatch(self, route_name: str, payload: dict = None):
        if route_name not in self.routes:
            return {
                "ok": False,
                "error": f"Route '{route_name}' not registered"
            }

        handler = self.routes[route_name]

        # Sem lógica, sem decisão, sem execução
        return handler(self.header, payload or {})

    # ========================================================
    # SNAPSHOT GLOBAL
    # ========================================================

    def snapshot(self):
        return self.header.snapshot()


# ============================================================
# ROUTE HANDLERS (ESTRUTURAIS)
# ============================================================

# ---- MODE ---------------------------------------------------

def route_set_mode(header, payload):
    mode = payload.get("mode")
    header.mode.set_mode(mode)
    header.global_state.mode = mode
    return {"ok": True, "mode": mode}


# ---- CONNECTION --------------------------------------------

def route_connection_status(header, payload):
    header.connection.api_connected = payload.get("api", False)
    header.connection.socket_connected = payload.get("socket", False)
    header.connection.last_heartbeat = payload.get("heartbeat")
    header.connection.latency = payload.get("latency")
    header.connection.status = payload.get("status", "UNKNOWN")

    header.global_state.connected = header.connection.api_connected
    return {"ok": True}


# ---- BALANCE -----------------------------------------------

def route_balance_update(header, payload):
    header.balance.total_usdc = payload.get("total_usdc", 0.0)
    header.balance.available_usdc = payload.get("available_usdc", 0.0)
    header.balance.locked_usdc = payload.get("locked_usdc", 0.0)
    header.balance.positions = payload.get("positions", {})
    header.balance.last_update = payload.get("timestamp")
    return {"ok": True}


# ---- PROFIT -------------------------------------------------

def route_profit_update(header, payload):
    header.profit.realized_profit = payload.get("realized", 0.0)
    header.profit.unrealized_profit = payload.get("unrealized", 0.0)
    header.profit.daily_profit = payload.get("daily", 0.0)
    header.profit.weekly_profit = payload.get("weekly", 0.0)
    header.profit.monthly_profit = payload.get("monthly", 0.0)
    header.profit.history.append(payload.get("event"))
    return {"ok": True}


# ---- AUTO MODE ---------------------------------------------

def route_auto_update(header, payload):
    header.auto.enabled = payload.get("enabled", False)
    header.auto.auto_entry = payload.get("auto_entry", False)
    header.auto.auto_exit = payload.get("auto_exit", False)
    header.auto.auto_reinvest = payload.get("auto_reinvest", False)
    header.auto.auto_pair_selection = payload.get("auto_pair_selection", False)
    return {"ok": True}


# ---- SAFE STOP ---------------------------------------------

def route_safe_stop(header, payload):
    header.safe_stop.active = payload.get("active", False)
    header.safe_stop.mode = payload.get("mode", "NONE")
    header.safe_stop.lock_trades = payload.get("lock_trades", False)
    header.safe_stop.allow_close_only = payload.get("allow_close_only", False)
    header.safe_stop.reason = payload.get("reason")
    header.safe_stop.triggered_at = payload.get("timestamp")

    header.global_state.safe_stop = header.safe_stop.active
    return {"ok": True}


# ---- STATUS -------------------------------------------------

def route_status_update(header, payload):
    header.status.system = payload.get("system", "UNKNOWN")
    header.status.engine = payload.get("engine", "OFF")
    header.status.integration = payload.get("integration", "OFF")
    header.status.ui = payload.get("ui", "OFF")
    header.status.slots = payload.get("slots", {})
    header.status.health = payload.get("health", "UNKNOWN")
    header.status.last_check = payload.get("timestamp")
    return {"ok": True}


# ---- ARCH FLAGS --------------------------------------------

def route_attach_engine(header, payload):
    header.engine_attached = True
    header.global_state.engine_loaded = True
    return {"ok": True}


def route_attach_integration(header, payload):
    header.integration_attached = True
    header.global_state.integration_loaded = True
    return {"ok": True}


def route_live_ready(header, payload):
    header.live_ready = True
    header.global_state.system_ready = True
    header.global_state.status = "LIVE_READY"
    return {"ok": True}


# ============================================================
# ROUTER FACTORY
# ============================================================

def build_real_router():
    router = RealRouter(REAL_HEADER)

    # Register routes
    router.register_route("set_mode", route_set_mode)
    router.register_route("connection", route_connection_status)
    router.register_route("balance", route_balance_update)
    router.register_route("profit", route_profit_update)
    router.register_route("auto", route_auto_update)
    router.register_route("safe_stop", route_safe_stop)
    router.register_route("status", route_status_update)
    router.register_route("attach_engine", route_attach_engine)
    router.register_route("attach_integration", route_attach_integration)
    router.register_route("live_ready", route_live_ready)

    return router


# ============================================================
# EXPORT ROUTER
# ============================================================

REAL_ROUTER = build_real_router()

