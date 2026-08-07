"""
HeaderView
Exibe o estado global do sistema H&A.

Responsabilidades:
- Mostrar system_status
- Mostrar mode
- Mostrar risco global
- Mostrar heartbeat
- NÃO decide nada
"""

from datetime import datetime


class HeaderView:

    def __init__(self):
        pass

    def render(self, state: dict):
        system = state.get("system", {})

        system_status = system.get("system_status", "UNKNOWN")
        mode = system.get("mode", "UNKNOWN")
        risk = system.get("risk", "UNKNOWN")
        heartbeat = system.get("heartbeat")

        heartbeat_str = (
            datetime.fromtimestamp(heartbeat).strftime("%H:%M:%S")
            if heartbeat else "--:--:--"
        )

        print("\n" + "=" * 60)
        print(" H&A | HEADER ")
        print("-" * 60)
        print(f" Status do Sistema : {system_status}")
        print(f" Modo              : {mode}")
        print(f" Risco Global      : {risk}")
        print(f" Heartbeat         : {heartbeat_str}")

        if mode == "LIVE":
            print(" >>> LIVE MODE ATIVO <<< ")

        print("=" * 60)
