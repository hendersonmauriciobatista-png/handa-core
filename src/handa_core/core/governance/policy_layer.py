# ============================================================
# policy_layer.py
# Camada de Política e Segurança do H&A
# ============================================================


class PolicyState:

    def __init__(self):
        self.active = True
        self.safe_mode = True
        self.global_lock = False
        self.live_allowed = False
        self.engine_allowed = False
        self.integration_allowed = False
        self.auto_allowed = False
        self.last_violation = None
        self.status = "INIT"


class PolicyLayer:

    def __init__(self):
        self.state = PolicyState()

    # ========================================================
    # MODOS
    # ========================================================

    def enable_safe_mode(self):
        self.state.safe_mode = True
        self.state.status = "SAFE_MODE"

    def disable_safe_mode(self):
        self.state.safe_mode = False
        self.state.status = "NORMAL"

    def enable_global_lock(self, reason="UNSPECIFIED"):
        self.state.global_lock = True
        self.state.last_violation = reason
        self.state.status = "GLOBAL_LOCK"

    def disable_global_lock(self):
        self.state.global_lock = False
        self.state.status = "UNLOCKED"

    # ========================================================
    # PERMISSÕES
    # ========================================================

    def allow_live(self):
        self.state.live_allowed = True

    def block_live(self):
        self.state.live_allowed = False

    def allow_engine(self):
        self.state.engine_allowed = True

    def block_engine(self):
        self.state.engine_allowed = False

    def allow_integration(self):
        self.state.integration_allowed = True

    def block_integration(self):
        self.state.integration_allowed = False

    def allow_auto(self):
        self.state.auto_allowed = True

    def block_auto(self):
        self.state.auto_allowed = False

    # ========================================================
    # VALIDADORES
    # ========================================================

    def validate_live_mode(self):
        if not self.state.active:
            return False, "POLICY_INACTIVE"
        if self.state.safe_mode:
            return False, "SAFE_MODE_ACTIVE"
        if self.state.global_lock:
            return False, "GLOBAL_LOCK_ACTIVE"
        if not self.state.live_allowed:
            return False, "LIVE_NOT_ALLOWED"
        return True, "LIVE_ALLOWED"

    def validate_engine_execution(self):
        if not self.state.engine_allowed:
            return False, "ENGINE_BLOCKED"
        if self.state.global_lock:
            return False, "GLOBAL_LOCK_ACTIVE"
        return True, "ENGINE_ALLOWED"

    def snapshot(self):
        return {
            "active": self.state.active,
            "safe_mode": self.state.safe_mode,
            "global_lock": self.state.global_lock,
            "live_allowed": self.state.live_allowed,
            "engine_allowed": self.state.engine_allowed,
            "integration_allowed": self.state.integration_allowed,
            "auto_allowed": self.state.auto_allowed,
            "last_violation": self.state.last_violation,
            "status": self.state.status,
        }