# ============================================================
# core/learning/learning_storage.py
# Persistência de perfis de aprendizado do ALO
# ============================================================

import json
import os
from copy import deepcopy
from datetime import datetime, date
from enum import Enum
from threading import Lock
from typing import Any, Dict, Optional


class LearningStorage:
    """
    Responsável por persistir e recuperar os perfis de aprendizado do ALO.

    Estrutura do arquivo JSON:
    {
        "updated_at": "...",
        "profiles": {
            "BTCUSDC": {...},
            "ETHUSDC": {...}
        }
    }
    """

    def __init__(self, path: str = "storage/learning/alo_learning_profiles.json"):
        self.path = path
        self._lock = Lock()
        self._ensure_storage()

    # =========================================================
    # INIT / BASE
    # =========================================================
    def _ensure_storage(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

        if not os.path.exists(self.path):
            self._write_file({"updated_at": self._now_iso(), "profiles": {}})

    def _now_iso(self) -> str:
        return datetime.utcnow().isoformat()

    # =========================================================
    # SERIALIZAÇÃO SEGURA
    # =========================================================
    def _make_json_safe(self, value: Any) -> Any:
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

    # =========================================================
    # LEITURA / ESCRITA BASE
    # =========================================================
    def _read_file(self) -> Dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                return {"updated_at": self._now_iso(), "profiles": {}}

            if "profiles" not in data or not isinstance(data["profiles"], dict):
                data["profiles"] = {}

            if "updated_at" not in data:
                data["updated_at"] = self._now_iso()

            return data

        except FileNotFoundError:
            return {"updated_at": self._now_iso(), "profiles": {}}

        except json.JSONDecodeError:
            print("[LEARNING STORAGE] JSON corrompido. Recriando base vazia.")
            return {"updated_at": self._now_iso(), "profiles": {}}

        except Exception as e:
            print(f"[LEARNING STORAGE] Erro ao ler arquivo: {e}")
            return {"updated_at": self._now_iso(), "profiles": {}}

    def _write_file(self, data: Dict[str, Any]) -> bool:
        try:
            safe_data = self._make_json_safe(data)

            temp_path = f"{self.path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(safe_data, f, ensure_ascii=False, indent=2)

            os.replace(temp_path, self.path)
            return True

        except Exception as e:
            print(f"[LEARNING STORAGE] Erro ao escrever arquivo: {e}")
            return False

    # =========================================================
    # PERFIS
    # =========================================================
    def get_all_profiles(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            data = self._read_file()
            return deepcopy(data.get("profiles", {}))

    def get_profile(self, symbol: str) -> Dict[str, Any]:
        symbol = str(symbol).strip().upper()

        with self._lock:
            data = self._read_file()
            profiles = data.get("profiles", {})
            profile = profiles.get(symbol)

            if isinstance(profile, dict):
                return deepcopy(profile)

            return {}

    def has_profile(self, symbol: str) -> bool:
        symbol = str(symbol).strip().upper()

        with self._lock:
            data = self._read_file()
            profiles = data.get("profiles", {})
            return symbol in profiles

    def save_profile(self, symbol: str, profile_data: Dict[str, Any]) -> bool:
        symbol = str(symbol).strip().upper()

        if not symbol:
            print("[LEARNING STORAGE] save_profile ignorado: símbolo inválido.")
            return False

        if not isinstance(profile_data, dict):
            print("[LEARNING STORAGE] save_profile ignorado: profile_data inválido.")
            return False

        with self._lock:
            data = self._read_file()
            profiles = data.setdefault("profiles", {})

            existing = profiles.get(symbol, {})
            if not isinstance(existing, dict):
                existing = {}

            merged = deepcopy(existing)
            merged.update(self._make_json_safe(profile_data))
            merged["symbol"] = symbol
            merged["updated_at"] = self._now_iso()

            if "created_at" not in merged:
                merged["created_at"] = self._now_iso()

            profiles[symbol] = merged
            data["updated_at"] = self._now_iso()

            ok = self._write_file(data)
            if ok:
                print(f"[LEARNING STORAGE] Perfil salvo: {symbol}")
            return ok

    def replace_profile(self, symbol: str, profile_data: Dict[str, Any]) -> bool:
        symbol = str(symbol).strip().upper()

        if not symbol:
            print("[LEARNING STORAGE] replace_profile ignorado: símbolo inválido.")
            return False

        if not isinstance(profile_data, dict):
            print("[LEARNING STORAGE] replace_profile ignorado: profile_data inválido.")
            return False

        with self._lock:
            data = self._read_file()
            profiles = data.setdefault("profiles", {})

            created_at = self._now_iso()
            if symbol in profiles and isinstance(profiles[symbol], dict):
                created_at = profiles[symbol].get("created_at", created_at)

            new_profile = self._make_json_safe(deepcopy(profile_data))
            new_profile["symbol"] = symbol
            new_profile["created_at"] = created_at
            new_profile["updated_at"] = self._now_iso()

            profiles[symbol] = new_profile
            data["updated_at"] = self._now_iso()

            ok = self._write_file(data)
            if ok:
                print(f"[LEARNING STORAGE] Perfil substituído: {symbol}")
            return ok

    def update_profile_fields(self, symbol: str, fields: Dict[str, Any]) -> bool:
        symbol = str(symbol).strip().upper()

        if not symbol:
            print(
                "[LEARNING STORAGE] update_profile_fields ignorado: símbolo inválido."
            )
            return False

        if not isinstance(fields, dict):
            print("[LEARNING STORAGE] update_profile_fields ignorado: fields inválido.")
            return False

        with self._lock:
            data = self._read_file()
            profiles = data.setdefault("profiles", {})

            current = profiles.get(symbol, {})
            if not isinstance(current, dict):
                current = {}

            for key, value in fields.items():
                current[str(key)] = self._make_json_safe(value)

            current["symbol"] = symbol
            current["updated_at"] = self._now_iso()

            if "created_at" not in current:
                current["created_at"] = self._now_iso()

            profiles[symbol] = current
            data["updated_at"] = self._now_iso()

            ok = self._write_file(data)
            if ok:
                print(f"[LEARNING STORAGE] Campos atualizados: {symbol}")
            return ok

    def delete_profile(self, symbol: str) -> bool:
        symbol = str(symbol).strip().upper()

        if not symbol:
            print("[LEARNING STORAGE] delete_profile ignorado: símbolo inválido.")
            return False

        with self._lock:
            data = self._read_file()
            profiles = data.setdefault("profiles", {})

            if symbol not in profiles:
                return True

            del profiles[symbol]
            data["updated_at"] = self._now_iso()

            ok = self._write_file(data)
            if ok:
                print(f"[LEARNING STORAGE] Perfil removido: {symbol}")
            return ok

    # =========================================================
    # CONTADORES / ESTATÍSTICAS
    # =========================================================
    def increment_field(self, symbol: str, field_name: str, amount: float = 1) -> bool:
        symbol = str(symbol).strip().upper()
        field_name = str(field_name).strip()

        if not symbol or not field_name:
            print("[LEARNING STORAGE] increment_field ignorado: parâmetros inválidos.")
            return False

        with self._lock:
            data = self._read_file()
            profiles = data.setdefault("profiles", {})

            current = profiles.get(symbol, {})
            if not isinstance(current, dict):
                current = {}

            old_value = current.get(field_name, 0)

            try:
                old_value = float(old_value)
            except Exception:
                old_value = 0.0

            current[field_name] = old_value + amount
            current["symbol"] = symbol
            current["updated_at"] = self._now_iso()

            if "created_at" not in current:
                current["created_at"] = self._now_iso()

            profiles[symbol] = current
            data["updated_at"] = self._now_iso()

            ok = self._write_file(data)
            if ok:
                print(
                    f"[LEARNING STORAGE] Incremento aplicado: "
                    f"{symbol} | {field_name} += {amount}"
                )
            return ok

    # =========================================================
    # RESUMOS BÁSICOS
    # =========================================================
    def get_profiles_count(self) -> int:
        with self._lock:
            data = self._read_file()
            profiles = data.get("profiles", {})
            return len(profiles)

    def get_storage_summary(self) -> Dict[str, Any]:
        with self._lock:
            data = self._read_file()
            profiles = data.get("profiles", {})

            summary = {
                "updated_at": data.get("updated_at"),
                "profiles_count": len(profiles),
                "symbols": sorted(list(profiles.keys())),
            }
            return summary

    def get_profile_summary(self, symbol: str) -> Dict[str, Any]:
        symbol = str(symbol).strip().upper()

        with self._lock:
            data = self._read_file()
            profiles = data.get("profiles", {})
            profile = profiles.get(symbol, {})

            if not isinstance(profile, dict):
                return {}

            summary = {
                "symbol": symbol,
                "created_at": profile.get("created_at"),
                "updated_at": profile.get("updated_at"),
                "wins": profile.get("wins", 0),
                "losses": profile.get("losses", 0),
                "trades": profile.get("trades", 0),
                "score": profile.get("score", 0.0),
                "confidence": profile.get("confidence", 0.0),
                "status": profile.get("status", "UNKNOWN"),
            }

            return summary

    # =========================================================
    # RESET CONTROLADO
    # =========================================================
    def reset_storage(self) -> bool:
        with self._lock:
            data = {"updated_at": self._now_iso(), "profiles": {}}

            ok = self._write_file(data)
            if ok:
                print("[LEARNING STORAGE] Storage resetado com sucesso.")
            return ok
