# ============================================================
# core/alo/alo_vision_engine.py
# H&A — ALO Vision Engine
# Motor central da camada de visão contextual do ALO
# ============================================================

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.alo.market_context_builder import MarketContextBuilder
from core.alo.setup_context_builder import SetupContextBuilder
from core.alo.vision_models import (
    AloVisionSnapshot,
    MarketContext,
    SetupContext,
    VisionInference,
    build_vision_snapshot,
)


class AloVisionEngine:
    """
    Camada de visão contextual do ALO.

    Objetivo:
    - interpretar contexto macro de mercado
    - interpretar qualidade micro do setup
    - gerar uma leitura consolidada
    - NÃO decidir
    - NÃO executar
    """

    def __init__(
        self,
        market_context_builder: Optional[MarketContextBuilder] = None,
        setup_context_builder: Optional[SetupContextBuilder] = None,
    ):
        self.market_context_builder = market_context_builder or MarketContextBuilder()
        self.setup_context_builder = setup_context_builder or SetupContextBuilder()

    # ============================================================
    # PUBLIC API
    # ============================================================

    def analyze(
        self,
        snapshot: Optional[Any] = None,
        liquidity_data: Optional[Dict[str, Any]] = None,
        market_summary: Optional[Dict[str, Any]] = None,
    ) -> AloVisionSnapshot:
        setup_context = self.setup_context_builder.build(snapshot)
        market_context = self.market_context_builder.build(
            liquidity_data=liquidity_data,
            market_summary=market_summary,
        )

        inference = self._build_inference(
            market_context=market_context,
            setup_context=setup_context,
        )

        timestamp = self._now_iso()
        symbol = setup_context.symbol or self._resolve_symbol(snapshot)

        # ========================================================
        # GUARDA ESTRUTURAL
        # --------------------------------------------------------
        # Quando não existe símbolo real, o ALO pode continuar
        # retornando snapshot analítico interno, mas o resultado
        # não deve ser tratado como setup operacional válido.
        # Isso permite que camadas externas evitem log vazio como:
        # [ALO VISION] | conf=... | guide=...
        # ========================================================
        is_valid_setup = bool(symbol)

        return build_vision_snapshot(
            symbol=symbol,
            timestamp=timestamp,
            market_context=market_context,
            setup_context=setup_context,
            inference=inference,
            extra={
                "engine": "AloVisionEngine",
                "mode": "READ_ONLY",
                "is_valid_setup": is_valid_setup,
                "loggable": is_valid_setup,
            },
        )

    def analyze_to_dict(
        self,
        snapshot: Optional[Any] = None,
        liquidity_data: Optional[Dict[str, Any]] = None,
        market_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        result = self.analyze(
            snapshot=snapshot,
            liquidity_data=liquidity_data,
            market_summary=market_summary,
        )
        return result.to_dict()

    # ============================================================
    # INFERENCE CORE
    # ============================================================

    def _build_inference(
        self,
        market_context: MarketContext,
        setup_context: SetupContext,
    ) -> VisionInference:
        confidence_score = self._infer_confidence_score(
            market_context=market_context,
            setup_context=setup_context,
        )

        confidence_label = self._infer_confidence_label(confidence_score)

        expected_outcome = self._infer_expected_outcome(
            market_context=market_context,
            setup_context=setup_context,
            confidence_score=confidence_score,
        )

        guidance = self._infer_guidance(
            market_context=market_context,
            setup_context=setup_context,
            confidence_score=confidence_score,
        )

        reasons = self._build_reasons(
            market_context=market_context,
            setup_context=setup_context,
            confidence_score=confidence_score,
            guidance=guidance,
        )

        summary = self._build_summary(
            market_context=market_context,
            setup_context=setup_context,
            confidence_label=confidence_label,
            expected_outcome=expected_outcome,
            guidance=guidance,
        )

        return VisionInference(
            confidence_label=confidence_label,
            confidence_score=round(confidence_score, 4),
            expected_outcome=expected_outcome,
            guidance=guidance,
            summary=summary,
            reasons=reasons,
            extra={
                "market_state": market_context.market_state,
                "setup_quality": setup_context.quality_label,
            },
        )

    def _infer_confidence_score(
        self,
        market_context: MarketContext,
        setup_context: SetupContext,
    ) -> float:
        score = 0.0

        # ------------------------------------------------
        # QUALIDADE DO SETUP
        # ------------------------------------------------
        score += min(max(setup_context.quality_score, 0.0), 12.0)

        # ------------------------------------------------
        # LIQUIDEZ / CONTEXTO MACRO
        # ------------------------------------------------
        liq = market_context.liquidity_score

        if liq >= 0.75:
            score += 3.0
        elif liq >= 0.55:
            score += 2.0
        elif liq >= 0.35:
            score += 0.75
        elif liq > 0.0:
            score -= 1.0
        else:
            # 🔥 PROTEÇÃO: evitar penalização quando dado está ausente
            score += 0.0

        # ------------------------------------------------
        # DENSIDADE DE OPORTUNIDADES
        # ------------------------------------------------
        if market_context.opportunity_density == "ALTA":
            score += 2.0
        elif market_context.opportunity_density == "MODERADA":
            score += 1.0
        elif market_context.opportunity_density == "BAIXA":
            score -= 0.75
        elif market_context.opportunity_density == "NULA":
            score -= 1.0

        # ------------------------------------------------
        # FORÇA DE TENDÊNCIA
        # ------------------------------------------------
        if market_context.trend_strength == "FORTE":
            score += 1.5
        elif market_context.trend_strength == "MODERADA":
            score += 0.75
        elif market_context.trend_strength == "FRACA":
            score -= 0.5

        # ------------------------------------------------
        # REGRAS DE ATRITO / CONFLITO
        # ------------------------------------------------
        if market_context.market_state in ("LATERAL_FRACO", "UNKNOWN"):
            score -= 1.0

        if setup_context.quality_label == "RUIM":
            score -= 3.0

        if setup_context.price <= 0:
            score -= 4.0

        if market_context.market_state in (
            "LATERAL_FRACO",
            "NEUTRO_OPERAVEL",
        ) and setup_context.quality_label in ("FRACA", "RUIM"):
            score -= 1.0

        if market_context.market_state in (
            "BULLISH_FORTE",
            "BULLISH_MODERADO",
        ) and setup_context.quality_label in ("BOA", "FORTE"):
            score += 2.5

        if score < 0.0:
            return 0.0

        return score

    def _infer_confidence_label(self, score: float) -> str:
        if score >= 15.0:
            return "MUITO_ALTA"
        if score >= 11.0:
            return "ALTA"
        if score >= 7.0:
            return "MODERADA"
        if score >= 3.0:
            return "BAIXA"
        return "MUITO_BAIXA"

    def _infer_expected_outcome(
        self,
        market_context: MarketContext,
        setup_context: SetupContext,
        confidence_score: float,
    ) -> str:
        if setup_context.price <= 0:
            return "INVALID_SETUP"

        if market_context.market_state == "LATERAL_FRACO" and confidence_score < 7.0:
            return "LOSS_PROVAVEL"

        if market_context.market_state == "UNKNOWN":
            return "INCERTO"

        if confidence_score >= 15.0:
            return "SETUP_FORTE"

        if confidence_score >= 11.0:
            return "GAIN_PROVAVEL"

        if confidence_score >= 7.0:
            return "OPERAVEL_COM_CAUTELA"

        if confidence_score >= 3.0:
            return "RISCO_ELEVADO"

        return "LOSS_PROVAVEL"

    def _infer_guidance(
        self,
        market_context: MarketContext,
        setup_context: SetupContext,
        confidence_score: float,
    ) -> str:
        if setup_context.price <= 0:
            return "INVALIDAR"

        if market_context.market_state == "UNKNOWN":
            return "AGUARDAR"

        if market_context.market_state == "LATERAL_FRACO" and confidence_score < 7.0:
            return "EVITAR"

        if confidence_score >= 15.0:
            return "FAVORAVEL"

        if confidence_score >= 11.0:
            return "OBSERVAR_ENTRADA"

        if confidence_score >= 7.0:
            return "CAUTELA"

        if confidence_score >= 3.0:
            return "RISCO_ALTO"

        return "EVITAR"

    def _build_reasons(
        self,
        market_context: MarketContext,
        setup_context: SetupContext,
        confidence_score: float,
        guidance: str,
    ) -> list[str]:
        reasons: list[str] = []

        reasons.append(f"MARKET_STATE={market_context.market_state}")
        reasons.append(f"OPPORTUNITY_DENSITY={market_context.opportunity_density}")
        reasons.append(f"TREND_STRENGTH={market_context.trend_strength}")
        reasons.append(f"SETUP_QUALITY={setup_context.quality_label}")
        reasons.append(f"GUIDANCE={guidance}")
        reasons.append(f"CONFIDENCE_SCORE={round(confidence_score, 4)}")

        if market_context.liquidity_score > 0:
            reasons.append(
                f"LIQUIDITY_SCORE={round(market_context.liquidity_score, 4)}"
            )

        if setup_context.volume_ratio > 0:
            reasons.append(f"VOLUME_RATIO={round(setup_context.volume_ratio, 4)}")

        if setup_context.rsi > 0:
            reasons.append(f"RSI={round(setup_context.rsi, 4)}")

        if setup_context.price <= 0:
            reasons.append("STRUCTURE_INVALID_PRICE")

        if market_context.market_state in (
            "LATERAL_FRACO",
            "UNKNOWN",
        ) and setup_context.quality_label in ("FRACA", "RUIM"):
            reasons.append("MACRO_MICRO_CONFLICT")

        if market_context.market_state in (
            "BULLISH_FORTE",
            "BULLISH_MODERADO",
        ) and setup_context.quality_label in ("BOA", "FORTE"):
            reasons.append("MACRO_MICRO_ALIGNMENT")

        return reasons

    def _build_summary(
        self,
        market_context: MarketContext,
        setup_context: SetupContext,
        confidence_label: str,
        expected_outcome: str,
        guidance: str,
    ) -> str:
        return (
            f"ALO Vision | "
            f"mercado={market_context.market_state} | "
            f"setup={setup_context.quality_label} | "
            f"confianca={confidence_label} | "
            f"resultado={expected_outcome} | "
            f"guia={guidance}"
        )

    # ============================================================
    # HELPERS
    # ============================================================

    def _resolve_symbol(self, snapshot: Optional[Any]) -> str:
        if snapshot is None:
            return ""

        if isinstance(snapshot, dict):
            value = snapshot.get("pair") or snapshot.get("symbol") or ""
            return str(value).strip().upper()

        value = getattr(snapshot, "pair", None) or getattr(snapshot, "symbol", "")
        return str(value).strip().upper()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
