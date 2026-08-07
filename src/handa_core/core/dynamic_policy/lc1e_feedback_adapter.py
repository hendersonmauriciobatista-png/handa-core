# =============================================================================
# core/dynamic_policy/lc1e_feedback_adapter.py
# H&A — LC-1E Feedback Adapter
# Learning Core 1 Expanded
# Registro factual de eventos de NÃO execução
# =============================================================================

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class LC1EEvent:
    timestamp: str
    source: str
    event_type: str

    symbol: str
    reason: str
    summary: str

    trend: str
    momentum: str
    market_state: str
    volume_state: str

    rsi: float
    volume_ratio: float

    price: float
    ema_fast: float
    ema_slow: float

    market_score: float

    liquidity_score: float = 0.0
    liquidity_label: str = ""
    avg_volume_ratio: float = 0.0
    uptrend_count: int = 0
    refined_count: int = 0
    approved_count: int = 0


# =============================================================================
# ADAPTER
# =============================================================================

class LC1EFeedbackAdapter:
    """
    Learning Core 1 Expanded (LC-1E)

    Responsável por registrar eventos factuais de NÃO execução.
    Regras:
    - append-only
    - factual
    - sem interpretação
    - sem decisão automática
    """

    def __init__(self, storage_path: str = "storage/lc1e_events_v2.jsonl"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.storage_path.exists():
            self.storage_path.touch()

        print("[LC1EFeedbackAdapter] inicializado")

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------

    def record_event(self, event: LC1EEvent) -> None:
        payload = asdict(event)

        with self.storage_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def build_event(
        self,
        *,
        symbol: str,
        reason: str,
        analysis: Optional[Dict[str, Any]] = None,
        snapshot: Optional[Any] = None,
        market_context: Optional[Dict[str, Any]] = None,
        event_type: str = "NON_EXECUTION",
        source: str = "selection_policy_engine",
        summary: str = "",
    ) -> LC1EEvent:
        analysis = analysis or {}
        market_context = market_context or {}

        price = self._extract_price(snapshot, analysis)
        ema_fast = self._extract_ema_fast(snapshot, analysis)
        ema_slow = self._extract_ema_slow(snapshot, analysis)

        return LC1EEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            source=str(source or ""),
            event_type=str(event_type or "NON_EXECUTION"),

            symbol=str(symbol or "").strip().upper(),
            reason=str(reason or ""),
            summary=str(summary or ""),

            trend=str(analysis.get("trend", "")),
            momentum=str(analysis.get("momentum", "")),
            market_state=str(analysis.get("market_state", "")),
            volume_state=str(analysis.get("volume", "")),

            rsi=float(analysis.get("rsi", 0.0) or 0.0),
            volume_ratio=float(analysis.get("volume_ratio", 0.0) or 0.0),

            price=float(price or 0.0),
            ema_fast=float(ema_fast or 0.0),
            ema_slow=float(ema_slow or 0.0),

            market_score=float(analysis.get("market_score", 0.0) or 0.0),

            liquidity_score=float(market_context.get("liquidity_score", 0.0) or 0.0),
            liquidity_label=str(market_context.get("liquidity_label", "")),
            avg_volume_ratio=float(market_context.get("avg_volume_ratio", 0.0) or 0.0),
            uptrend_count=int(market_context.get("uptrend_count", 0) or 0),
            refined_count=int(market_context.get("refined_count", 0) or 0),
            approved_count=int(market_context.get("approved_count", 0) or 0),
        )

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _get_snapshot_value(self, snapshot: Any, key: str, default: float = 0.0) -> float:
        if snapshot is None:
            return default

        if isinstance(snapshot, dict):
            return snapshot.get(key, default)

        return getattr(snapshot, key, default)

    def _extract_price(self, snapshot: Any, analysis: Dict[str, Any]) -> float:
        return float(
            self._get_snapshot_value(snapshot, "close")
            or self._get_snapshot_value(snapshot, "price")
            or self._get_snapshot_value(snapshot, "last_price")
            or analysis.get("price")
            or 0.0
        )

    def _extract_ema_fast(self, snapshot: Any, analysis: Dict[str, Any]) -> float:
        return float(
            self._get_snapshot_value(snapshot, "ema_fast")
            or self._get_snapshot_value(snapshot, "ema_10")
            or self._get_snapshot_value(snapshot, "ema10")
            or analysis.get("ema_fast")
            or analysis.get("ema_10")
            or 0.0
        )

    def _extract_ema_slow(self, snapshot: Any, analysis: Dict[str, Any]) -> float:
        return float(
            self._get_snapshot_value(snapshot, "ema_slow")
            or self._get_snapshot_value(snapshot, "ema_20")
            or self._get_snapshot_value(snapshot, "ema20")
            or analysis.get("ema_slow")
            or analysis.get("ema_20")
            or 0.0
        )