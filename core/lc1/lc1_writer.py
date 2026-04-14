import json
import os
from enum import Enum
from datetime import datetime, date
from core.learning.adaptive_learning_observer import AdaptiveLearningObserver
from core.alo_profile import AloProfileUpdater


class LC1Writer:

    def __init__(self, path="storage/lc1/handa_lc1_events.jsonl"):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.alo = AdaptiveLearningObserver()
        self.alo_profile_updater = AloProfileUpdater()

    def _make_json_safe(self, value):
        if isinstance(value, dict):
            return {str(k): self._make_json_safe(v) for k, v in value.items()}

        if isinstance(value, list):
            return [self._make_json_safe(v) for v in value]

        if isinstance(value, tuple):
            return [self._make_json_safe(v) for v in value]

        if isinstance(value, set):
            return [self._make_json_safe(v) for v in value]

        if isinstance(value, Enum):
            return value.value

        if isinstance(value, (datetime, date)):
            return value.isoformat()

        if hasattr(value, "isoformat") and callable(value.isoformat):
            try:
                return value.isoformat()
            except Exception:
                pass

        if isinstance(value, (str, int, float, bool)) or value is None:
            return value

        return str(value)

    def write(self, event: dict):
        try:
            safe_event = self._make_json_safe(event)

            self.alo.ingest_event(safe_event)

            try:
                updated_profile = self.alo_profile_updater.update_from_event(safe_event)
                if updated_profile is not None:
                    print(
                        f"[ALO PROFILE] atualizado: "
                        f"{updated_profile.symbol} | "
                        f"trades={updated_profile.total_trades} | "
                        f"wins={updated_profile.wins} | "
                        f"losses={updated_profile.losses} | "
                        f"block_bias={updated_profile.block_bias:.2f}"
                    )
            except Exception as e:
                print(f"[ALO PROFILE ERROR] Falha ao atualizar profile: {e}")

            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(safe_event, ensure_ascii=False) + "\n")

        except Exception as e:
            print(f"[LC1 ERROR] Falha ao gravar evento: {e}")
