"""
UI App — Bootstrap principal
Responsável por:
- iniciar o StateListener
- renderizar a UI continuamente
"""

import time
import threading

from ui.services.ha_client import HAClient
from ui.services.state_listener import StateListener

from ui.views.header_view import HeaderView
from ui.views.slots_view import SlotsView
from ui.views.center_view import CenterView
from ui.views.activity_view import ActivityView
from ui.views.latency_view import LatencyView
from ui.views.risk_view import RiskView
from ui.views.footer_view import FooterView


def main():
    # Cliente H&A (API local)
    ha_client = HAClient()

    # Listener de estado
    state_listener = StateListener(ha_client)

    listener_thread = threading.Thread(
        target=state_listener.run,
        daemon=True
    )
    listener_thread.start()

    # Pequeno delay para garantir primeiro ciclo
    time.sleep(0.6)

    # Views
    header = HeaderView()
    slots = SlotsView()
    center = CenterView()
    activity = ActivityView()
    latency = LatencyView()
    risk = RiskView()
    footer = FooterView()

    # Loop principal da UI
    while True:
        state = state_listener.get_state_snapshot()

        header.render(state)
        slots.render(state)
        center.render(state)
        activity.render(state)
        latency.render(state)
        risk.render(state)
        footer.render(state)

        time.sleep(1)


if __name__ == "__main__":
    main()
