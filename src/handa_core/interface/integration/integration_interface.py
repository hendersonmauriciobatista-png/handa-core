# ============================================================
# integration_interface.py
# Contrato de Integração (Interface estrutural)
# Sistema: H&A + ALFRED IA
# ------------------------------------------------------------
# ❌ sem conexão real
# ❌ sem API keys
# ❌ sem WebSocket
# ❌ sem execução
# ❌ sem risco
# ❌ sem trading
#
# ✅ contrato de integração
# ✅ estrutura de métodos
# ✅ estados
# ✅ lifecycle
# ✅ compatível com REAL MODE
# ============================================================


class IntegrationState:
    """
    Estado interno da integração.
    Nenhuma lógica operacional.
    Apenas estrutura de estado.
    """

    def __init__(self):
        self.loaded = False
        self.connected = False
        self.authenticated = False
        self.streaming = False
        self.synced = False
        self.safe_mode = False
        self.last_ping = None
        self.last_error = None
        self.status = "OFF"


class IntegrationInterface:
    """
    Interface base de integração.
    Serve como contrato para integrações reais:
    - Binance
    - Web3
    - APIs externas
    - WebSocket streams
    - Market data feeds
    """

    def __init__(self):
        self.state = IntegrationState()
        self.bound_router = None
        self.bound_header = None
        self.bound_engine = None

    # ========================================================
    # BINDINGS
    # ========================================================

    def bind_router(self, router):
        """Vincula integração ao router (sem execução)"""
        self.bound_router = router

    def bind_header(self, header):
        """Vincula integração ao header (sem execução)"""
        self.bound_header = header

    def bind_engine(self, engine):
        """Vincula integração à engine (sem execução)"""
        self.bound_engine = engine

    # ========================================================
    # LIFECYCLE (CONTRATO)
    # ========================================================

    def load(self):
        self.state.loaded = True
        self.state.status = "LOADED"

    def connect(self):
        self.state.connected = True
        self.state.status = "CONNECTED"

    def authenticate(self):
        self.state.authenticated = True
        self.state.status = "AUTHENTICATED"

    def start_streams(self):
        self.state.streaming = True
        self.state.status = "STREAMING"

    def sync(self):
        self.state.synced = True
        self.state.status = "SYNCED"

    def stop_streams(self):
        self.state.streaming = False
        self.state.status = "CONNECTED"

    def disconnect(self):
        self.state.connected = False
        self.state.status = "DISCONNECTED"

    def shutdown(self):
        self.state = IntegrationState()

    # ========================================================
    # SAFE MODE
    # ========================================================

    def enable_safe_mode(self):
        self.state.safe_mode = True
        self.state.status = "SAFE_MODE"

    def disable_safe_mode(self):
        self.state.safe_mode = False
        self.state.status = "CONNECTED"

    # ========================================================
    # INTERFACES OPERACIONAIS (STUBS)
    # ========================================================

    # ---- MARKET DATA ---------------------------------------

    def fetch_market_data(self, symbol: str):
        raise NotImplementedError

    def subscribe_market_stream(self, symbol: str):
        raise NotImplementedError

    def unsubscribe_market_stream(self, symbol: str):
        raise NotImplementedError

    # ---- ACCOUNT DATA --------------------------------------

    def fetch_balance(self):
        raise NotImplementedError

    def fetch_positions(self):
        raise NotImplementedError

    def fetch_orders(self):
        raise NotImplementedError

    # ---- ORDER FLOW ----------------------------------------

    def send_order(self, order):
        raise NotImplementedError

    def cancel_order(self, order_id):
        raise NotImplementedError

    # ---- SYSTEM --------------------------------------------

    def heartbeat(self):
        raise NotImplementedError

    def ping(self):
        raise NotImplementedError

    # ========================================================
    # SNAPSHOT
    # ========================================================

    def snapshot(self):
        return {
            "loaded": self.state.loaded,
            "connected": self.state.connected,
            "authenticated": self.state.authenticated,
            "streaming": self.state.streaming,
            "synced": self.state.synced,
            "safe_mode": self.state.safe_mode,
            "status": self.state.status,
            "last_ping": self.state.last_ping,
            "last_error": self.state.last_error,
        }


# ============================================================
# INTEGRATION REGISTRY
# ============================================================

class IntegrationRegistry:
    """
    Registro de integrações.
    Permite múltiplas integrações:
    - BinanceIntegration
    - Web3Integration
    - MockIntegration
    - SimIntegration
    """

    def __init__(self):
        self.integrations = {}

    def register(self, name: str, integration: IntegrationInterface):
        self.integrations[name] = integration

    def get(self, name: str):
        return self.integrations.get(name)

    def list(self):
        return list(self.integrations.keys())


# ============================================================
# GLOBAL INTEGRATION REGISTRY
# ============================================================

INTEGRATION_REGISTRY = IntegrationRegistry()
