# ============================================================
# core/alo_profile/profile_updater.py
# Atualizador dos perfis do ALO com base em eventos LC1/LC1E
# ============================================================

from typing import Any, Dict, Optional

from core.alo_profile.profile_models import AloSymbolProfile
from core.alo_profile.profile_store import AloProfileStore


class AloProfileUpdater:
    def __init__(self, store: Optional[AloProfileStore] = None):
        self.store = store or AloProfileStore()

    def _safe_symbol(self, symbol: Any) -> str:
        return str(symbol or "").strip().upper()

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _safe_str(self, value: Any) -> str:
        return str(value or "").strip()

    def _append_limited(self, items, value, limit: int = 20):
        items = list(items or [])
        items.append(value)
        if len(items) > limit:
            items = items[-limit:]
        return items

    def _classify_non_execution(self, reason: str) -> str:
        text = self._safe_str(reason).upper()

        if not text:
            return "UNKNOWN"

        structural_keywords = [
            "STRUCTURE",
            "STRUCTURAL",
            "BLACKLIST",
            "HARD_BLOCK",
            "SOFT_BLOCK",
            "PROFILE_BLOCK",
        ]

        macro_keywords = [
            "NO_TRADE",
            "MQII",
            "MACRO",
            "MARKET_BLOCK",
            "GLOBAL_BLOCK",
        ]

        for keyword in structural_keywords:
            if keyword in text:
                return "STRUCTURAL"

        for keyword in macro_keywords:
            if keyword in text:
                return "MACRO"

        return "TECHNICAL"

    def register_trade_result(
        self,
        symbol: str,
        pnl_pct: float,
        close_reason: str = "",
        market_state: str = "",
    ) -> AloSymbolProfile:
        safe_symbol = self._safe_symbol(symbol)
        if not safe_symbol:
            return AloSymbolProfile(symbol="UNKNOWN")

        safe_pnl = self._safe_float(pnl_pct, 0.0)
        safe_reason = self._safe_str(close_reason)
        safe_market_state = self._safe_str(market_state)

        def _update(profile: AloSymbolProfile) -> AloSymbolProfile:
            profile.total_trades += 1

            if safe_pnl > 0:
                profile.wins += 1
            else:
                profile.losses += 1

            profile.recent_results = self._append_limited(
                profile.recent_results,
                round(safe_pnl, 6),
                limit=20,
            )

            if safe_reason:
                profile.recent_reasons = self._append_limited(
                    profile.recent_reasons,
                    safe_reason,
                    limit=20,
                )

            profile.last_market_state = safe_market_state

            # =========================
            # PENALIDADES INICIAIS
            # =========================
            upper_reason = safe_reason.upper()
            upper_market = safe_market_state.upper()

            if safe_pnl <= 0 and "LATERAL" in upper_market:
                profile.lateral_penalty += 0.15

            false_breakout_markers = [
                "DYNAMIC_STAGNATION",
                "DYNAMIC_HARD_EXIT",
                "STOP_LOSS",
                "FALSE_BREAKOUT",
            ]
            if safe_pnl <= 0 and any(
                marker in upper_reason for marker in false_breakout_markers
            ):
                profile.false_breakout_penalty += 0.20

            # =========================
            # LIMITES DE SEGURANÇA
            # =========================
            profile.lateral_penalty = max(0.0, min(profile.lateral_penalty, 3.0))
            profile.false_breakout_penalty = max(
                0.0, min(profile.false_breakout_penalty, 3.0)
            )

            return profile

        return self.store.update_profile(safe_symbol, _update)

    def register_non_execution(
        self,
        symbol: str,
        reason: str = "",
        market_state: str = "",
    ) -> AloSymbolProfile:
        safe_symbol = self._safe_symbol(symbol)
        if not safe_symbol:
            return AloSymbolProfile(symbol="UNKNOWN")

        safe_reason = self._safe_str(reason)
        safe_market_state = self._safe_str(market_state)
        reason_class = self._classify_non_execution(safe_reason)

        def _update(profile: AloSymbolProfile) -> AloSymbolProfile:
            profile.non_execution_count += 1
            profile.last_market_state = safe_market_state

            if safe_reason:
                profile.recent_reasons = self._append_limited(
                    profile.recent_reasons,
                    safe_reason,
                    limit=20,
                )

            if reason_class == "STRUCTURAL":
                profile.structural_rejections += 1
                profile.block_bias += 0.10

            elif reason_class == "MACRO":
                profile.macro_block_count += 1

            else:
                profile.technical_rejections += 1
                profile.block_bias += 0.05

            profile.block_bias = max(0.0, min(profile.block_bias, 3.0))
            return profile

        return self.store.update_profile(safe_symbol, _update)

    def update_from_event(self, event: Dict[str, Any]) -> Optional[AloSymbolProfile]:
        if not isinstance(event, dict):
            return None

        event_type = self._safe_str(event.get("event_type", "")).upper()
        symbol = self._safe_symbol(event.get("symbol", ""))
        if not symbol:
            return None

        market_state = self._safe_str(event.get("market_state", ""))
        reason = self._safe_str(event.get("reason", ""))

        if event_type == "SELL":
            pnl_pct = self._safe_float(
                event.get("pnl_pct", event.get("profit_pct", 0.0)),
                0.0,
            )
            return self.register_trade_result(
                symbol=symbol,
                pnl_pct=pnl_pct,
                close_reason=reason,
                market_state=market_state,
            )

        if event_type == "NON_EXECUTION":
            return self.register_non_execution(
                symbol=symbol,
                reason=reason,
                market_state=market_state,
            )

        return None
