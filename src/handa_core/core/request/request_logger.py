import json
from pathlib import Path
from datetime import datetime, timezone

from h_a.core.request.request_model import Request


class RequestLogger:
    def __init__(self, log_path: str = "logs/requests.log"):
        self.path = Path(log_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, request: Request) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request.request_id,
            "type": request.type,
            "origin": request.origin,
            "system_phase": request.system_phase,
            "status": request.status,
            "decision_reason": request.decision_reason,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
