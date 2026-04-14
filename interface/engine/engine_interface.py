# ============================================================
# engine_interface.py
# Contrato da Engine (Interface estrutural)
# Sistema: H&A + ALFRED IA
# ------------------------------------------------------------
# ❌ sem lógica
# ❌ sem execução
# ❌ sem integração
# ❌ sem risco
# ❌ sem trading
#
# ✅ contrato da engine
# ✅ estrutura de métodos
# ✅ estados
# ✅ lifecycle
# ✅ compatível com REAL MODE
# ✅ compatível com router_real
# ============================================================


class EngineState:
    """
    Estado interno da engine.
    Nenhuma lógica operacional.
    Apenas estrutura de estado.
    """

    def __init__(self):
        self.loaded = False
        self.initialized = False
        self.running = False
        self.paused = False
        self.stopped = True
        self.safe_mode = False
        self.last_tick = None
        self.last_error = None
        self.status = "OFF"


class EngineInterface:
    """
    Interface base da Engine.
    Serve como contrato para qualquer engine real.
    (mock, simulação, live, backtest, paper, real money)
    """

    def __init__(self):
        self.state = EngineState()
        self.bound_router = None
        self.bound_header = None

    # ========================================================
    # BINDINGS
    # ========================================================

    def bind_router(self, router):
        """Vincula a engine ao router (sem execução)"""
        self.bound_router = router

    def bind_header(self, header):
        """Vincula a engine ao header (sem execução)"""
        self.bound_header = header

    # ========================================================
    # LIFECYCLE (CONTRATO)
    # ========================================================

    def load(self):
        """Carregamento da engine (stub)"""
        self.state.loaded = True
        self.state.status = "LOADED"

    def initialize(self):
        """Inicialização da engine (stub)"""
        self.state.initialized = True
        self.state.status = "INITIALIZED"

    def start(self):
        """Início da engine (stub)"""
        self.state.running = True
        self.state.stopped = False
        self.state.status = "RUNNING"

    def pause(self):
        """Pausa da engine (stub)"""
        self.state.paused = True
        self.state.status = "PAUSED"

    def resume(self):
        """Retomar engine (stub)"""
        self.state.paused = False
        self.state.status = "RUNNING"

    def stop(self):
        """Parada da engine (stub)"""
        self.state.running = False
        self.state.stopped = True
        self.state.status = "STOPPED"

    def shutdown(self):
        """Shutdown total da engine (stub)"""
        self.state.running = False
        self.state.loaded = False
        self.state.initialized = False
        self.state.status = "OFF"

    # ========================================================
    # SAFE MODE
    # ========================================================

    def enable_safe_mode(self):
        self.state.safe_mode = True
        self.state.status = "SAFE_MODE"

    def disable_safe_mode(self):
        self.state.safe_mode = False
        self.state.status = "RUNNING"

    # ========================================================
    # CORE LOOP (CONTRATO)
    # ========================================================

    def tick(self):
        """
        Ciclo base da engine.
        (stub — sem lógica)
        """
        self.state.last_tick = "TICK"

    # ========================================================
    # INTERFACES OPERACIONAIS (STUBS)
    # ========================================================

    def evaluate_market(self, data):
        """Avaliação de mercado (stub)"""
        raise NotImplementedError

    def generate_signals(self, data):
        """Geração de sinais (stub)"""
        raise NotImplementedError

    def manage_positions(self, state):
        """Gestão de posições (stub)"""
        raise NotImplementedError

    def risk_control(self, context):
        """Controle de risco (stub)"""
        raise NotImplementedError

    def execute_orders(self, orders):
        """Execução de ordens (stub)"""
        raise NotImplementedError

    # ========================================================
    # SNAPSHOT
    # ========================================================

    def snapshot(self):
        return {
            "loaded": self.state.loaded,
            "initialized": self.state.initialized,
            "running": self.state.running,
            "paused": self.state.paused,
            "stopped": self.state.stopped,
            "safe_mode": self.state.safe_mode,
            "status": self.state.status,
            "last_tick": self.state.last_tick,
            "last_error": self.state.last_error,
        }


# ============================================================
# ENGINE REGISTRY
# ============================================================

class EngineRegistry:
    """
    Registro de engines.
    Permite múltiplas implementações:
    - MockEngine
    - SimEngine
    - BacktestEngine
    - PaperEngine
    - LiveEngine
    """

    def __init__(self):
        self.engines = {}

    def register(self, name: str, engine: EngineInterface):
        self.engines[name] = engine

    def get(self, name: str):
        return self.engines.get(name)

    def list(self):
        return list(self.engines.keys())


# ============================================================
# GLOBAL ENGINE REGISTRY
# ============================================================

ENGINE_REGISTRY = EngineRegistry()
