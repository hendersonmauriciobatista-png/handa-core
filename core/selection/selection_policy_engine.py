# =============================================================================
# core/selection/selection_policy_engine.py
# H&A — Selection Policy Engine
# Núcleo soberano de seleção de ativos
# =============================================================================

from dataclasses import dataclass, field
from core.lc1.lc1_logger import LC1Logger
from typing import List
from core.dynamic_policy.lc1e_feedback_adapter import LC1EFeedbackAdapter
from core.selection_dynamic.selection_dynamic_policy import SelectionDynamicPolicy

# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class SelectionInput:
    symbol: str

    # ===== ANALYSIS =====
    trend: str
    momentum: str
    market_state: str
    volume_state: str

    # ===== INDICADORES =====
    rsi: float
    volume_ratio: float

    # ===== PREÇO / ESTRUTURA =====
    price: float
    ema_fast: float
    ema_slow: float

    # ===== OPCIONAL (TRANSIÇÃO) =====
    market_score: float = 0.0


@dataclass
class PartialScores:
    trend: float = 0.0
    momentum: float = 0.0
    rsi: float = 0.0
    volume: float = 0.0
    market: float = 0.0


@dataclass
class SelectionDecision:
    symbol: str
    approved: bool
    final_score: float
    partial_scores: PartialScores
    rejection_reasons: List[str] = field(default_factory=list)
    approval_reasons: List[str] = field(default_factory=list)
    is_trending: bool = False
    is_sideways_operable: bool = False
    summary: str = ""


# =============================================================================
# ENGINE
# =============================================================================


