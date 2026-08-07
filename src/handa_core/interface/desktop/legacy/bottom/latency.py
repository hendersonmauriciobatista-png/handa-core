from interface.desktop.bottom.telemetry_graph import TelemetryGraphPanel
from interface.desktop.theme.theme import ACCENT_WARN


class LatencyPanel(TelemetryGraphPanel):
    def __init__(self, parent):
        # valores fake só para visual
        values = [30, 35, 40, 38, 45, 50, 55, 52, 48, 46, 44]
        super().__init__(
            parent,
            title="LATÊNCIA",
            values=values,
            color=ACCENT_WARN
        )
