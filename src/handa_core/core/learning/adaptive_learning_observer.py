# ============================================================
# H&A — ADAPTIVE LEARNING OBSERVER (ALO)
# Observer passivo de aprendizado adaptativo
# ============================================================

from typing import Dict, Optional

from core.learning.learning_models import SymbolLearningProfile
from core.learning.learning_storage import LearningStorage


# ============================================================
# ADAPTIVE LEARNING OBSERVER
# ============================================================


class AdaptiveLearningObserver:
    """
    Observer passivo do H&A.

    Responsabilidades:
    - ingerir eventos do LC1E
    - consolidar estatísticas por ativo
    - calcular score de confiança
    - manter perfil de aprendizado por símbolo

    Limites:
    - não altera decisões do sistema
    - não executa ordens
    - não interfere no trading
    """

    def __init__(self):
        self.storage = LearningStorage()
        self.symbol_profiles = {}
        self._load_profiles_from_storage()

    # ============================================================
    # HELPERS
    # ============================================================

    def _normalize_symbol(self, symbol: str) -> str:
        return str(symbol).strip().upper()

    def _get_or_create_profile(self, symbol: str) -> SymbolLearningProfile:
        symbol = self._normalize_symbol(symbol)

        if symbol not in self.symbol_profiles:
            self.symbol_profiles[symbol] = SymbolLearningProfile(symbol=symbol)

        return self.symbol_profiles[symbol]

    def _load_profiles_from_storage(self):
        raw_profiles = self.storage.get_all_profiles()

        if not isinstance(raw_profiles, dict):
            return

        for symbol, data in raw_profiles.items():
            try:
                profile = SymbolLearningProfile(symbol=symbol)

                profile.attempts = data.get("attempts", 0)
                profile.approvals = data.get("approvals", 0)
                profile.rejections = data.get("rejections", {})
                profile.confidence_score = data.get("confidence_score", 0.0)
                profile.status = data.get("status", "UNKNOWN")

                self.symbol_profiles[symbol] = profile

            except Exception as e:
                print(f"[ALO LOAD ERROR] {symbol}: {e}")

    # ============================================================
    # INGESTÃO DE EVENTOS
    # ============================================================

    def ingest_event(self, event: dict):
        if not isinstance(event, dict):
            return

        symbol = self._normalize_symbol(event.get("symbol", ""))
        if not symbol:
            return

        event_type = str(event.get("event_type", "")).strip().upper()
        reason = str(event.get("reason", "")).strip().upper()

        analysis = event.get("analysis", {}) or {}
        market_context = event.get("market_context", {}) or {}
        snapshot = event.get("snapshot", {}) or {}

        stage = str(market_context.get("stage", "")).strip().upper()
        mqii_state = str(market_context.get("mqii_state", "")).strip().upper()

        try:
            liquidity_score = float(market_context.get("liquidity_score", 0.0) or 0.0)
        except Exception:
            liquidity_score = 0.0

        try:
            selection_score = float(analysis.get("selection_score", 0.0) or 0.0)
        except Exception:
            selection_score = 0.0

        try:
            volume_ratio = float(snapshot.get("volume_ratio", 0.0) or 0.0)
        except Exception:
            volume_ratio = 0.0

        try:
            rsi_14 = float(snapshot.get("rsi_14", 0.0) or 0.0)
        except Exception:
            rsi_14 = 0.0

        profile = self._get_or_create_profile(symbol)
        profile.register_attempt()

        if event_type == "BUY":
            profile.register_approval()

        elif event_type == "NON_EXECUTION":

            enriched_reason = reason

            # ======================================================
            # ENRIQUECIMENTO POR STAGE
            # ======================================================
            if stage:
                enriched_reason = f"{reason}_{stage}"

            # ======================================================
            # AJUSTE POR MQII (CONTEXTO DE MERCADO)
            # ======================================================
            if mqii_state == "NO_TRADE":
                enriched_reason = f"{enriched_reason}_MARKET_BAD"

            # ======================================================
            # AJUSTE POR LIQUIDEZ
            # ======================================================
            if liquidity_score < 0.3:
                enriched_reason = f"{enriched_reason}_LOW_LIQ"

            # ======================================================
            # AJUSTE POR QUALIDADE DE SETUP
            # ======================================================
            if selection_score < 0.3:
                enriched_reason = f"{enriched_reason}_WEAK_SETUP"

            profile.register_rejection(enriched_reason)
        elif event_type == "SELL":
            pass
        else:
            pass

        profile.calculate_score()
        profile.update_status()

        self.storage.replace_profile(
            symbol,
            {
                "symbol": profile.symbol,
                "attempts": profile.attempts,
                "approvals": profile.approvals,
                "rejections": profile.rejections,
                "confidence_score": profile.confidence_score,
                "status": profile.status,
            },
        )

    # ============================================================
    # CONSULTA
    # ============================================================

    def get_symbol_profile(self, symbol: str) -> Optional[SymbolLearningProfile]:
        symbol = self._normalize_symbol(symbol)
        return self.symbol_profiles.get(symbol)

    def get_all_profiles(self) -> Dict[str, SymbolLearningProfile]:
        return self.symbol_profiles

    def get_symbol_summary(self, symbol: str) -> Optional[dict]:
        profile = self.get_symbol_profile(symbol)
        if profile is None:
            return None

        return {
            "symbol": profile.symbol,
            "attempts": profile.attempts,
            "approvals": profile.approvals,
            "rejections": profile.rejections,
            "dominant_rejection_reason": profile.get_dominant_rejection_reason(),
            "confidence_score": profile.confidence_score,
            "status": profile.status,
        }

    def get_learning_summary(self) -> dict:
        total_symbols = len(self.symbol_profiles)

        approved_symbols = 0
        blocked_symbols = 0
        learning_symbols = 0

        top_confidence = []

        for symbol, profile in self.symbol_profiles.items():
            status = str(profile.status).strip().upper()

            if status == "APPROVED":
                approved_symbols += 1
            elif status in ("BLOCKED", "REJECTED"):
                blocked_symbols += 1
            else:
                learning_symbols += 1

            top_confidence.append(
                {
                    "symbol": profile.symbol,
                    "confidence_score": profile.confidence_score,
                    "attempts": profile.attempts,
                    "approvals": profile.approvals,
                    "dominant_rejection_reason": profile.get_dominant_rejection_reason(),
                    "status": profile.status,
                }
            )

        top_confidence.sort(
            key=lambda item: (
                float(item.get("confidence_score", 0.0)),
                int(item.get("attempts", 0)),
            ),
            reverse=True,
        )

        return {
            "total_symbols": total_symbols,
            "approved_symbols": approved_symbols,
            "blocked_symbols": blocked_symbols,
            "learning_symbols": learning_symbols,
            "top_symbols": top_confidence[:10],
        }
