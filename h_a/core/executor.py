class Executor:
    """
    Executor técnico (Mock).
    Não executa ordens reais.
    """

    def execute(self, order, approved: bool):
        if not approved:
            raise PermissionError("Ordem não aprovada pelo RiskManager")

        # Mock: simula execução
        return {
            "status": "executed",
            "order": order
        }
