"""
LatencyView
Exibe o estado de conectividade / latência do H&A.

Responsabilidades:
- Mostrar estado qualitativo: OK | DELAYED | NO_FEED
- Mostrar timestamp da última atualização
- NÃO exibir números técnicos
- NÃO gerar alarme emocional
"""

from datetime import datetime


class LatencyView:
    def __init__(self):
        pass

    def render(self, state: dict):
        connectivity = state.get("connectivity", {})

        status = connectivity.get("status", "UNKNOWN")
        last_update = connectivity.get("last_update")

        time_str = (
            datetime.fromtimestamp(last_update).strftime("%H:%M:%S")
            if last_update else "--:--:--"
        )

        print("\n" + "-" * 60)
        print(" CONECTIVIDADE / LATÊNCIA ")
        print("-" * 60)
        print(f" Estado             : {status}")
        print(f" Última atualização : {time_str}")
        print("-" * 60)
