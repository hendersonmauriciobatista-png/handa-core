# ============================================================
# core/alo_profile/profile_store.py
# Persistência dos perfis do ALO por ativo
# ============================================================

import json
import os
from datetime import datetime, timezone
from typing import Dict

from core.alo_profile.profile_models import AloSymbolProfile


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AloProfileStore:
    def __init__(self, path: str = "storage/alo_profile/alo_profiles.json"):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def _safe_symbol(self, symbol: str) -> str:
        return str(symbol or "").strip().upper()

    def load_all(self) -> Dict[str, AloSymbolProfile]:
        if not os.path.exists(self.path):
            return {}

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = f.read().strip()

            if not raw:
                return {}

            data = json.loads(raw)

            if not isinstance(data, dict):
                return {}

            profiles: Dict[str, AloSymbolProfile] = {}

            for symbol, payload in data.items():
                safe_symbol = self._safe_symbol(symbol)
                if not safe_symbol:
                    continue

                if not isinstance(payload, dict):
                    continue

                payload["symbol"] = safe_symbol
                profiles[safe_symbol] = AloSymbolProfile.from_dict(payload)

            return profiles

        except Exception as e:
            print(f"[ALO PROFILE STORE] erro ao carregar perfis: {e}")
            return {}

    def save_all(self, profiles: Dict[str, AloSymbolProfile]) -> None:
        try:
            serializable = {}

            for symbol, profile in (profiles or {}).items():
                safe_symbol = self._safe_symbol(symbol)
                if not safe_symbol:
                    continue

                if isinstance(profile, AloSymbolProfile):
                    serializable[safe_symbol] = profile.to_dict()
                elif isinstance(profile, dict):
                    payload = dict(profile)
                    payload["symbol"] = safe_symbol
                    serializable[safe_symbol] = AloSymbolProfile.from_dict(
                        payload
                    ).to_dict()

            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"[ALO PROFILE STORE] erro ao salvar perfis: {e}")

    def get_profile(self, symbol: str) -> AloSymbolProfile:
        safe_symbol = self._safe_symbol(symbol)
        if not safe_symbol:
            return AloSymbolProfile(symbol="UNKNOWN")

        profiles = self.load_all()

        if safe_symbol in profiles:
            return profiles[safe_symbol]

        return AloSymbolProfile(symbol=safe_symbol)

    def upsert_profile(self, profile: AloSymbolProfile) -> None:
        if not isinstance(profile, AloSymbolProfile):
            return

        safe_symbol = self._safe_symbol(profile.symbol)
        if not safe_symbol:
            return

        profiles = self.load_all()
        profile.symbol = safe_symbol
        profile.last_update = _utc_now_iso()
        profiles[safe_symbol] = profile
        self.save_all(profiles)

    def update_profile(self, symbol: str, updater_fn) -> AloSymbolProfile:
        safe_symbol = self._safe_symbol(symbol)
        if not safe_symbol:
            return AloSymbolProfile(symbol="UNKNOWN")

        profiles = self.load_all()
        profile = profiles.get(safe_symbol, AloSymbolProfile(symbol=safe_symbol))

        try:
            updated = updater_fn(profile)
            if isinstance(updated, AloSymbolProfile):
                profile = updated
        except Exception as e:
            print(f"[ALO PROFILE STORE] erro no updater de {safe_symbol}: {e}")

        profile.symbol = safe_symbol
        profile.last_update = _utc_now_iso()
        profiles[safe_symbol] = profile
        self.save_all(profiles)
        return profile
