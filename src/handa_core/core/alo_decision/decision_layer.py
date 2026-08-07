# ============================================================
# core/alo_decision/decision_layer.py
# H&A - ALO Decision Layer
# Modo inicial: OBSERVER
# ============================================================

from typing import Any, Dict, Optional

from .decision_models import (
    AloDecisionInput,
    AloDecisionMode,
    AloDecisionResult,
)


class AloDecisionLayer:
    """
    Camada de decisão do ALO.

    Fase inicial:
    - modo OBSERVER
    - não bloqueia execução real
    - não altera capital real
    - não altera confiança real
    - apenas observa, pontua e registra sugestões
    """

    def __init__(
        self,
        mode: AloDecisionMode = AloDecisionMode.OBSERVER,
        min_events_for_confidence: int = 5,
        strong_block_bias_threshold: float = 0.75,
        weak_block_bias_threshold: float = 0.55,
        max_confidence_adjustment: float = 0.15,
        min_capital_adjustment: float = 0.85,
        max_capital_adjustment: float = 1.10,
    ):
        self.mode = mode
        self.min_events_for_confidence = int(min_events_for_confidence)
        self.strong_block_bias_threshold = float(strong_block_bias_threshold)
        self.weak_block_bias_threshold = float(weak_block_bias_threshold)
        self.max_confidence_adjustment = float(max_confidence_adjustment)
        self.min_capital_adjustment = float(min_capital_adjustment)
        self.max_capital_adjustment = float(max_capital_adjustment)

    # ============================================================
    # API PRINCIPAL
    # ============================================================

    def evaluate(self, data: AloDecisionInput) -> AloDecisionResult:
        result = AloDecisionResult(mode=self.mode)

        if not isinstance(data, AloDecisionInput):
            result.labels.append("ALO_INVALID_INPUT")
            result.reasons.append("input_invalido")
            result.diagnostics["invalid_input_type"] = str(type(data))
            return result

        symbol = str(data.symbol).upper().strip()

        if not symbol:
            result.labels.append("ALO_EMPTY_SYMBOL")
            result.reasons.append("symbol_vazio")
            return result

        result.diagnostics["symbol"] = symbol
        result.diagnostics["mode"] = self.mode.value
        result.diagnostics["profile_exists"] = bool(data.profile_exists)

        self._apply_profile_presence_analysis(data, result)
        self._apply_history_analysis(data, result)
        self._apply_block_bias_analysis(data, result)
        self._apply_confidence_analysis(data, result)
        self._apply_capital_analysis(data, result)
        self._finalize_observer_behavior(result)

        return result

    # ============================================================
    # ANÁLISES INTERNAS
    # ============================================================

    def _apply_profile_presence_analysis(
        self,
        data: AloDecisionInput,
        result: AloDecisionResult,
    ) -> None:
        if data.profile_exists:
            result.labels.append("ALO_PROFILE_PRESENT")
            result.reasons.append("perfil_encontrado")
        else:
            result.labels.append("ALO_PROFILE_MISSING")
            result.reasons.append("perfil_ausente")
            result.diagnostics["profile_fallback"] = True

    def _apply_history_analysis(
        self,
        data: AloDecisionInput,
        result: AloDecisionResult,
    ) -> None:
        total_events = max(0, int(data.total_events))
        execution_count = max(0, int(data.execution_count))
        non_execution_count = max(0, int(data.non_execution_count))
        structural_block_count = max(0, int(data.structural_block_count))
        quality_filter_count = max(0, int(data.quality_filter_count))
        low_score_count = max(0, int(data.low_score_count))
        loss_count = max(0, int(data.loss_count))
        win_count = max(0, int(data.win_count))

        result.score_components["total_events"] = float(total_events)
        result.score_components["execution_count"] = float(execution_count)
        result.score_components["non_execution_count"] = float(non_execution_count)
        result.score_components["structural_block_count"] = float(
            structural_block_count
        )
        result.score_components["quality_filter_count"] = float(quality_filter_count)
        result.score_components["low_score_count"] = float(low_score_count)
        result.score_components["loss_count"] = float(loss_count)
        result.score_components["win_count"] = float(win_count)

        if total_events <= 0:
            result.labels.append("ALO_NO_HISTORY")
            result.reasons.append("sem_historico")
            return

        result.labels.append("ALO_HISTORY_AVAILABLE")
        result.reasons.append("historico_disponivel")

        if total_events < self.min_events_for_confidence:
            result.labels.append("ALO_LOW_SAMPLE")
            result.reasons.append("amostra_pequena")
        else:
            result.labels.append("ALO_MIN_SAMPLE_OK")
            result.reasons.append("amostra_minima_ok")

        if non_execution_count > execution_count:
            result.labels.append("ALO_NON_EXECUTION_DOMINANT")
            result.reasons.append("nao_execucao_predominante")

        if structural_block_count > 0:
            result.labels.append("ALO_STRUCTURAL_MEMORY")
            result.reasons.append("memoria_estrutural")

        if quality_filter_count > 0:
            result.labels.append("ALO_QUALITY_MEMORY")
            result.reasons.append("memoria_quality_filter")

        if low_score_count > 0:
            result.labels.append("ALO_LOW_SCORE_MEMORY")
            result.reasons.append("memoria_score_baixo")

        if loss_count > win_count and loss_count > 0:
            result.labels.append("ALO_LOSS_DOMINANT")
            result.reasons.append("loss_predominante")

        if win_count > loss_count and win_count > 0:
            result.labels.append("ALO_WIN_DOMINANT")
            result.reasons.append("win_predominante")

    def _apply_block_bias_analysis(
        self,
        data: AloDecisionInput,
        result: AloDecisionResult,
    ) -> None:
        block_bias = self._clamp(float(data.block_bias), 0.0, 1.0)
        result.score_components["block_bias"] = block_bias
        result.diagnostics["block_bias"] = block_bias

        if block_bias >= self.strong_block_bias_threshold:
            result.labels.append("ALO_BLOCK_BIAS_STRONG")
            result.reasons.append("block_bias_forte")
            result.block_suggested = True

        elif block_bias >= self.weak_block_bias_threshold:
            result.labels.append("ALO_BLOCK_BIAS_MODERATE")
            result.reasons.append("block_bias_moderado")

        else:
            result.labels.append("ALO_BLOCK_BIAS_LOW")
            result.reasons.append("block_bias_baixo")

    def _apply_confidence_analysis(
        self,
        data: AloDecisionInput,
        result: AloDecisionResult,
    ) -> None:
        total_events = max(0, int(data.total_events))
        confidence_score = self._clamp(float(data.confidence_score), 0.0, 1.0)
        block_bias = self._clamp(float(data.block_bias), 0.0, 1.0)

        result.score_components["confidence_score"] = confidence_score
        result.diagnostics["confidence_score"] = confidence_score

        suggested_adjustment = 0.0

        if total_events < self.min_events_for_confidence:
            result.labels.append("ALO_CONFIDENCE_NEUTRAL_BY_SAMPLE")
            result.reasons.append("confianca_neutra_por_amostra")
            suggested_adjustment = 0.0

        else:
            if block_bias >= self.strong_block_bias_threshold:
                suggested_adjustment = -self.max_confidence_adjustment
                result.labels.append("ALO_CONFIDENCE_REDUCED")
                result.reasons.append("confianca_reduzida_por_block_bias")

            elif (
                confidence_score >= 0.70 and block_bias < self.weak_block_bias_threshold
            ):
                suggested_adjustment = self.max_confidence_adjustment * 0.50
                result.labels.append("ALO_CONFIDENCE_SOFT_BOOST")
                result.reasons.append("confianca_leve_positiva")

            else:
                result.labels.append("ALO_CONFIDENCE_NEUTRAL")
                result.reasons.append("confianca_neutra")
                suggested_adjustment = 0.0

        result.confidence_suggested = float(suggested_adjustment)

    def _apply_capital_analysis(
        self,
        data: AloDecisionInput,
        result: AloDecisionResult,
    ) -> None:
        total_events = max(0, int(data.total_events))
        confidence_score = self._clamp(float(data.confidence_score), 0.0, 1.0)
        block_bias = self._clamp(float(data.block_bias), 0.0, 1.0)

        capital_suggested = 1.0

        if total_events < self.min_events_for_confidence:
            result.labels.append("ALO_CAPITAL_NEUTRAL_BY_SAMPLE")
            result.reasons.append("capital_neutro_por_amostra")
            capital_suggested = 1.0

        else:
            if block_bias >= self.strong_block_bias_threshold:
                capital_suggested = self.min_capital_adjustment
                result.labels.append("ALO_CAPITAL_REDUCED")
                result.reasons.append("capital_reduzido_por_block_bias")

            elif (
                confidence_score >= 0.80 and block_bias < self.weak_block_bias_threshold
            ):
                capital_suggested = min(1.05, self.max_capital_adjustment)
                result.labels.append("ALO_CAPITAL_SOFT_BOOST")
                result.reasons.append("capital_leve_positivo")

            else:
                result.labels.append("ALO_CAPITAL_NEUTRAL")
                result.reasons.append("capital_neutro")
                capital_suggested = 1.0

        result.capital_suggested = float(
            self._clamp(
                capital_suggested,
                self.min_capital_adjustment,
                self.max_capital_adjustment,
            )
        )

    def _finalize_observer_behavior(self, result: AloDecisionResult) -> None:
        if self.mode == AloDecisionMode.OBSERVER:
            result.observer_only = True
            result.should_block = False
            result.confidence_adjustment = 0.0
            result.capital_adjustment = 1.0
            result.labels.append("ALO_OBSERVER_ONLY")
            result.reasons.append("sem_interferencia_real")
            return

        result.observer_only = False

        if self.mode == AloDecisionMode.ADVISORY:
            result.should_block = False
            result.confidence_adjustment = float(result.confidence_suggested)
            result.capital_adjustment = float(result.capital_suggested)
            result.labels.append("ALO_ADVISORY_MODE")
            result.reasons.append("ajuste_consultivo")
            return

        if self.mode == AloDecisionMode.ACTIVE:
            result.should_block = bool(result.block_suggested)
            result.confidence_adjustment = float(result.confidence_suggested)
            result.capital_adjustment = float(result.capital_suggested)
            result.labels.append("ALO_ACTIVE_MODE")
            result.reasons.append("ajuste_ativo_controlado")
            return

    # ============================================================
    # HELPERS
    # ============================================================

    def set_mode(self, mode: AloDecisionMode) -> None:
        self.mode = mode

    def get_mode(self) -> AloDecisionMode:
        return self.mode

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "min_events_for_confidence": self.min_events_for_confidence,
            "strong_block_bias_threshold": self.strong_block_bias_threshold,
            "weak_block_bias_threshold": self.weak_block_bias_threshold,
            "max_confidence_adjustment": self.max_confidence_adjustment,
            "min_capital_adjustment": self.min_capital_adjustment,
            "max_capital_adjustment": self.max_capital_adjustment,
        }

    @staticmethod
    def _clamp(value: Optional[float], min_value: float, max_value: float) -> float:
        if value is None:
            return float(min_value)

        if value < min_value:
            return float(min_value)

        if value > max_value:
            return float(max_value)

        return float(value)
