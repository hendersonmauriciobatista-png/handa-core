"""
FooterView
Rodapé informativo da UI H&A.

Responsabilidades:
- Mostrar mensagens globais curtas
- Exibir status geral de execução
- NÃO exibir métricas
- NÃO sugerir ação
"""

from datetime import datetime


class FooterView:
    def __init__(self):
        pass

    def render(self, state: dict):
        system = state.get("system", {})
        activity = state.get("activity", {})

        system_status = system.get("system_status", "UNKNOWN")
        last_event = activity.get("last_event", "-")

        now_str = datetime.now().strftime("%H:%M:%S")

        print("\n" + "=" * 60)
        print(" RODAPÉ ")
        print("-" * 60)
        print(f" Status geral : {system_status}")
        print(f" Último evento: {last_event}")
        print(f" Atualizado em: {now_str}")
        print("=" * 60)
