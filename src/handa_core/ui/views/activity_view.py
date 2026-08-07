"""
ActivityView
Exibe a atividade global do sistema H&A.

Responsabilidades:
- Mostrar resumo textual da atividade
- Mostrar último evento relevante
- NÃO exibir métricas numéricas
- NÃO induzir ação
"""

class ActivityView:
    def __init__(self):
        pass

    def render(self, state: dict):
        activity = state.get("activity", {})

        summary = activity.get("summary", "Sem informações de atividade")
        last_event = activity.get("last_event", "-")

        print("\n" + "-" * 60)
        print(" ATIVIDADE DO SISTEMA ")
        print("-" * 60)
        print(f" {summary}")
        print(f" Último evento : {last_event}")
        print("-" * 60)
