from interface.desktop.bottom.telemetry_graph import TelemetryGraphPanel
from interface.desktop.theme.theme import ACCENT_OK


class ActivityPanel(TelemetryGraphPanel):
    def __init__(self, parent):
        # valores fake só para visual (depois vêm do core)
        values = [40, 45, 60, 70, 65, 75, 80, 82, 78, 85, 90]
        super().__init__(
            parent,
            title="ATIVIDADE",
            values=values,
            color=ACCENT_OK
        )
