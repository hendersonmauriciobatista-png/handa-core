# ============================================================
# ui_state_adapter.py
# UI STATE ADAPTER — READ ONLY (FASE 2)
# Sistema: H&A + ALFRED IA
# ------------------------------------------------------------
# Função:
# - Expor estado do sistema para a UI
# - Somente leitura
# - Snapshot seguro
#
# PROIBIDO:
# ❌ executar comandos
# ❌ alterar estado
# ❌ acessar router
# ❌ acessar engine
# ❌ acessar integration
# ============================================================


class UIStateAdapter:
    """
    Adaptador de estado READ-ONLY entre Core/Header e UI.

    A UI nunca executa nada.
    A UI nunca decide nada.
    A UI apenas observa snapshots.
    """

    def __init__(self, header):
        self.header = header

    # ========================================================
    # SNAPSHOTS SIMPLES (UI → Estado)
    # ========================================================

    def get_global_state(self):
        return self.header.global_state.snapshot()

    def get_connection(self):
        return self.header.connection.snapshot()

    def get_balance(self):
        return self.header.balance.snapshot()

    def get_profit(self):
        return self.header.profit.snapshot()

    def get_auto(self):
        return self.header.auto.snapshot()

    def get_safe_stop(self):
        return self.header.safe_stop.snapshot()

    def get_status(self):
        return self.header.status.snapshot()

    def snapshot(self):
        """
        Snapshot completo para UI.
        """
        return {
            "global": self.get_global_state(),
            "connection": self.get_connection(),
            "balance": self.get_balance(),
            "profit": self.get_profit(),
            "auto": self.get_auto(),
            "safe_stop": self.get_safe_stop(),
            "status": self.get_status(),
        }


# ============================================================
# FACTORY
# ============================================================

def build_ui_adapter(app_context):
    """
    Factory oficial da FASE 2.
    UIStateAdapter é sempre READ-ONLY.
    """
    return UIStateAdapter(
        header=app_context.header
    )
