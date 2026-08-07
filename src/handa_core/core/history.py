import json
import time
from pathlib import Path
from typing import Dict, Any


class History:
    """
    Histórico central do H&A.
    Append-only.
    Usado por mock, live, saldo e estatísticas futuras.
    """

    def __init__(self, symbol: str = "GENERIC"):
        base = Path("logs")
        base.mkdir(exist_ok=True)

        ts = time.strftime("%Y%m%d_%H%M%S")
        self.filepath = base / f"history_{symbol}_{ts}.jsonl"

    def log_event(self, data: Dict[str, Any]):
        """
        Registra um evento no histórico.
        Cada evento é uma linha JSON (JSONL).
        """
        with self.filepath.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")

