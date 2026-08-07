import json
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock

LOG_DIR = Path("storage")
LOG_FILE = LOG_DIR / "history.jsonl"  # JSON Lines (1 evento por linha)

_lock = Lock()


class HALogger:
    """
    Logger append-only do H&A.
    Seguro para threads.
    Retenção automática por tempo (janela deslizante).
    """

    RETENTION_HOURS = 24

    @staticmethod
    def _now():
        return datetime.utcnow()

    @staticmethod
    def log(event: dict):
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        payload = {
            "ts": HALogger._now().isoformat(timespec="seconds") + "Z",
            **event,
        }

        with _lock:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    @staticmethod
    def cleanup():
        """
        Remove eventos mais antigos que RETENTION_HOURS.
        Deve ser chamado raramente (ex: startup).
        """
        if not LOG_FILE.exists():
            return

        cutoff = HALogger._now() - timedelta(hours=HALogger.RETENTION_HOURS)
        kept_lines = []

        with _lock:
            with LOG_FILE.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        event = json.loads(line)
                        ts = datetime.fromisoformat(event["ts"].replace("Z", ""))
                        if ts >= cutoff:
                            kept_lines.append(line)
                    except Exception:
                        # ignora linhas corrompidas
                        continue

            with LOG_FILE.open("w", encoding="utf-8") as f:
                f.writelines(kept_lines)

