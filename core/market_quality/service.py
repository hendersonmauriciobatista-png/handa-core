# ============================================================
# core/market_quality/service.py
# MQII — Market Quality Internal Indicator
# Service oficial v1.0
# ============================================================

from typing import List, Optional, Dict

from core.market_quality.models import (
    MarketQualityAggregate,
    MarketQualitySnapshot,
)
from core.market_quality.aggregator import MarketQualityAggregator
from core.market_quality.evaluator import MarketQualityEvaluator
from core.market_quality.reversal_detector import MarketReversalDetector

# ============================================================
# core/market_quality/reversal_detector.py
# MQII — Detector de Virada de Mercado
# v1.0 Observador
# ============================================================

from typing import Dict, List, Optional


class MarketReversalDetector:
    """
    Detector observador de possível virada de mercado.

    Não decide trade.
    Não altera policy.
    Apenas observa a evolução do MQII ao longo dos ciclos.
    """

    def __init__(self, history_size: int = 10):
        self.history_size = history_size
        self.history: List[Dict] = []

    # ============================================================
    # HELPERS
    # ============================================================

    def _to_float(self, value, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _safe_upper(self, value) -> str:
        if value is None:
            return ""

        try:
            return str(value).strip().upper()
        except Exception:
            return ""

    def _push_snapshot(self, snapshot: Dict) -> None:
        self.history.append(snapshot)

        if len(self.history) > self.history_size:
            self.history.pop(0)

    def _score_series(self) -> List[float]:
        return [
            self._to_float(item.get("score", 0.0), default=0.0) for item in self.history
        ]

    def _is_rising_last_n(self, n: int = 3) -> bool:
        series = self._score_series()

        if len(series) < n:
            return False

        recent = series[-n:]

        for i in range(1, len(recent)):
            if recent[i] <= recent[i - 1]:
                return False

        return True

    # ============================================================
    # API
    # ============================================================

    def evaluate(self, snapshot: Optional[Dict]) -> Dict:
        """
        Recebe o snapshot atual do MQII e devolve um diagnóstico
        de possível pré-virada / virada.
        """
        if not isinstance(snapshot, dict):
            return {
                "reversal_state": "NO_DATA",
                "reversal_signal": False,
                "confidence": 0.0,
                "reason": "Snapshot inválido.",
                "score_delta": 0.0,
                "history_size": len(self.history),
            }

        self._push_snapshot(snapshot)

        current_score = self._to_float(snapshot.get("score", 0.0), default=0.0)
        current_state = self._safe_upper(snapshot.get("state", "UNKNOWN"))

        components = snapshot.get("components") or {}
        volume_component = self._to_float(components.get("volume", 0.0), default=0.0)
        trend_component = self._to_float(components.get("trend", 0.0), default=0.0)
        momentum_component = self._to_float(
            components.get("momentum", 0.0), default=0.0
        )

        previous_score = 0.0
        if len(self.history) >= 2:
            previous_score = self._to_float(
                self.history[-2].get("score", 0.0), default=0.0
            )

        score_delta = current_score - previous_score
        rising_3 = self._is_rising_last_n(3)

        # ========================================================
        # ESTADO PADRÃO
        # ========================================================
        reversal_state = "NONE"
        reversal_signal = False
        confidence = 0.0
        reason = "Sem sinais de virada."

        # ========================================================
        # PRÉ-VIRADA
        # ========================================================
        if (
            current_state == "NO_TRADE"
            and rising_3
            and current_score >= 0.12
            and volume_component >= 0.35
        ):
            reversal_state = "PRE_REVERSAL"
            reversal_signal = True
            confidence = 0.45
            reason = (
                "MQII em recuperação gradual com volume crescente, "
                "mas sem confirmação de momentum."
            )

        # ========================================================
        # VIRADA INICIANDO
        # ========================================================
        if (
            rising_3
            and current_score >= 0.25
            and volume_component >= 0.40
            and trend_component >= 0.10
            and momentum_component >= 0.05
        ):
            reversal_state = "REVERSAL_STARTED"
            reversal_signal = True
            confidence = 0.70
            reason = (
                "MQII mostra melhora consistente com avanço de volume, "
                "tendência e início de momentum."
            )

        return {
            "reversal_state": reversal_state,
            "reversal_signal": reversal_signal,
            "confidence": round(confidence, 4),
            "reason": reason,
            "score_delta": round(score_delta, 4),
            "history_size": len(self.history),
        }


class MarketQualityService:
    """
    Orquestrador do MQII.

    Responsabilidades:
    - receber dados do radar
    - agregar métricas
    - avaliar qualidade do mercado
    - retornar snapshot final
    """

    def __init__(self):
        self.aggregator = MarketQualityAggregator()
        self.evaluator = MarketQualityEvaluator()
        self.reversal_detector = MarketReversalDetector()

        self.last_snapshot: Optional[MarketQualitySnapshot] = None
        self.last_reversal_signal: Optional[Dict] = None

    # ============================================================
    # PIPELINE PRINCIPAL
    # ============================================================

    def evaluate_market(
        self,
        all_analyses: Optional[List[dict]],
        refined_tokens: Optional[List[dict]],
        approved_tokens: Optional[List[dict]],
        market_snapshot: Optional[Dict] = None,
    ) -> Dict:
        """
        Executa o pipeline completo do MQII.
        """

        aggregate: MarketQualityAggregate = self.aggregator.aggregate(
            all_analyses=all_analyses,
            refined_tokens=refined_tokens,
            approved_tokens=approved_tokens,
        )

        snapshot: MarketQualitySnapshot = self.evaluator.evaluate(aggregate)

        snapshot_dict = snapshot.to_dict()

        # ============================================================
        # 🔥 SINCRONIZAÇÃO COM SNAPSHOT DO RANKING
        # ============================================================
        if market_snapshot:
            snapshot_dict["refined_count"] = int(
                market_snapshot.get(
                    "refined_count", snapshot_dict.get("refined_count", 0)
                )
            )
            snapshot_dict["approved_count"] = int(
                market_snapshot.get(
                    "approved_count", snapshot_dict.get("approved_count", 0)
                )
            )
            snapshot_dict["avg_volume_ratio"] = float(
                market_snapshot.get(
                    "avg_volume_ratio", snapshot_dict.get("avg_volume_ratio", 0.0)
                )
            )
            snapshot_dict["uptrend_count"] = int(
                market_snapshot.get(
                    "uptrend_count", snapshot_dict.get("uptrend_count", 0)
                )
            )

        reversal_signal = self.reversal_detector.evaluate(snapshot_dict)

        self.last_snapshot = snapshot_dict
        self.last_reversal_signal = reversal_signal

        snapshot_dict["reversal"] = reversal_signal

        return snapshot_dict

    # ============================================================
    # ACESSO
    # ============================================================

    def get_last_snapshot(self) -> Optional[Dict]:
        return self.last_snapshot
