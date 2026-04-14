class RiskState:
    def __init__(self):
        self.status = "UNKNOWN"
        self.reason = None
        self.last_event = None
        self.updated_at = None

    def update(self, risk_payload: dict):
        self.status = risk_payload.get("status", "UNKNOWN")
        self.reason = risk_payload.get("reason")
        self.last_event = risk_payload.get("last_event")
        self.updated_at = risk_payload.get("updated_at")
