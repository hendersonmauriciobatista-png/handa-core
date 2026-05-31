import json
import os
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from core.alo_memory.models import (
    ALOMemoryDivergence,
    ALOMemoryProfile,
    ALOMemorySnapshot,
)


class ALOMemoryBuilder:
    """
    Builds a read-only projection from LC1/LC1E and legacy ALO memory files.

    This class does not write files, register gates, mutate runtime state, or
    connect to operational consumers.
    """

    def __init__(
        self,
        lc1_path: str = "storage/lc1/handa_lc1_events.jsonl",
        lc1e_path: str = "storage/lc1e_events_v2.jsonl",
        adaptive_learning_path: str = "storage/learning/alo_learning_profiles.json",
        alo_profile_path: str = "storage/alo_profile/alo_profiles.json",
        max_lc1_events: int = 5000,
        max_lc1e_events: int = 5000,
        max_tail_bytes: int = 8 * 1024 * 1024,
        confidence_divergence_threshold: float = 0.15,
        block_bias_divergence_threshold: float = 0.25,
    ) -> None:
        self.lc1_path = lc1_path
        self.lc1e_path = lc1e_path
        self.adaptive_learning_path = adaptive_learning_path
        self.alo_profile_path = alo_profile_path
        self.max_lc1_events = int(max_lc1_events)
        self.max_lc1e_events = int(max_lc1e_events)
        self.max_tail_bytes = int(max_tail_bytes)
        self.confidence_divergence_threshold = float(confidence_divergence_threshold)
        self.block_bias_divergence_threshold = float(block_bias_divergence_threshold)

    def build_snapshot(self) -> ALOMemorySnapshot:
        lc1_events = self._read_jsonl_tail(self.lc1_path, self.max_lc1_events)
        lc1e_events = self._read_jsonl_tail(self.lc1e_path, self.max_lc1e_events)
        adaptive_profiles = self._read_adaptive_learning_profiles()
        alo_profiles = self._read_alo_profiles()

        projection = self._project_profiles(lc1_events, lc1e_events)
        self._merge_legacy_context(projection, adaptive_profiles, alo_profiles)

        profiles = {
            symbol: self._build_profile(symbol, data)
            for symbol, data in sorted(projection.items())
        }
        divergences = self._build_divergences(
            profiles=profiles,
            adaptive_profiles=adaptive_profiles,
            alo_profiles=alo_profiles,
        )

        summary = {
            "symbols_projected": len(profiles),
            "divergences": len(divergences),
            "no_effect": True,
            "operational_effect_count": 0,
            "mode": "READ_ONLY",
        }

        return ALOMemorySnapshot(
            generated_at=self._now_iso(),
            profiles_count=len(profiles),
            profiles=profiles,
            divergences=tuple(divergences),
            source_files={
                "lc1": self.lc1_path,
                "lc1e": self.lc1e_path,
                "adaptive_learning": self.adaptive_learning_path,
                "alo_profile": self.alo_profile_path,
            },
            source_event_counts={
                "lc1": len(lc1_events),
                "lc1e": len(lc1e_events),
                "adaptive_learning_profiles": len(adaptive_profiles),
                "alo_profiles": len(alo_profiles),
            },
            summary=summary,
        )

    def _project_profiles(
        self, lc1_events: Iterable[Dict[str, Any]], lc1e_events: Iterable[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        profiles: Dict[str, Dict[str, Any]] = defaultdict(self._new_projection)

        for event in lc1_events:
            symbol = self._safe_symbol(event.get("symbol") or event.get("pair"))
            if not symbol:
                continue

            data = profiles[symbol]
            event_type = self._safe_upper(event.get("event_type"))
            data["source_counts"]["lc1"] += 1
            data["total_events"] += 1

            if event_type == "BUY":
                data["buy_count"] += 1
                data["approval_count"] += 1
                data["attempt_count"] += 1

            elif event_type == "SELL":
                pnl = self._extract_pnl(event)
                data["sell_count"] += 1
                data["closed_trade_count"] += 1
                data["recent_results"].append(round(pnl, 6))
                if pnl > 0:
                    data["win_count"] += 1
                else:
                    data["loss_count"] += 1

                reason = self._safe_text(
                    event.get("close_reason") or event.get("reason")
                )
                if reason:
                    data["recent_reasons"].append(reason)

            self._update_timestamps(data, event.get("timestamp"))

        for event in lc1e_events:
            symbol = self._safe_symbol(event.get("symbol") or event.get("pair"))
            if not symbol:
                continue

            data = profiles[symbol]
            reason = self._safe_upper(event.get("reason") or event.get("summary"))
            reason_class = self._classify_non_execution(reason)

            data["source_counts"]["lc1e"] += 1
            data["total_events"] += 1
            data["attempt_count"] += 1
            data["rejection_count"] += 1
            data["non_execution_count"] += 1
            data["recent_reasons"].append(reason or "UNKNOWN")
            data["reason_counts"][reason or "UNKNOWN"] += 1
            data["last_market_state"] = self._safe_text(event.get("market_state"))

            if reason_class == "STRUCTURAL":
                data["structural_block_count"] += 1
                data["block_bias"] += 0.10
            elif reason_class == "MACRO":
                data["macro_block_count"] += 1
            else:
                data["technical_rejection_count"] += 1
                data["block_bias"] += 0.05

            if "QUALITY" in reason:
                data["quality_filter_count"] += 1
            if "LOW_SCORE" in reason or "SCORE_BAIXO" in reason:
                data["low_score_count"] += 1

            self._update_timestamps(data, event.get("timestamp"))

        return profiles

    def _merge_legacy_context(
        self,
        projection: Dict[str, Dict[str, Any]],
        adaptive_profiles: Dict[str, Dict[str, Any]],
        alo_profiles: Dict[str, Dict[str, Any]],
    ) -> None:
        for symbol in set(adaptive_profiles) | set(alo_profiles):
            data = projection.setdefault(symbol, self._new_projection())

            adaptive = adaptive_profiles.get(symbol, {})
            alo_profile = alo_profiles.get(symbol, {})

            data["source_counts"]["adaptive_learning"] += 1 if adaptive else 0
            data["source_counts"]["alo_profile"] += 1 if alo_profile else 0

            if not data["confidence_score"] and adaptive:
                data["confidence_score"] = self._safe_float(
                    adaptive.get("confidence_score"), 0.0
                )
            if data["status"] == "NO_HISTORY" and adaptive:
                data["status"] = self._safe_text(adaptive.get("status")) or "NO_HISTORY"

            if alo_profile:
                data["confidence_bias"] = self._safe_float(
                    alo_profile.get("confidence_bias"), 0.0
                )
                data["capital_bias"] = self._safe_float(
                    alo_profile.get("capital_bias"), 1.0
                )
                data["last_market_state"] = (
                    data["last_market_state"]
                    or self._safe_text(alo_profile.get("last_market_state"))
                )
                data["recent_results"].extend(
                    self._safe_float(item, 0.0)
                    for item in list(alo_profile.get("recent_results", []) or [])[-20:]
                )
                data["recent_reasons"].extend(
                    self._safe_text(item)
                    for item in list(alo_profile.get("recent_reasons", []) or [])[-20:]
                    if self._safe_text(item)
                )

    def _build_profile(self, symbol: str, data: Dict[str, Any]) -> ALOMemoryProfile:
        attempt_count = int(data["attempt_count"])
        approval_count = int(data["approval_count"])
        confidence_score = float(data["confidence_score"])

        if attempt_count > 0:
            confidence_score = approval_count / max(attempt_count, 1)

        status = self._infer_status(confidence_score, int(data["total_events"]))
        if data["status"] and data["status"] != "NO_HISTORY" and data["total_events"] <= 0:
            status = data["status"]

        dominant_reason = "NONE"
        if data["reason_counts"]:
            dominant_reason = data["reason_counts"].most_common(1)[0][0]

        block_bias = max(0.0, min(float(data["block_bias"]), 3.0))

        return ALOMemoryProfile(
            symbol=symbol,
            total_events=int(data["total_events"]),
            execution_count=int(data["closed_trade_count"]),
            non_execution_count=int(data["non_execution_count"]),
            win_count=int(data["win_count"]),
            loss_count=int(data["loss_count"]),
            attempt_count=attempt_count,
            approval_count=approval_count,
            rejection_count=int(data["rejection_count"]),
            structural_block_count=int(data["structural_block_count"]),
            technical_rejection_count=int(data["technical_rejection_count"]),
            macro_block_count=int(data["macro_block_count"]),
            quality_filter_count=int(data["quality_filter_count"]),
            low_score_count=int(data["low_score_count"]),
            confidence_score=round(confidence_score, 6),
            status=status,
            block_bias=round(block_bias, 6),
            confidence_bias=float(data["confidence_bias"]),
            capital_bias=float(data["capital_bias"]),
            recent_results=tuple(list(data["recent_results"])[-20:]),
            recent_reasons=tuple(list(data["recent_reasons"])[-20:]),
            dominant_rejection_reason=dominant_reason,
            last_market_state=str(data["last_market_state"] or ""),
            source_counts=dict(data["source_counts"]),
            created_at=str(data["created_at"] or ""),
            updated_at=str(data["updated_at"] or ""),
        )

    def _build_divergences(
        self,
        profiles: Dict[str, ALOMemoryProfile],
        adaptive_profiles: Dict[str, Dict[str, Any]],
        alo_profiles: Dict[str, Dict[str, Any]],
    ) -> List[ALOMemoryDivergence]:
        divergences: List[ALOMemoryDivergence] = []

        all_symbols = set(profiles) | set(adaptive_profiles) | set(alo_profiles)
        for symbol in sorted(all_symbols):
            profile = profiles.get(symbol, ALOMemoryProfile(symbol=symbol))
            adaptive = adaptive_profiles.get(symbol)
            alo_profile = alo_profiles.get(symbol)

            if adaptive is None:
                divergences.append(
                    self._divergence(symbol, "profile", "present", "missing", "adaptive_learning", "INFO", "PROFILE_MISSING_IN_ADAPTIVE_LEARNING")
                )
            if alo_profile is None:
                divergences.append(
                    self._divergence(symbol, "profile", "present", "missing", "alo_profile", "INFO", "PROFILE_MISSING_IN_ALO_PROFILE")
                )

            if adaptive:
                self._compare_int(
                    divergences,
                    symbol,
                    "attempt_count",
                    profile.attempt_count,
                    adaptive.get("attempts", 0),
                    "adaptive_learning",
                )
                self._compare_int(
                    divergences,
                    symbol,
                    "approval_count",
                    profile.approval_count,
                    adaptive.get("approvals", 0),
                    "adaptive_learning",
                )
                self._compare_int(
                    divergences,
                    symbol,
                    "rejection_count",
                    profile.rejection_count,
                    adaptive.get("rejections", 0),
                    "adaptive_learning",
                )
                legacy_confidence = self._safe_float(
                    adaptive.get("confidence_score"), 0.0
                )
                if abs(profile.confidence_score - legacy_confidence) >= self.confidence_divergence_threshold:
                    divergences.append(
                        self._divergence(
                            symbol,
                            "confidence_score",
                            profile.confidence_score,
                            legacy_confidence,
                            "adaptive_learning",
                            "WARN",
                            "CONFIDENCE_DIVERGENCE",
                        )
                    )

            if alo_profile:
                self._compare_int(
                    divergences,
                    symbol,
                    "closed_trade_count",
                    profile.execution_count,
                    alo_profile.get("total_trades", 0),
                    "alo_profile",
                )
                self._compare_int(
                    divergences,
                    symbol,
                    "win_count",
                    profile.win_count,
                    alo_profile.get("wins", 0),
                    "alo_profile",
                )
                self._compare_int(
                    divergences,
                    symbol,
                    "loss_count",
                    profile.loss_count,
                    alo_profile.get("losses", 0),
                    "alo_profile",
                )
                self._compare_int(
                    divergences,
                    symbol,
                    "non_execution_count",
                    profile.non_execution_count,
                    alo_profile.get("non_execution_count", 0),
                    "alo_profile",
                )
                legacy_block_bias = self._safe_float(alo_profile.get("block_bias"), 0.0)
                if abs(profile.block_bias - legacy_block_bias) >= self.block_bias_divergence_threshold:
                    divergences.append(
                        self._divergence(
                            symbol,
                            "block_bias",
                            profile.block_bias,
                            legacy_block_bias,
                            "alo_profile",
                            "WARN",
                            "BLOCK_BIAS_DIVERGENCE",
                        )
                    )

        return divergences

    def _read_jsonl_tail(self, path: str, max_events: int) -> List[Dict[str, Any]]:
        if max_events <= 0 or not os.path.exists(path):
            return []

        try:
            file_size = os.path.getsize(path)
            with open(path, "rb") as handle:
                if file_size > self.max_tail_bytes:
                    handle.seek(max(0, file_size - self.max_tail_bytes))
                    handle.readline()
                lines = deque(handle, maxlen=max_events)
        except Exception as exc:
            print(f"[ALO MEMORY] source_read_error path={path} | error={exc} | no_effect=true")
            return []

        events: List[Dict[str, Any]] = []
        for raw_line in lines:
            try:
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                payload = json.loads(line)
                if isinstance(payload, dict):
                    events.append(payload)
            except Exception:
                continue
        return events

    def _read_adaptive_learning_profiles(self) -> Dict[str, Dict[str, Any]]:
        data = self._read_json_file(self.adaptive_learning_path)
        profiles = data.get("profiles", {}) if isinstance(data, dict) else {}
        return self._normalize_profile_dict(profiles)

    def _read_alo_profiles(self) -> Dict[str, Dict[str, Any]]:
        data = self._read_json_file(self.alo_profile_path)
        return self._normalize_profile_dict(data if isinstance(data, dict) else {})

    def _read_json_file(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            print(f"[ALO MEMORY] source_read_error path={path} | error={exc} | no_effect=true")
            return {}

    def _normalize_profile_dict(self, raw: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        profiles: Dict[str, Dict[str, Any]] = {}
        for symbol, payload in (raw or {}).items():
            safe_symbol = self._safe_symbol(symbol)
            if safe_symbol and isinstance(payload, dict):
                profiles[safe_symbol] = dict(payload)
        return profiles

    def _compare_int(
        self,
        divergences: List[ALOMemoryDivergence],
        symbol: str,
        field: str,
        projected: int,
        reference: Any,
        source: str,
    ) -> None:
        reference_value = int(self._safe_float(reference, 0.0))
        if int(projected) != reference_value:
            divergences.append(
                self._divergence(
                    symbol,
                    field,
                    int(projected),
                    reference_value,
                    source,
                    "INFO",
                    "COUNTER_DIVERGENCE",
                )
            )

    def _divergence(
        self,
        symbol: str,
        field: str,
        projected: Any,
        reference: Any,
        reference_source: str,
        severity: str,
        reason: str,
    ) -> ALOMemoryDivergence:
        return ALOMemoryDivergence(
            symbol=symbol,
            field=field,
            projected=projected,
            reference=reference,
            reference_source=reference_source,
            severity=severity,
            reason=reason,
        )

    def _new_projection(self) -> Dict[str, Any]:
        return {
            "total_events": 0,
            "buy_count": 0,
            "sell_count": 0,
            "closed_trade_count": 0,
            "non_execution_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "attempt_count": 0,
            "approval_count": 0,
            "rejection_count": 0,
            "structural_block_count": 0,
            "technical_rejection_count": 0,
            "macro_block_count": 0,
            "quality_filter_count": 0,
            "low_score_count": 0,
            "confidence_score": 0.0,
            "status": "NO_HISTORY",
            "block_bias": 0.0,
            "confidence_bias": 0.0,
            "capital_bias": 1.0,
            "recent_results": [],
            "recent_reasons": [],
            "reason_counts": Counter(),
            "last_market_state": "",
            "source_counts": Counter(),
            "created_at": "",
            "updated_at": "",
        }

    def _classify_non_execution(self, reason: str) -> str:
        text = self._safe_upper(reason)
        if not text:
            return "UNKNOWN"

        structural_keywords = (
            "STRUCTURE",
            "STRUCTURAL",
            "BLACKLIST",
            "HARD_BLOCK",
            "SOFT_BLOCK",
            "PROFILE_BLOCK",
        )
        macro_keywords = ("NO_TRADE", "MQII", "MACRO", "MARKET_BLOCK", "GLOBAL_BLOCK")

        if any(keyword in text for keyword in structural_keywords):
            return "STRUCTURAL"
        if any(keyword in text for keyword in macro_keywords):
            return "MACRO"
        return "TECHNICAL"

    def _extract_pnl(self, event: Dict[str, Any]) -> float:
        for key in ("pnl_pct", "profit_pct", "gross_pnl", "net_pnl"):
            if key in event:
                return self._safe_float(event.get(key), 0.0)
        return 0.0

    def _update_timestamps(self, data: Dict[str, Any], timestamp: Any) -> None:
        text = self._safe_text(timestamp)
        if not text:
            return
        if not data["created_at"] or text < data["created_at"]:
            data["created_at"] = text
        if not data["updated_at"] or text > data["updated_at"]:
            data["updated_at"] = text

    def _infer_status(self, confidence_score: float, total_events: int) -> str:
        if total_events <= 0:
            return "NO_HISTORY"
        if total_events < 5:
            return "LOW_SAMPLE"
        if confidence_score > 0.60:
            return "HIGH_CONFIDENCE"
        if confidence_score > 0.30:
            return "MEDIUM_CONFIDENCE"
        return "LOW_CONFIDENCE"

    def _safe_symbol(self, value: Any) -> str:
        return str(value or "").strip().upper()

    def _safe_upper(self, value: Any) -> str:
        return str(value or "").strip().upper()

    def _safe_text(self, value: Any) -> str:
        return str(value or "").strip()

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
