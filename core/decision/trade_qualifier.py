# ============================================================
# H&A - Trade Qualifier
# Qualificação de setup de entrada
# ============================================================

from dataclasses import dataclass


@dataclass
class QualificationResult:
    approved: bool
    mode: str
    reason: str
    size_multiplier: float = 1.0


class TradeQualifier:
    """
    Verifica se o setup atende os requisitos mínimos
    para existir como trade potencial.

    Modos possíveis:
    - NORMAL: setup forte
    - OPPORTUNITY: setup imperfeito, mas protegido
    - REJECTED: setup inválido
    """

    # ========================================================
    # NORMAL MODE
    # ========================================================
    NORMAL_MIN_RSI = 52.0
    NORMAL_MAX_RSI = 68.0
    NORMAL_MIN_VOLUME_RATIO = 1.20

    # ========================================================
    # OPPORTUNITY MODE
    # ========================================================
    OPPORTUNITY_ENABLED = True
    OPPORTUNITY_MIN_RSI = 45.0
    OPPORTUNITY_MAX_RSI = 62.0
    OPPORTUNITY_MIN_VOLUME_RATIO = 1.20
    OPPORTUNITY_SIZE_MULTIPLIER = 0.50

    # ========================================================
    # PUBLIC API
    # ========================================================
    def qualify(self, snapshot):
        """
        Recebe o snapshot/análise do ativo e devolve QualificationResult.
        """

        trend = self._safe_upper(self._read(snapshot, "trend"))
        momentum = self._safe_upper(self._read(snapshot, "momentum"))
        market_state = self._safe_upper(self._read(snapshot, "market_state"))
        volume_state = self._safe_upper(self._read(snapshot, "volume"))
        if volume_state == "":
            volume_state = self._safe_upper(self._read(snapshot, "volume_state"))

        rsi = self._to_float(self._read(snapshot, "rsi"))
        if rsi is None:
            rsi = self._to_float(self._read(snapshot, "rsi_14"))

        volume_ratio = self._to_float(self._read(snapshot, "volume_ratio"), default=0.0)
        ema_fast = self._to_float(self._read(snapshot, "ema_10"))
        ema_slow = self._to_float(self._read(snapshot, "ema_20"))

        # ----------------------------------------------------
        # Validação estrutural mínima
        # ----------------------------------------------------
        if trend != "UPTREND":
            return QualificationResult(
                approved=False,
                mode="REJECTED",
                reason="TREND_NOT_UPTREND",
            )

        if ema_fast is None or ema_slow is None:
            return QualificationResult(
                approved=False,
                mode="REJECTED",
                reason="EMA_DATA_MISSING",
            )

        if ema_fast <= ema_slow:
            return QualificationResult(
                approved=False,
                mode="REJECTED",
                reason="EMA_STRUCTURE_INVALID",
            )

        if rsi is None:
            return QualificationResult(
                approved=False,
                mode="REJECTED",
                reason="RSI_MISSING",
            )

        if rsi >= 75.0:
            return QualificationResult(
                approved=False,
                mode="REJECTED",
                reason="RSI_EXTREME",
            )

        if volume_ratio <= 0:
            return QualificationResult(
                approved=False,
                mode="REJECTED",
                reason="VOLUME_RATIO_INVALID",
            )

        if volume_state not in {"MODERATE", "HIGH"}:
            return QualificationResult(
                approved=False,
                mode="REJECTED",
                reason="VOLUME_STATE_TOO_LOW",
            )

        # ----------------------------------------------------
        # NORMAL MODE
        # ----------------------------------------------------
        if (
            momentum == "BULLISH"
            and market_state in {"BULLISH", "BULLISH_STRONG"}
            and self.NORMAL_MIN_RSI <= rsi <= self.NORMAL_MAX_RSI
            and volume_ratio >= self.NORMAL_MIN_VOLUME_RATIO
        ):
            return QualificationResult(
                approved=True,
                mode="NORMAL",
                reason="NORMAL_SETUP_APPROVED",
                size_multiplier=1.0,
            )

        # ----------------------------------------------------
        # OPPORTUNITY MODE
        # ----------------------------------------------------
        if self.OPPORTUNITY_ENABLED:
            if (
                momentum == "NEUTRAL"
                and market_state
                in {"SIDEWAYS", "BULLISH", "BULLISH_WEAK", "BULLISH_STRONG"}
                and self.OPPORTUNITY_MIN_RSI <= rsi <= self.OPPORTUNITY_MAX_RSI
                and volume_ratio >= self.OPPORTUNITY_MIN_VOLUME_RATIO
            ):
                return QualificationResult(
                    approved=True,
                    mode="OPPORTUNITY",
                    reason="OPPORTUNITY_SETUP_APPROVED",
                    size_multiplier=self.OPPORTUNITY_SIZE_MULTIPLIER,
                )

        # ----------------------------------------------------
        # Fallback final
        # ----------------------------------------------------
        return QualificationResult(
            approved=False,
            mode="REJECTED",
            reason="SETUP_NOT_QUALIFIED",
        )

    # ========================================================
    # HELPERS
    # ========================================================
    def _read(self, snapshot, key):
        """
        Lê valor tanto de dict quanto de objeto.
        """
        if snapshot is None:
            return None

        if isinstance(snapshot, dict):
            return snapshot.get(key)

        return getattr(snapshot, key, None)

    def _safe_upper(self, value):
        """
        Normaliza enums/strings para comparação.
        Ex:
        TrendDirection.UPTREND -> UPTREND
        """
        if value is None:
            return ""

        text = str(value).strip().upper()

        if "." in text:
            text = text.split(".")[-1]

        return text

    def _to_float(self, value, default=None):
        if value is None:
            return default

        try:
            return float(value)
        except (TypeError, ValueError):
            return default