class SelectionPolicyEngine:
    """
    Núcleo soberano de seleção de ativos do H&A.

    Responsável apenas por:
    - validar inputs
    - aplicar filtros estruturais
    - calcular score
    - aprovar/rejeitar ativos
    - ordenar ativos aprovados

    Não é responsável por:
    - execução de BUY/SELL
    - capital
    - risco
    - penalty operacional
    - slots
    - validações de exchange
    """

    def __init__(self):
        self.lc1e = LC1EFeedbackAdapter()
        self.dynamic_policy = SelectionDynamicPolicy()
        self._last_min_score_result = None
        print("[SelectionPolicyEngine] inicializado")

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------

    def evaluate(self, token) -> SelectionDecision:

        # =========================
        # BUILD INPUT
        # =========================
        data = self._build_input(token)

        try:
            self._validate_input(data)
        except Exception as e:
            print(
                "[SELECTION DEBUG] INVALID_INPUT | "
                f"symbol={data.symbol} | "
                f"price={data.price} | "
                f"ema_fast={data.ema_fast} | "
                f"ema_slow={data.ema_slow} | "
                f"rsi={data.rsi} | "
                f"volume_ratio={data.volume_ratio} | "
                f"erro={e}"
            )

            # LC-1E REGISTRO
            self._record_lc1e_event(
                token=token,
                reason="INVALID_INPUT",
                summary=str(e),
            )

            decision = self._build_decision(
                data=data,
                approved=False,
                final_score=0.0,
                partial_scores=PartialScores(),
                rejection_reasons=["INVALID_INPUT"],
                approval_reasons=[],
                is_trending=False,
                is_sideways_operable=False,
                summary=str(e),
            )
            self._log_selection_semantic(
                data=data,
                decision=decision,
                min_required=None,
                market_context={},
                reason_detail="INVALID_INPUT",
            )

            return decision

        # =========================
        # HARD FILTERS
        # =========================
        hard_reasons = self._check_hard_filters(data)
        if hard_reasons:
            decision = self._build_decision(
                data=data,
                approved=False,
                final_score=0.0,
                partial_scores=PartialScores(),
                rejection_reasons=hard_reasons,
                approval_reasons=[],
                is_trending=False,
                is_sideways_operable=False,
                summary="HARD_FILTER",
            )
            self._log_decision(decision)
            self._log_selection_semantic(
                data=data,
                decision=decision,
                min_required=None,
                market_context=token.get("market_context", {}) or {},
                reason_detail="HARD_FILTER",
            )

            self._record_lc1e_event(
                token=token,
                reason="|".join(hard_reasons),
                summary="HARD_FILTER",
            )

            return decision

        # =========================
        # STRUCTURAL CHECKS
        # =========================
        structural_reasons = self._check_structural_eligibility(data)

        is_trending = self._check_structural_trend(data)
        is_sideways = self._check_sideways_operable(data)

        if structural_reasons:
            decision = self._build_decision(
                data=data,
                approved=False,
                final_score=0.0,
                partial_scores=PartialScores(),
                rejection_reasons=structural_reasons,
                approval_reasons=[],
                is_trending=is_trending,
                is_sideways_operable=is_sideways,
                summary="STRUCTURAL_REJECTION",
            )
            self._log_decision(decision)
            self._log_selection_semantic(
                data=data,
                decision=decision,
                min_required=None,
                market_context=token.get("market_context", {}) or {},
                reason_detail="STRUCTURAL_REJECTION",
            )

            # LC-1E REGISTRO
            self._record_lc1e_event(
                token=token,
                reason="|".join(structural_reasons),
                summary="STRUCTURAL_REJECTION",
            )

            return decision

        # =========================
        # SCORING
        # =========================
        partials = self._compute_partial_scores(data)
        final_score = self._compose_final_score(partials)

        # ========================================================
        # 🔥 ALO SCORE ADJUSTMENT (LIGHT)
        # ========================================================
        alo = token.get("alo_guidance")

        if alo:
            try:
                confidence = str(getattr(alo, "confidence_level", "")).upper()

                if confidence == "LOW":
                    final_score -= 0.05

                elif confidence == "HIGH":
                    final_score += 0.03

            except Exception as e:
                print(f"[ALO SCORE ERROR] {data.symbol} | erro={e}")

        # =========================
        # FINAL DECISION
        # =========================
        market_context = token.get("market_context", {}) or {}

        # 🔥 PROTEÇÃO CONTEXTUAL
        if not market_context or market_context.get("approved_count", 0) == 0:
            fallback_context = token.get("analysis", {}) or {}

            market_context = {
                "mqii_state": str(
                    fallback_context.get("market_state", "CAUTIOUS")
                ).upper(),
                "liquidity_score": float(
                    fallback_context.get("liquidity_score", 0.5) or 0.5
                ),
                "approved_count": int(fallback_context.get("approved_count", 1) or 1),
                "uptrend_count": int(fallback_context.get("uptrend_count", 5) or 5),
                "avg_volume_ratio": float(
                    fallback_context.get("volume_ratio", 1.0) or 1.0
                ),
            }

        # ========================================================
        # 🔥 EXCEÇÃO PREMIUM (CONTROLADA)
        # ========================================================
        premium_override = False

        try:
            trend = str(data.trend).upper()
            momentum = str(data.momentum).upper()
            state = str(data.market_state).upper()
            volume = float(data.volume_ratio)
            score = float(final_score)

            if (
                trend == "UPTREND"
                and state == "SIDEWAYS"
                and momentum == "NEUTRAL"
                and volume >= 1.2
                and score >= 0.80
            ):

                mqii_state = str(market_context.get("mqii_state", "")).upper()
                avg_volume_ratio = float(
                    market_context.get("avg_volume_ratio", 0.0) or 0.0
                )
                approved_count = int(market_context.get("approved_count", 0) or 0)

                # ======================================================
                # 🔥 H&A PATCH — PREMIUM CONTEXT FILTER
                # ======================================================
                # Só permite premium se o mercado estiver minimamente saudável
                # ======================================================

                allow_premium = False

                if mqii_state == "TRADE_OK":
                    allow_premium = True

                elif mqii_state == "CAUTIOUS":

                    # ======================================================
                    # 🔥 CIE-X PATCH — PREMIUM RECOVERY CONTEXTUAL
                    # ======================================================
                    # Mercado moderado não deve congelar totalmente
                    # setups premium reais.
                    #
                    # Objetivo:
                    # - evitar loop fechado de approved_count
                    # - permitir recuperação controlada
                    # - preservar proteção institucional
                    # ======================================================

                    if avg_volume_ratio >= 1.0:

                        # Mercado já saudável
                        if approved_count >= 2:
                            allow_premium = True

                        # 🔥 recuperação contextual controlada
                        elif score >= 0.85 and volume >= 1.5 and trend == "UPTREND":
                            allow_premium = True

                if allow_premium:
                    premium_override = True

                    print(
                        f"[PREMIUM OVERRIDE] {data.symbol} | "
                        f"score={score:.4f} | trend={trend} | "
                        f"momentum={momentum} | state={state} | vol={volume:.2f} | "
                        f"mqii={mqii_state}"
                    )

        except Exception as e:
            print(f"[PREMIUM OVERRIDE ERROR] {data.symbol} | erro={e}")

        # ========================================================
        # DECISÃO FINAL
        # ========================================================
        self._last_min_score_result = None
        approved = premium_override or self._check_min_score(
            final_score, data, market_context
        )
        min_score_result = self._last_min_score_result
        min_required = None
        reason_detail = "PREMIUM_OVERRIDE" if premium_override else "UNKNOWN"

        if min_score_result is not None:
            min_required = min_score_result.min_score_required
            reason_detail = min_score_result.reason

        decision = self._build_decision(
            data=data,
            approved=approved,
            final_score=final_score,
            partial_scores=partials,
            rejection_reasons=[] if approved else ["SCORE_BELOW_MIN"],
            approval_reasons=["SCORE_OK"] if approved else [],
            is_trending=is_trending,
            is_sideways_operable=is_sideways,
            summary="FINAL_DECISION",
        )

        self._log_decision(decision)
        self._log_selection_semantic(
            data=data,
            decision=decision,
            min_required=min_required,
            market_context=market_context,
            reason_detail=reason_detail,
        )

        # LC-1E REGISTRO
        if not approved:
            self._record_lc1e_event(
                token=token,
                reason="SCORE_BELOW_MIN",
                summary="FINAL_DECISION",
            )

        return decision

    def evaluate_many(self, opportunities) -> List[SelectionDecision]:
        decisions: List[SelectionDecision] = []

        if not opportunities:
            return decisions

        for token in opportunities:
            try:
                decision = self.evaluate(token)
                decisions.append(decision)
            except Exception as e:
                symbol = (
                    str(token.get("symbol") or token.get("pair") or "UNKNOWN")
                    .strip()
                    .upper()
                )

                decisions.append(
                    SelectionDecision(
                        symbol=symbol,
                        approved=False,
                        final_score=0.0,
                        partial_scores=PartialScores(),
                        rejection_reasons=["EVALUATION_ERROR"],
                        approval_reasons=[],
                        is_trending=False,
                        is_sideways_operable=False,
                        summary=str(e),
                    )
                )

        return decisions

    def get_approved_ranked(self, decisions) -> list:
        if not decisions:
            return []

        approved = [d for d in decisions if d.approved]

        approved.sort(key=lambda d: d.final_score, reverse=True)

        return approved

    # -------------------------------------------------------------------------
    # INPUT / VALIDATION
    # -------------------------------------------------------------------------

    def _build_input(self, token) -> SelectionInput:
        analysis = token.get("analysis", {}) or {}
        print(f"[DEBUG BUILD_INPUT ANALYSIS] {analysis}")
        snapshot = token.get("snapshot")

        symbol = str(token.get("symbol") or token.get("pair") or "").strip().upper()

        # compatibilidade: snapshot pode ser dict OU objeto
        def get_snapshot_value(obj, key, default=0.0):
            if obj is None:
                return default

            # dict
            if isinstance(obj, dict):
                return obj.get(key, default)

            # objeto (IndicatorSnapshot)
            return getattr(obj, key, default)

        # =====================================================
        # PRICE FALLBACKS
        # =====================================================
        price = (
            get_snapshot_value(snapshot, "close")
            or getattr(snapshot, "close", None)
            or getattr(snapshot, "price", None)
            or getattr(snapshot, "last_price", None)
            or analysis.get("price")
            or token.get("price")
            or 0.0
        )

        # =====================================================
        # EMA FALLBACKS
        # Padrão preferencial:
        # - ema_fast  -> ema_fast ou ema_10
        # - ema_slow  -> ema_slow ou ema_20
        # =====================================================
        ema_fast = (
            get_snapshot_value(snapshot, "ema_fast")
            or get_snapshot_value(snapshot, "ema_10")
            or get_snapshot_value(snapshot, "ema10")
            or analysis.get("ema_fast")
            or analysis.get("ema_10")
            or 0.0
        )

        ema_slow = (
            get_snapshot_value(snapshot, "ema_slow")
            or get_snapshot_value(snapshot, "ema_20")
            or get_snapshot_value(snapshot, "ema20")
            or analysis.get("ema_slow")
            or analysis.get("ema_20")
            or 0.0
        )

        # =====================================================
        # CORREÇÃO DEFINITIVA DE PREÇO (ANTI-ZERO)
        # =====================================================
        if not price or price <= 0:
            if ema_fast and ema_slow:
                price = (ema_fast + ema_slow) / 2
            elif ema_fast:
                price = ema_fast
            elif ema_slow:
                price = ema_slow

        # =====================================================
        # FALLBACK FINAL DE PREÇO (DEBUG + PROTEÇÃO)
        # =====================================================
        if not price or price <= 0:
            print(f"[PRICE FIX] {symbol} veio sem preço válido ...")

            if ema_fast and ema_slow:
                price = (ema_fast + ema_slow) / 2
            elif ema_fast:
                price = ema_fast
            elif ema_slow:
                price = ema_slow

        return SelectionInput(
            symbol=symbol,
            # ===== ANALYSIS =====
            trend=self._normalize_enum_value(analysis.get("trend")),
            momentum=self._normalize_enum_value(analysis.get("momentum")),
            market_state=self._normalize_enum_value(analysis.get("market_state")),
            volume_state=self._normalize_enum_value(analysis.get("volume")),
            # ===== INDICADORES =====
            rsi=float(analysis.get("rsi", 0.0) or 0.0),
            volume_ratio=float(analysis.get("volume_ratio", 0.0) or 0.0),
            # ===== PREÇO / ESTRUTURA =====
            price=float(price or 0.0),
            ema_fast=float(ema_fast or 0.0),
            ema_slow=float(ema_slow or 0.0),
            # ===== TRANSIÇÃO =====
            market_score=float(analysis.get("market_score", 0.0) or 0.0),
        )

    def _normalize_enum_value(self, value) -> str:
        if value is None:
            return ""

        # Caso seja Enum real
        if hasattr(value, "value"):
            return str(value.value).strip().upper()

        raw = str(value).strip()

        # Caso venha como "TrendDirection.UPTREND"
        if "." in raw:
            raw = raw.split(".")[-1]

        return raw.upper()

    def _validate_input(self, data: SelectionInput) -> None:

        if not data.symbol:
            raise ValueError("SelectionInput inválido: symbol vazio")

        if data.price <= 0:
            raise ValueError(f"{data.symbol}: preço inválido")

        if data.ema_fast <= 0 or data.ema_slow <= 0:
            raise ValueError(f"{data.symbol}: EMAs inválidas")

        # RSI pode ser 0 em alguns casos, mas tratamos como inválido estruturalmente
        if data.rsi <= 0:
            raise ValueError(f"{data.symbol}: RSI inválido")

        # Volume pode ser 0, mas não pode ser negativo
        if data.volume_ratio < 0:
            raise ValueError(f"{data.symbol}: volume_ratio inválido")

    # -------------------------------------------------------------------------
    # STRUCTURAL FILTERS
    # -------------------------------------------------------------------------

    def _check_symbol_block(self, symbol: str) -> bool:
        blocked_keywords = {
            "PEPE",
            "TRUMP",
            "DOGE",
            "SHIB",
            "FLOKI",
            "ROBO",
            "SAHARA",
            "BANANAS",
            "TURBO",
            "PENGU",
            "WIF",
        }

        normalized = str(symbol).strip().upper()
        return any(keyword in normalized for keyword in blocked_keywords)

    def _check_hard_filters(self, data: SelectionInput) -> List[str]:
        reasons: List[str] = []

        if self._check_symbol_block(data.symbol):
            reasons.append("SYMBOL_BLOCKED")

        if data.rsi > 75:
            reasons.append("RSI_EXTREMO")

        if data.volume_ratio >= 4.0:
            reasons.append("VOLUME_EXTREMO")

        return reasons

    def _check_structural_trend(self, data: SelectionInput) -> bool:
        trend_value = str(data.trend).strip().upper()
        return trend_value == "UPTREND"

    def _check_structural_spread(self, data: SelectionInput) -> bool:
        if data.price <= 0:
            return False

        spread = abs(data.ema_fast - data.ema_slow) / data.price
        return spread >= 0.0003

    def _check_sideways_operable(self, data: SelectionInput) -> bool:
        market_state = str(data.market_state).strip().upper()

        if market_state != "SIDEWAYS":
            return False

        if data.price <= 0:
            return False

        spread = abs(data.ema_fast - data.ema_slow) / data.price

        # -----------------------------------------------------
        # 🔥 DINÂMICO
        # -----------------------------------------------------

        if data.volume_ratio >= 1.5:
            min_spread = 0.00025
            min_rsi = 40.0

        elif data.volume_ratio >= 1.0:
            min_spread = 0.00030
            min_rsi = 42.0

        else:
            min_spread = 0.00035
            min_rsi = 45.0

        return (
            data.ema_fast > data.ema_slow
            and spread >= min_spread
            and data.rsi >= min_rsi
            and data.volume_ratio >= 0.9
        )

    def _check_structural_rsi(self, data: SelectionInput) -> bool:
        return data.rsi >= 45.0

    def _check_structural_volume(self, data: SelectionInput) -> bool:
        return data.volume_ratio >= 0.9

    def _check_structural_eligibility(self, data: SelectionInput) -> List[str]:
        reasons: List[str] = []

        is_trending = self._check_structural_trend(data)
        is_sideways_ok = self._check_sideways_operable(data)

        # ==========================================================
        # PATCH H&A — STRUCTURAL FLEX v1
        # ==========================================================

        fail_count = 0

        if not is_trending and not is_sideways_ok:
            reasons.append("STRUCTURE_INVALID")
            fail_count += 1

        if not self._check_structural_spread(data):
            reasons.append("SPREAD_INSUFFICIENT")
            fail_count += 1

        if not self._check_structural_rsi(data):
            reasons.append("RSI_BELOW_MIN")
            fail_count += 1

        if not self._check_structural_volume(data):
            reasons.append("VOLUME_BELOW_MIN")
            fail_count += 1

        # 🔥 NOVA REGRA:
        # tolera até 1 falha estrutural leve
        if fail_count <= 1:
            reasons = []

            if reasons:
                spread = 0.0
                if data.price > 0:
                    spread = abs(data.ema_fast - data.ema_slow) / data.price

                print(
                    f"[STRUCTURAL DEBUG] {data.symbol} | "
                    f"trend={data.trend} | "
                    f"momentum={data.momentum} | "
                    f"market_state={data.market_state} | "
                    f"volume_state={data.volume_state} | "
                    f"price={data.price:.8f} | "
                    f"ema_fast={data.ema_fast:.8f} | "
                    f"ema_slow={data.ema_slow:.8f} | "
                    f"spread={spread:.8f} | "
                    f"rsi={data.rsi:.2f} | "
                    f"volume_ratio={data.volume_ratio:.4f} | "
                    f"reasons={','.join(reasons)}"
                )

        return reasons

    # -------------------------------------------------------------------------
    # SCORING
    # -------------------------------------------------------------------------

    def _score_trend(self, data: SelectionInput) -> float:
        trend_value = str(data.trend).strip().upper()

        if trend_value == "UPTREND":
            return 0.35

        return 0.0

    def _score_momentum(self, data: SelectionInput) -> float:
        momentum_value = str(data.momentum).strip().upper()

        if momentum_value == "BULLISH":
            return 0.25
        elif momentum_value == "NEUTRAL":
            return 0.10

        return 0.0

    def _score_rsi(self, data: SelectionInput) -> float:
        rsi = float(data.rsi)

        if 45 <= rsi <= 60:
            return 0.20
        elif 40 <= rsi < 45 or 60 < rsi <= 65:
            return 0.10
        elif 65 < rsi <= 72:
            return 0.05

        return 0.0

    def _score_volume(self, data: SelectionInput) -> float:
        volume_ratio = float(data.volume_ratio)

        # =========================================
        # Volume forte
        # =========================================
        if 1.5 <= volume_ratio < 3.0:
            return 0.15

        elif 3.0 <= volume_ratio < 4.0:
            return 0.10

        # =========================================
        # Volume aceitável / saudável
        # =========================================
        elif 1.2 <= volume_ratio < 1.5:
            return 0.10

        # =========================================
        # Volume estrutural mínimo
        # =========================================
        elif 1.0 <= volume_ratio < 1.2:
            return 0.05

        return 0.0

    def _score_market_state(self, data: SelectionInput) -> float:
        state = str(data.market_state).strip().upper()
        market_score = float(data.market_score or 0.0)

        base_score = 0.0

        # =========================================
        # UPTREND = melhor cenário
        # =========================================
        if state in ("BULLISH_STRONG", "UPTREND"):
            base_score = 0.10

        # =========================================
        # SIDEWAYS OPERÁVEL = neutro positivo
        # =========================================
        elif state == "SIDEWAYS" and self._check_sideways_operable(data):
            base_score = 0.05

        # =========================================
        # Outros estados
        # =========================================
        elif state == "BULLISH_WEAK":
            base_score = 0.03

        elif state in ("BEARISH_WEAK", "BEARISH_STRONG"):
            base_score = 0.0

        # =========================================
        # Bônus leve por market_score
        # Mantém o motor conservador e evita campo órfão
        # =========================================
        bonus = 0.0

        if market_score >= 0.80:
            bonus = 0.03
        elif market_score >= 0.65:
            bonus = 0.02
        elif market_score >= 0.50:
            bonus = 0.01

        final_market_score = base_score + bonus

        return min(final_market_score, 0.12)

    def _compute_partial_scores(self, data: SelectionInput) -> PartialScores:
        return PartialScores(
            trend=self._score_trend(data),
            momentum=self._score_momentum(data),
            rsi=self._score_rsi(data),
            volume=self._score_volume(data),
            market=self._score_market_state(data),
        )

    def _compose_final_score(self, partials: PartialScores) -> float:
        score = (
            float(partials.trend)
            + float(partials.momentum)
            + float(partials.rsi)
            + float(partials.volume)
            + float(partials.market)
        )

        score = max(min(score, 1.0), 0.0)
        return round(score, 4)

    def _check_min_score(
        self,
        final_score: float,
        data: SelectionInput,
        market_context: dict,
    ) -> bool:
        real_score = float(final_score)

        dynamic_context = {
            "mqii_state": str(market_context.get("mqii_state", "CAUTIOUS")).upper(),
            "liquidity_score": float(market_context.get("liquidity_score", 0.0) or 0.0),
            "approved_count": int(market_context.get("approved_count", 0) or 0),
            "uptrend_count": int(market_context.get("uptrend_count", 0) or 0),
            "avg_volume_ratio": float(
                market_context.get("avg_volume_ratio", 0.0) or 0.0
            ),
        }

        result = self.dynamic_policy.evaluate(
            data=data,
            final_score=real_score,
            market_context=dynamic_context,
        )

        print(
            f"[MIN_SCORE DEBUG] "
            f"score={real_score:.4f} | "
            f"mode={result.mode.value} | "
            f"min={result.min_score_required:.4f} | "
            f"approved={result.approved} | "
            f"reason={result.reason} | "
            f"trend={str(data.trend).strip().upper()} | "
            f"momentum={str(data.momentum).strip().upper()} | "
            f"state={str(data.market_state).strip().upper()} | "
            f"vol={float(data.volume_ratio):.3f}"
        )

        self._last_min_score_result = result
        return result.approved

    # -------------------------------------------------------------------------
    # DECISION / LOG
    # -------------------------------------------------------------------------

    def _build_decision(
        self,
        data: SelectionInput,
        approved: bool,
        final_score: float,
        partial_scores: PartialScores,
        rejection_reasons: List[str],
        approval_reasons: List[str],
        is_trending: bool,
        is_sideways_operable: bool,
        summary: str,
    ) -> SelectionDecision:
        return SelectionDecision(
            symbol=data.symbol,
            approved=bool(approved),
            final_score=float(final_score),
            partial_scores=partial_scores,
            rejection_reasons=list(rejection_reasons),
            approval_reasons=list(approval_reasons),
            is_trending=bool(is_trending),
            is_sideways_operable=bool(is_sideways_operable),
            summary=str(summary),
        )

    def _log_decision(self, decision: SelectionDecision) -> None:
        ps = decision.partial_scores

        print(
            f"[SELECTION SCORE] {decision.symbol} | "
            f"trend={ps.trend:.2f} momentum={ps.momentum:.2f} "
            f"rsi={ps.rsi:.2f} volume={ps.volume:.2f} "
            f"market={ps.market:.2f} final={decision.final_score:.4f}"
        )

        if decision.approved:
            print(
                f"[SELECTION APPROVED] {decision.symbol} | score={decision.final_score:.4f}"
            )
        else:
            reasons = ",".join(decision.rejection_reasons) or "UNKNOWN"
            print(f"[SELECTION REJECTED] {decision.symbol} | reasons={reasons}")

    def _log_selection_semantic(
        self,
        data: SelectionInput,
        decision: SelectionDecision,
        min_required=None,
        market_context=None,
        reason_detail: str = "UNKNOWN",
    ) -> None:
        market_context = market_context or {}

        score = float(decision.final_score)
        min_value = None
        delta_to_min = None

        if min_required is not None:
            min_value = float(min_required)
            delta_to_min = min_value - score

        trend = str(data.trend).strip().upper()
        momentum = str(data.momentum).strip().upper()
        volume_state = str(data.volume_state).strip().upper()
        mqii_state = str(market_context.get("mqii_state", "UNKNOWN")).strip().upper()
        rsi = float(data.rsi or 0.0)
        volume_ratio = float(data.volume_ratio or 0.0)

        structural_reasons = {
            "INVALID_INPUT",
            "SYMBOL_BLOCKED",
            "RSI_EXTREMO",
            "VOLUME_EXTREMO",
            "STRUCTURE_INVALID",
            "SPREAD_INSUFFICIENT",
            "RSI_BELOW_MIN",
            "VOLUME_BELOW_MIN",
        }

        rejection_reasons = {
            str(reason).upper() for reason in decision.rejection_reasons
        }
        premium_context = (
            score >= 0.80
            and trend in ("UPTREND", "STRONG_UPTREND")
            and (volume_state in ("HIGH", "MODERATE") or volume_ratio >= 1.20)
            and 42.0 <= rsi <= 68.0
        )

        contextual_reason = (
            "CONTEXT" in str(reason_detail).upper()
            or "NEUTRAL" in str(reason_detail).upper()
            or "SIDEWAYS" in str(reason_detail).upper()
            or mqii_state in ("CAUTIOUS", "NO_TRADE", "DEFENSIVE")
        )

        if rejection_reasons.intersection(structural_reasons):
            classification = "STRUCTURAL_REJECT"
        elif premium_context:
            classification = "PREMIUM_SETUP"
        elif decision.approved:
            classification = "GOOD_SETUP"
        elif delta_to_min is not None and 0.0 <= delta_to_min <= 0.05:
            classification = "SCORE_NEAR_PASS"
        elif contextual_reason:
            classification = "CONTEXTUAL_REJECT"
        else:
            classification = "WEAK_SETUP"

        min_text = "None" if min_value is None else f"{min_value:.4f}"
        delta_text = "None" if delta_to_min is None else f"{delta_to_min:.4f}"

        print(
            f"[SELECTION SEMANTIC] "
            f"symbol={decision.symbol} | "
            f"classification={classification} | "
            f"score={score:.4f} | "
            f"min_required={min_text} | "
            f"delta_to_min={delta_text} | "
            f"approved={decision.approved} | "
            f"trend={trend} | "
            f"momentum={momentum} | "
            f"volume={volume_state} | "
            f"rsi={rsi:.2f} | "
            f"mqii_state={mqii_state} | "
            f"reason_detail={reason_detail}"
        )

    def _record_lc1e_event(
        self,
        token,
        reason: str,
        summary: str = "",
        event_type: str = "NON_EXECUTION",
        market_context: dict | None = None,
    ) -> None:
        try:
            analysis = token.get("analysis", {}) or {}
            snapshot = token.get("snapshot")
            symbol = str(token.get("symbol") or token.get("pair") or "").strip().upper()

            event = self.lc1e.build_event(
                symbol=symbol,
                reason=reason,
                analysis=analysis,
                snapshot=snapshot,
                market_context=market_context or {},
                event_type=event_type,
                source="selection_policy_engine",
                summary=summary,
            )
            self.lc1e.record_event(event)
        except Exception as e:
            print(
                f"[LC1E ERROR] falha ao registrar evento | reason={reason} | erro={e}"
            )
