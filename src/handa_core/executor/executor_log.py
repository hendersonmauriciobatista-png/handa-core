# ============================================================
# Executor Log — LOG IRREFUTÁVEL (FASE 3.2.3)
# ============================================================

import json
from pathlib import Path
from datetime import datetime, timezone


class ExecutorLogger:
    def __init__(self, log_path: str = "logs/executor.log"):
        self.path = Path(log_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, record: dict) -> None:
        record["timestamp"] = datetime.now(timezone.utc).isoformat()
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
