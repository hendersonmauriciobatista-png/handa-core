import time
from pathlib import Path


class Heartbeat:
    """
    Heartbeat simples para long runs.
    Registra atividade periódica do sistema.
    """

    def __init__(self, interval_seconds: int = 60):
        self.interval = interval_seconds
        self._last_beat = 0.0

        base = Path("logs")
        base.mkdir(exist_ok=True)

        ts = time.strftime("%Y%m%d_%H%M%S")
        self.filepath = base / f"heartbeat_{ts}.log"

        self.start_time = time.time()

    def beat(self):
        now = time.time()
        if now - self._last_beat < self.interval:
            return

        uptime = int(now - self.start_time)
        msg = f"[HEARTBEAT] uptime={uptime}s\n"

        with self.filepath.open("a", encoding="utf-8") as f:
            f.write(msg)

        self._last_beat = now
