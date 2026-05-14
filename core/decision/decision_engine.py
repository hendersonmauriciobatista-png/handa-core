# =============================================================================
# core/decision/decision_engine.py
# H&A — DECISION ENGINE
# BUY ONLY / MCE COMPAT / DYNAMIC POLICY FULL INTEGRATION
# + SYSTEM CONTEXT PROVIDER ENABLED
# =============================================================================

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List

from core.dynamic_policy.dynamic_policy_core import DynamicPolicyCore
from core.dynamic_policy.lc1_feedback_adapter import LC1FeedbackAdapter
from core.dynamic_policy.policy_models import MarketContext, SystemContext
from core.decision.trade_qualifier import TradeQualifier
from core.alo_decision import AloDecisionLayer, AloDecisionMode
from core.alo.dynamic_core_adapter import AloDynamicCoreAdapter
from core.alo.dynamic_core_engine import AloDynamicCoreEngine

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================


class SignalType(Enum):
    BUY = "BUY"
    HOLD = "HOLD"


class SellReason(Enum):
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    TRAILING_STOP = "TRAILING_STOP"
    MOMENTUM_REVERSAL = "MOMENTUM_REVERSAL"


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class BuySignal:
    pair: str
    entry_price: float
    allocated_usdc: float
    stop_loss: float
    take_profit: float
    confidence: float
    reasons: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MarketSnapshot:
    pair: str
    price: float
    rsi: float
    ema_fast: float
    ema_slow: float
    volume_ratio: float
    atr: float


# =============================================================================
# DECISION ENGINE
# =============================================================================


class DecisionEngine:

    def __init__(
        self,
        risk_manager,
        capital_allocator,
        lc1_adapter=None,
        system_context_provider=None,
    ):
        self.risk = risk_manager
        self.allocator = capital_allocator
        self.trade_qualifier = TradeQualifier()

        self.dynamic_policy = DynamicPolicyCore()
        self.lc1_adapter = (
            lc1_adapter if lc1_adapter is not None else LC1FeedbackAdapter()
        )
        self.system_context_provider = system_context_provider
        self.position_manager = None
        self.alo = None
        self.alo_decision = AloDecisionLayer(mode=AloDecisionMode.OBSERVER)

        self.dynamic_core_adapter = AloDynamicCoreAdapter()
        self.dynamic_core_engine = AloDynamicCoreEngine()

        # ==========================================================
        # 🔥 H&A MEMORY (INJETADO - NÃO REMOVER)
        # ==========================================================
        self.penalty_map = {}
        self.last_traded_symbol = None
        self.last_trade_time = 0
        self.last_trade_was_loss = False
        self.last_trade_duration = 9999
        self.last_trade_reason = ""

        logger.info("[DecisionEngine] BUY ONLY + Dynamic Policy FULL inicializado")

    # -------------------------------------------------------------------------
    # EXTERNAL PROVIDER
    # -------------------------------------------------------------------------

    def set_system_context_provider(self, provider):
        self.system_context_provider = provider
        logger.info("[DecisionEngine] System context provider conectado")

    def set_position_manager(self, position_manager):
        self.position_manager = position_manager
        logger.info("[DecisionEngine] PositionManager conectado")

    def set_alo(self, alo):
        self.alo = alo
        logger.info("[DecisionEngine] ALO conectado")

    # -------------------------------------------------------------------------
    # BUY
    # -------------------------------------------------------------------------

    def evaluate_buy(self, snapshot: MarketSnapshot) -> Optional[BuySignal]:

        if snapshot is None:
            logger.warning("[Engine] Snapshot inválido")
            return None

        pair = str(snapshot.pair).strip().upper()

        # ======================================================
        # 🔥 GLOBAL ENTRY COOLDOWN (ANTI-OVERTRADING)
        # ======================================================
        cooldown_global_seconds = 90  # 1.5 minuto (ajustável)

        last_time = getattr(self, "last_trade_time", 0)
        now = datetime.utcnow().timestamp()

        if now - last_time < cooldown_global_seconds:
            logger.info(
                f"[GLOBAL COOLDOWN] {pair} bloqueado | "
                f"aguardando {(cooldown_global_seconds - (now - last_time)):.1f}s"
            )
            return None

        if not pair:
            logger.warning("[Engine] Pair inválido")
            return None

        # 0. BLOQUEIO SE JÁ EXISTE POSIÇÃO ATIVA NO PAR
        if self.position_manager is not None:
            try:
                if self.position_manager.has_position(symbol=pair):
                    logger.info(f"[Engine] BLOQUEADO POR POSIÇÃO JÁ ATIVA: {pair}")
                    return None
            except Exception as e:
                logger.warning(f"[Engine] erro ao checar posição ativa de {pair}: {e}")

        # ==========================================================
        # 🔥 H&A PROTECTION LAYER (NÃO REMOVE NADA EXISTENTE)
        # ==========================================================

        # 1. BLOQUEIO DE REENTRADA
        if self.last_traded_symbol == pair:

            # ======================================================
            # 🔥 DRC — COOLDOWN TEMPORAL
            # ======================================================
            cooldown_seconds = 300  # 5 minutos

            last_time = getattr(self, "last_trade_time", 0)
            now = datetime.utcnow().timestamp()

            if now - last_time < cooldown_seconds:
                logger.info(f"[DRC] BLOQUEADO POR COOLDOWN: {pair}")
                return None

            # ======================================================
            # 🔥 DRC V2 — REENTRADA PÓS-LUCRO CONTROLADA
            # ======================================================
            last_was_loss = getattr(self, "last_trade_was_loss", False)

            if last_was_loss is False:
                post_profit_reentry_allowed = (
                    float(snapshot.ema_fast) > float(snapshot.ema_slow)
                    and float(snapshot.volume_ratio) >= 2.0
                    and 50 <= float(snapshot.rsi) <= 64
                )

                if not post_profit_reentry_allowed:
                    logger.info(
                        f"[DRC V2] BLOQUEADO PÓS-LUCRO: {pair} | "
                        f"vol={snapshot.volume_ratio:.2f} | rsi={snapshot.rsi:.2f}"
                    )
                    return None

                logger.info(
                    f"[DRC V2] REENTRADA PÓS-LUCRO PERMITIDA: {pair} | "
                    f"vol={snapshot.volume_ratio:.2f} | rsi={snapshot.rsi:.2f}"
                )

            recent_loss = getattr(self, "last_trade_was_loss", False)

            # ======================================================
            # 🔥 DRC V2 — BLOQUEIO POR LOSS RÁPIDO / TRADE CURTO
            # ======================================================
            last_duration = getattr(self, "last_trade_duration", 9999)

            fast_loss_block = recent_loss and last_duration <= 30  # segundos

            if fast_loss_block:
                logger.info(
                    f"[DRC V2] BLOQUEADO POR LOSS RÁPIDO: {pair} | "
                    f"duration={last_duration}s"
                )
                return None

            # ======================================================
            # 🔥 DRC V3 — REVALIDAÇÃO CONTEXTUAL PÓS-LOSS / STAGNATION
            # ======================================================
            revalidation_required = recent_loss and 30 < last_duration <= 360

            if revalidation_required:
                mqii_state = ""
                avg_market_volume = 1.0

                try:
                    mqii = getattr(self, "mqii_quality", None)
                    if isinstance(mqii, dict):
                        mqii_state = str(mqii.get("state", "") or "").strip().upper()
                        avg_market_volume = float(
                            mqii.get("avg_volume_ratio", 1.0) or 1.0
                        )
                except Exception:
                    mqii_state = ""
                    avg_market_volume = 1.0

                if mqii_state == "NO_TRADE":
                    logger.info(
                        f"[DRC V3] BLOQUEADO {pair} | motivo=MQII_NO_TRADE | "
                        f"last_duration={last_duration}s"
                    )
                    return None

                if mqii_state == "CAUTIOUS":
                    volume_factor = 1.35
                    max_rsi_reentry = 68.0
                elif mqii_state in ("TRADE_OK", "AGGRESSIVE_OK"):
                    volume_factor = 1.20
                    max_rsi_reentry = 72.0
                else:
                    volume_factor = 1.30
                    max_rsi_reentry = 70.0

                dynamic_min_volume = max(
                    1.20, min(2.80, avg_market_volume * volume_factor)
                )

                price = float(snapshot.price or 0.0)
                ema_fast = float(snapshot.ema_fast or 0.0)
                ema_slow = float(snapshot.ema_slow or 0.0)
                rsi = float(snapshot.rsi or 0.0)
                volume_ratio = float(snapshot.volume_ratio or 0.0)

                ema_spread = abs(ema_fast - ema_slow) / price if price > 0 else 0.0
                dynamic_min_spread = 0.00035 if mqii_state == "CAUTIOUS" else 0.00025

                drc_revalidation_ok = (
                    ema_fast > ema_slow
                    and ema_spread >= dynamic_min_spread
                    and volume_ratio >= dynamic_min_volume
                    and 50 <= rsi <= max_rsi_reentry
                )

                if not drc_revalidation_ok:
                    logger.info(
                        f"[DRC V3] BLOQUEADO REVALIDAÇÃO {pair} | "
                        f"duration={last_duration}s | mqii={mqii_state} | "
                        f"vol={volume_ratio:.2f} min_vol={dynamic_min_volume:.2f} | "
                        f"rsi={rsi:.2f} max_rsi={max_rsi_reentry:.2f} | "
                        f"spread={ema_spread:.6f} min_spread={dynamic_min_spread:.6f}"
                    )
                    return None

                logger.info(
                    f"[DRC V3] REVALIDAÇÃO APROVADA {pair} | "
                    f"duration={last_duration}s | mqii={mqii_state} | "
                    f"vol={volume_ratio:.2f} min_vol={dynamic_min_volume:.2f} | "
                    f"rsi={rsi:.2f} | spread={ema_spread:.6f}"
                )

            reentry_allowed = (
                float(snapshot.ema_fast) > float(snapshot.ema_slow)
                and float(snapshot.volume_ratio) >= 1.2
                and 45 <= float(snapshot.rsi) <= 68
            )

            # 🔥 BLOQUEIO INTELIGENTE PÓS-LOSS
            if recent_loss and not reentry_allowed:
                logger.info(
                    f"[Engine] BLOQUEADO POR LOSS RECENTE (setup fraco): {pair}"
                )
                return None

            # comportamento original
            if not reentry_allowed:
                logger.info(f"[Engine] BLOQUEADO POR REENTRADA IMEDIATA: {pair}")
                return None
            else:
                logger.info(
                    f"[Engine] REENTRADA CONTROLADA PERMITIDA: {pair} | "
                    f"volume={snapshot.volume_ratio:.2f} | rsi={snapshot.rsi:.2f}"
                )

        # 2. BLOQUEIO POR PENALTY
        penalty = self.penalty_map.get(pair, 0)
        if penalty >= 2:
            penalty_override_allowed = (
                float(snapshot.ema_fast) > float(snapshot.ema_slow)
                and float(snapshot.volume_ratio) >= 1.25
                and 45 <= float(snapshot.rsi) <= 66
            )

            if not penalty_override_allowed:
                logger.info(
                    f"[Engine] BLOQUEADO POR PENALTY: {pair} | penalty={penalty}"
                )
                return None
            else:
                logger.info(
                    f"[Engine] PENALTY OVERRIDE CONTROLADO: {pair} | "
                    f"penalty={penalty} | volume={snapshot.volume_ratio:.2f} | "
                    f"rsi={snapshot.rsi:.2f}"
                )

        # 3. BLOQUEIO DE LATERALIZAÇÃO EXTREMA (SPREAD BAIXO)
        price = float(snapshot.price or 0.0)
        ema_fast = float(snapshot.ema_fast or 0.0)
        ema_slow = float(snapshot.ema_slow or 0.0)

        market_ctx = self._build_market_context(snapshot)
        system_ctx = self._build_system_context()
        lc1_feedback = self.lc1_adapter.build_feedback(pair)

        policy = self.dynamic_policy.build_policy(
            market=market_ctx,
            system=system_ctx,
            lc1=lc1_feedback,
        )

        debug_info = self.dynamic_policy.build_debug_info(market_ctx)

        approved, reasons, confidence = self._check_momentum_buy(snapshot, policy)

        # ==========================================================
        # 🔥 ALO CONTEXTUAL BIAS (FASE 3)
        # ==========================================================
        alo_dynamic_min_confidence = 0.0

        if self.alo is not None:
            try:
                profile = self.alo.get_symbol_profile(pair)

                if profile is not None:

                    alo_status = str(getattr(profile, "status", "")).strip().upper()

                    alo_conf = float(getattr(profile, "confidence_score", 0.0))

                    total_events = int(getattr(profile, "total_events", 0) or 0)

                    if total_events >= 10:

                        if alo_status in ("BLOCKED", "REJECTED"):
                            alo_dynamic_min_confidence = 0.82

                        elif alo_status in ("LEARNING", "MEDIUM_CONFIDENCE"):
                            alo_dynamic_min_confidence = 0.74

                        elif alo_status == "APPROVED":
                            if alo_conf >= 0.85:
                                alo_dynamic_min_confidence = 0.62
                            elif alo_conf >= 0.70:
                                alo_dynamic_min_confidence = 0.68
                            else:
                                alo_dynamic_min_confidence = 0.72

                        if approved and confidence < alo_dynamic_min_confidence:

                            logger.info(
                                f"[ALO CONTEXTUAL BIAS] BLOQUEADO {pair} | "
                                f"conf={confidence:.3f} | "
                                f"min_required={alo_dynamic_min_confidence:.3f} | "
                                f"alo_status={alo_status} | "
                                f"alo_conf={alo_conf:.2f}"
                            )

                            return False

                        if approved:

                            logger.info(
                                f"[ALO CONTEXTUAL BIAS] APROVADO {pair} | "
                                f"conf={confidence:.3f} | "
                                f"min_required={alo_dynamic_min_confidence:.3f} | "
                                f"alo_status={alo_status} | "
                                f"alo_conf={alo_conf:.2f}"
                            )

            except Exception as e:
                logger.warning(f"[ALO CONTEXTUAL BIAS ERROR] {e}")

        # 🔥 EXECUTION STABILITY GATE + TCE PATCH
        # Trend Continuation Entry — RSI alto contextual
        # ======================================================
        market_state_raw = (
            str(getattr(snapshot, "market_state", "") or "").strip().upper()
        )
        trend_raw = str(getattr(snapshot, "trend", "") or "").strip().upper()
        momentum_raw = str(getattr(snapshot, "momentum", "") or "").strip().upper()
        mqii_state = ""

        try:
            mqii = getattr(self, "mqii_quality", None)
            if isinstance(mqii, dict):
                mqii_state = str(mqii.get("state", "") or "").strip().upper()
        except Exception:
            mqii_state = ""

        normal_stability_ok = (
            float(snapshot.volume_ratio) >= 1.15 and 50 <= float(snapshot.rsi) <= 62
        )

        tce_stability_ok = (
            trend_raw.endswith("UPTREND")
            and momentum_raw.endswith("BULLISH")
            and market_state_raw == "BULLISH_STRONG"
            and float(snapshot.volume_ratio) >= 2.0
            and 62 < float(snapshot.rsi) <= 75
            and mqii_state != "NO_TRADE"
        )

        stability_ok = normal_stability_ok or tce_stability_ok

        if approved and not stability_ok:
            logger.info(
                f"[STABILITY GATE] BLOQUEADO {pair} | "
                f"vol={snapshot.volume_ratio:.2f} | rsi={snapshot.rsi:.2f}"
            )
            return None

        if approved and tce_stability_ok:
            logger.info(
                f"[TCE PATCH] LIBERADO {pair} | "
                f"trend={trend_raw} | momentum={momentum_raw} | "
                f"state={market_state_raw} | vol={snapshot.volume_ratio:.2f} | "
                f"rsi={snapshot.rsi:.2f} | mqii={mqii_state}"
            )

        if not approved:

            # ==========================================================
            # 🔥 CAUTION_PASS — LIBERAÇÃO CONTROLADA
            # ==========================================================
            market_state_raw = str(getattr(snapshot, "market_state", "")).upper()
            trend_raw = str(getattr(snapshot, "trend", "")).upper()
            momentum_raw = str(getattr(snapshot, "momentum", "")).upper()
            volume_ratio = float(snapshot.volume_ratio or 0.0)
            rsi = float(snapshot.rsi or 0.0)

            caution_pass = (
                confidence >= 0.75
                and trend_raw.endswith("UPTREND")
                and volume_ratio >= 1.2
                and 48 <= rsi <= 65
                and market_state_raw in ("SIDEWAYS", "CAUTIOUS", "MODERATE", "TRADE_OK")
            )

            if caution_pass:
                logger.info(
                    f"[CAUTION PASS] LIBERADO {pair} | "
                    f"conf={confidence:.3f} | vol={volume_ratio:.2f} | rsi={rsi:.2f}"
                )

                approved = True
                reasons.append("CAUTION_PASS_LIBERATION")
        else:

            # ==========================================================
            # 🔥 PRÉ-MOVIMENTO (NOVO)
            # ==========================================================
            pre_ok, pre_reasons, pre_confidence = self._check_pre_movement_entry(
                snapshot, policy
            )

            if pre_ok:
                allocation = self.allocator.request_allocation(pair)

                if not allocation.approved:
                    logger.warning(
                        f"[Engine] Capital negado (pre-movement) {pair}: {allocation.reason}"
                    )
                    return None

                # entrada menor para pré-movimento
                reduced_capital = float(allocation.allocated_usdc) * 0.60

                risk_eval = self.risk.evaluate_entry(
                    pair=pair,
                    entry_price=float(snapshot.price),
                    capital_to_use=float(reduced_capital),
                    expected_profit_pct=max(
                        float(policy.expected_profit_pct) * 0.85, 0.0025
                    ),
                    atr=float(snapshot.atr),
                    min_rr=max(float(policy.min_rr) * 0.90, 1.10),
                    stop_loss_pct=max(float(policy.stop_loss_pct), 0.0028),
                )

                if not risk_eval.approved:
                    logger.warning(
                        f"[Engine] Risk negou (pre-movement) {pair}: {risk_eval.reason}"
                    )
                    return None

                signal = BuySignal(
                    pair=pair,
                    entry_price=float(snapshot.price),
                    allocated_usdc=float(reduced_capital),
                    stop_loss=float(risk_eval.stop_loss_price),
                    take_profit=float(risk_eval.take_profit_price),
                    confidence=float(pre_confidence),
                    reasons=list(pre_reasons) + ["PRE_MOVEMENT_MODE"],
                )

                logger.info(
                    f"[Engine] BUY PRÉ-MOVIMENTO {pair} | "
                    f"entry={signal.entry_price:.8f} | "
                    f"capital={signal.allocated_usdc:.4f} | "
                    f"conf={signal.confidence:.3f}"
                )

                return signal

            # ==========================================================
            # 🔥 FALLBACK OPORTUNISTA (EXISTENTE)
            # ==========================================================
            qualifier_result = self.trade_qualifier.qualify(snapshot)

            opportunity_context_ok = (
                float(snapshot.ema_fast) > float(snapshot.ema_slow)
                and float(snapshot.volume_ratio) >= 1.2
                and 50 <= float(snapshot.rsi) <= 65
            )

            if (
                qualifier_result.approved
                and qualifier_result.mode == "OPPORTUNITY"
                and opportunity_context_ok
            ):

                allocation = self.allocator.request_allocation(pair)

                if not allocation.approved:
                    logger.warning(
                        f"[Engine] Capital negado (opportunity) {pair}: {allocation.reason}"
                    )
                    return None

                risk_eval = self.risk.evaluate_entry(
                    pair=pair,
                    entry_price=float(snapshot.price),
                    capital_to_use=float(allocation.allocated_usdc),
                    expected_profit_pct=max(float(policy.expected_profit_pct), 0.003),
                    atr=float(snapshot.atr),
                    min_rr=max(float(policy.min_rr), 1.15),
                    stop_loss_pct=float(policy.stop_loss_pct),
                )

                if not risk_eval.approved:
                    logger.warning(
                        f"[Engine] Risk negou (opportunity) {pair}: {risk_eval.reason}"
                    )
                    return None

                signal = BuySignal(
                    pair=pair,
                    entry_price=float(snapshot.price),
                    allocated_usdc=float(allocation.allocated_usdc),
                    stop_loss=float(risk_eval.stop_loss_price),
                    take_profit=float(risk_eval.take_profit_price),
                    confidence=float(qualifier_result.confidence),
                    reasons=list(qualifier_result.reasons) + ["OPPORTUNITY_MODE"],
                )

                logger.info(
                    f"[Engine] BUY OPORTUNIDADE {pair} | "
                    f"entry={signal.entry_price:.8f} | "
                    f"capital={signal.allocated_usdc:.4f} | "
                    f"conf={signal.confidence:.3f}"
                )

                return signal

            # ==========================================================
            # ❌ BLOQUEIO FINAL
            # ==========================================================
            logger.info(
                f"[Engine] BUY negado {pair} | "
                f"regime={debug_info.regime} | motivos={reasons}"
            )

            if self.alo is not None:
                try:
                    self.alo.ingest_event(
                        {
                            "symbol": pair,
                            "event_type": "NON_EXECUTION",
                            "reason": "BUY_REJECTED",
                            "analysis": {"selection_score": float(confidence)},
                            "market_context": {
                                "stage": "DECISION_ENGINE",
                                "mqii_state": (
                                    getattr(self, "mqii_quality", {}).get("state", "")
                                    if isinstance(
                                        getattr(self, "mqii_quality", None), dict
                                    )
                                    else ""
                                ),
                                "liquidity_score": (
                                    getattr(self, "mqii_quality", {}).get(
                                        "liquidity_score", 0.0
                                    )
                                    if isinstance(
                                        getattr(self, "mqii_quality", None), dict
                                    )
                                    else 0.0
                                ),
                            },
                            "snapshot": {
                                "volume_ratio": float(snapshot.volume_ratio or 0.0),
                                "rsi_14": float(snapshot.rsi or 0.0),
                            },
                        }
                    )
                except Exception as e:
                    logger.warning(f"[ALO INGEST ERROR - NON_EXECUTION] {e}")

            return None

        allocation = self.allocator.request_allocation(pair)

        if not allocation.approved:
            logger.warning(f"[Engine] Capital negado {pair}: {allocation.reason}")
            return None

        dynamic_capital = float(allocation.allocated_usdc) * float(
            policy.capital_multiplier
        )

        risk_eval = self.risk.evaluate_entry(
            pair=pair,
            entry_price=float(snapshot.price),
            capital_to_use=float(dynamic_capital),
            expected_profit_pct=float(policy.expected_profit_pct),
            atr=float(snapshot.atr),
            min_rr=float(policy.min_rr),
            stop_loss_pct=float(policy.stop_loss_pct),
        )

        if not risk_eval.approved:
            logger.warning(
                f"[Engine] Risk negou {pair}: {risk_eval.reason} | "
                f"regime={debug_info.regime} | "
                f"exp_profit={policy.expected_profit_pct:.4%} | "
                f"policy_min_rr={policy.min_rr:.2f} | "
                f"policy_stop={policy.stop_loss_pct:.4%}"
            )
            return None

        signal_reasons = list(reasons)
        signal_reasons.append(f"Regime: {debug_info.regime}")
        signal_reasons.append(
            f"Expected profit dinâmico: {policy.expected_profit_pct:.4%}"
        )
        signal_reasons.append(f"Capital multiplier: {policy.capital_multiplier:.2f}")
        signal_reasons.append(f"Min RR dinâmico: {policy.min_rr:.2f}")
        signal_reasons.append(f"Stop dinâmico: {policy.stop_loss_pct:.4%}")
        signal_reasons.append(
            f"Slots ativos: {system_ctx.active_slots}/{system_ctx.max_slots}"
        )
        signal_reasons.append(f"Loss streak sistêmico: {system_ctx.loss_streak}")
        signal_reasons.append(f"Win rate recente: {system_ctx.win_rate_recent:.2%}")
        signal_reasons.append(f"Drawdown atual: {system_ctx.drawdown_pct:.2%}")

        # ==========================================================
        # 🔥 NEW ALO DECISION LAYER (OBSERVER ONLY)
        # ==========================================================
        if self.alo_decision is not None:
            try:
                alo_decision_input = self._build_alo_decision_input(
                    snapshot=snapshot,
                    system_ctx=system_ctx,
                    dynamic_capital=float(dynamic_capital),
                )

                alo_decision_result = self.alo_decision.evaluate(alo_decision_input)

                signal_reasons.append(
                    f"ALO Decision mode: {alo_decision_result.mode.value}"
                )
                signal_reasons.append(
                    f"ALO Decision observer_only: {alo_decision_result.observer_only}"
                )

                if alo_decision_result.labels:
                    signal_reasons.append(
                        "ALO Decision labels: " + ", ".join(alo_decision_result.labels)
                    )

                if alo_decision_result.reasons:
                    signal_reasons.append(
                        "ALO Decision reasons: "
                        + ", ".join(alo_decision_result.reasons)
                    )

                logger.info(
                    f"[ALO DECISION OBS] {pair} | "
                    f"mode={alo_decision_result.mode.value} | "
                    f"observer_only={alo_decision_result.observer_only} | "
                    f"block_suggested={alo_decision_result.block_suggested} | "
                    f"confidence_suggested={alo_decision_result.confidence_suggested:.3f} | "
                    f"capital_suggested={alo_decision_result.capital_suggested:.3f} | "
                    f"labels={alo_decision_result.labels} | "
                    f"reasons={alo_decision_result.reasons}"
                )

            except Exception as e:
                logger.warning(f"[ALO DECISION OBS ERROR] {e}")

        # ==========================================================
        # 🔥 ALO DYNAMIC CORE (OBSERVER ONLY)
        # ==========================================================
        if (
            self.dynamic_core_adapter is not None
            and self.dynamic_core_engine is not None
        ):
            try:
                dynamic_profile = None
                if self.alo is not None:
                    try:
                        dynamic_profile = self.alo.get_symbol_profile(pair)
                    except Exception as e:
                        logger.warning(f"[ALO DYNAMIC CORE PROFILE ERROR] {e}")

                dynamic_mqii = getattr(self, "mqii_quality", None)

                dynamic_input = self.dynamic_core_adapter.build_input(
                    snapshot=snapshot,
                    profile=dynamic_profile,
                    system_ctx=system_ctx,
                    mqii_data=dynamic_mqii,
                )

                dynamic_result = self.dynamic_core_engine.evaluate(dynamic_input)

                signal_reasons.append(
                    f"ALO Dynamic mode: {dynamic_result.dynamic_mode}"
                )
                signal_reasons.append(
                    f"ALO Dynamic confidence: {dynamic_result.confidence_score:.4f}"
                )

                if dynamic_result.override_permission:
                    signal_reasons.append("ALO Dynamic override permission: TRUE")

                if dynamic_result.block_reason:
                    signal_reasons.append(
                        f"ALO Dynamic block reason: {dynamic_result.block_reason}"
                    )

                if dynamic_result.reasons:
                    signal_reasons.append(
                        "ALO Dynamic reasons: " + ", ".join(dynamic_result.reasons)
                    )

                logger.info(
                    f"[ALO DYNAMIC CORE] {pair} | "
                    f"mode={dynamic_result.dynamic_mode} | "
                    f"score={dynamic_result.confidence_score:.4f} | "
                    f"label={dynamic_result.confidence_label} | "
                    f"risk_weight={dynamic_result.risk_weight:.2f} | "
                    f"override={dynamic_result.override_permission} | "
                    f"block_reason={dynamic_result.block_reason}"
                )

            except Exception as e:
                logger.warning(f"[ALO DYNAMIC CORE ERROR] {e}")

        # ==========================================================
        # 🔥 ALO GATE (FILTRO INTELIGENTE + EXCEÇÃO CONTROLADA)
        # ==========================================================
        if self.alo is not None:
            try:
                profile = self.alo.get_symbol_profile(pair)

                alo_confidence = 0.0
                alo_status = "NO_PROFILE"

                if profile is not None:
                    alo_confidence = float(getattr(profile, "confidence_score", 0.0))
                    alo_status = str(getattr(profile, "status", "")).strip().upper()

                    market_state_raw = (
                        str(getattr(snapshot, "market_state", "") or "").strip().upper()
                    )
                    trend_raw = (
                        str(getattr(snapshot, "trend", "") or "").strip().upper()
                    )
                    momentum_raw = (
                        str(getattr(snapshot, "momentum", "") or "").strip().upper()
                    )
                    volume_state_raw = (
                        str(getattr(snapshot, "volume_state", "") or "").strip().upper()
                    )

                    premium_setup = (
                        confidence >= 0.70
                        and trend_raw.endswith("UPTREND")
                        and momentum_raw.endswith("BULLISH")
                        and volume_state_raw in ("HIGH", "MODERATE")
                        and market_state_raw
                        in (
                            "BULLISH_STRONG",
                            "AGGRESSIVE_OK",
                            "TRADE_OK",
                            "BULLISH_WEAK",
                        )
                    )

                    mqii_state = ""
                    mqii_score = 0.0
                    market_ok = True

                    try:
                        mqii = getattr(self, "mqii_quality", None)
                        if isinstance(mqii, dict):
                            mqii_state = (
                                str(mqii.get("state", "") or "").strip().upper()
                            )
                            mqii_score = float(mqii.get("score", 0.0) or 0.0)

                            if mqii_state == "NO_TRADE":
                                market_ok = False
                            elif mqii_state == "CAUTIOUS" and mqii_score < 0.30:
                                market_ok = False
                    except Exception:
                        market_ok = False

                    allow_premium_override = (
                        alo_status in ("BLOCKED", "REJECTED")
                        and alo_confidence < 0.40
                        and premium_setup
                        and market_ok
                    )

                    # ======================================================
                    # 🔥 ALO — LIBERAÇÃO SEM CONTEXTO (CRÍTICO)
                    # ======================================================
                    total_events = int(getattr(profile, "total_events", 0) or 0)

                    if total_events < 5:
                        logger.info(
                            f"[ALO LIBERADO SEM CONTEXTO] {pair} | events={total_events}"
                        )
                    else:
                        if (
                            alo_status in ("BLOCKED", "REJECTED")
                            and alo_confidence < 0.40
                            and total_events >= 10
                        ):
                            if allow_premium_override:
                                logger.info(
                                    f"[ALO GATE] CAUTION_PASS {pair} | "
                                    f"motivo=SETUP_PREMIUM_OVERRIDE | "
                                    f"status={alo_status} | "
                                    f"conf={alo_confidence:.2f} | "
                                    f"base_conf={confidence:.3f} | "
                                    f"mqii_state={mqii_state} | "
                                    f"mqii_score={mqii_score:.3f}"
                                )

                                signal_reasons.append(
                                    "ALO premium override: veto rebaixado para cautela"
                                )
                            else:
                                logger.info(
                                    f"[ALO GATE] BLOQUEADO {pair} | "
                                    f"status={alo_status} | conf={alo_confidence:.2f}"
                                )
                                return None

                signal_reasons.append(
                    f"ALO status: {alo_status} | conf={alo_confidence:.2f}"
                )

            except Exception as e:
                logger.warning(f"[ALO GATE ERROR] {e}")

        # ==========================================================
        # 🔥 ALO CONFIDENCE ADJUSTMENT
        # ==========================================================
        final_confidence = float(confidence)

        if self.alo is not None:
            try:
                profile = self.alo.get_symbol_profile(pair)

                if profile is not None:
                    alo_confidence = float(getattr(profile, "confidence_score", 0.0))
                    alo_status = str(getattr(profile, "status", "")).strip().upper()

                    if alo_status == "APPROVED":
                        final_confidence *= 1.10
                    elif alo_status in ("MEDIUM_CONFIDENCE", "LEARNING"):
                        final_confidence *= 1.00
                    elif alo_status in ("BLOCKED", "REJECTED"):
                        final_confidence *= 0.90

                    final_confidence = max(0.0, min(1.0, final_confidence))

                    signal_reasons.append(
                        f"ALO adjusted confidence: {final_confidence:.3f}"
                    )

            except Exception as e:
                logger.warning(f"[ALO CONFIDENCE ERROR] {e}")

        # ==========================================================
        # 🔥 ALO CAPITAL ADJUSTMENT (SEMI-AUTÔNOMO SEGURO)
        # ==========================================================
        final_capital = float(dynamic_capital)

        if self.alo is not None:
            try:
                profile = self.alo.get_symbol_profile(pair)

                if profile is not None:
                    alo_conf = float(getattr(profile, "confidence_score", 0.5))
                    alo_status = str(getattr(profile, "status", "")).strip().upper()

                    multiplier = 1.0

                    if alo_status in ("BLOCKED", "REJECTED"):
                        multiplier = 0.80
                    elif alo_status in ("MEDIUM_CONFIDENCE", "LEARNING"):
                        multiplier = 1.00
                    elif alo_status == "APPROVED" and alo_conf >= 0.85:
                        multiplier = 1.20
                    elif alo_status == "APPROVED" and alo_conf >= 0.70:
                        multiplier = 1.10

                    final_capital *= multiplier

                    signal_reasons.append(
                        f"ALO capital x{multiplier:.2f} | conf={alo_conf:.2f}"
                    )

            except Exception as e:
                logger.warning(f"[ALO CAPITAL ERROR] {e}")

        # ==========================================================
        # 🔥 ALO OBSERVABILITY
        # ==========================================================
        alo_status_log = "NO_PROFILE"
        alo_conf_log = 0.0

        if self.alo is not None:
            try:
                profile = self.alo.get_symbol_profile(pair)

                if profile is not None:
                    alo_status_log = (
                        str(getattr(profile, "status", "UNKNOWN")).strip().upper()
                    )
                    alo_conf_log = float(getattr(profile, "confidence_score", 0.0))

            except Exception as e:
                logger.warning(f"[ALO OBS ERROR] {e}")

        logger.info(
            f"[ALO OBS] {pair} | "
            f"status={alo_status_log} | "
            f"alo_conf={alo_conf_log:.2f} | "
            f"final_conf={final_confidence:.3f} | "
            f"final_capital={final_capital:.4f}"
        )

        signal = BuySignal(
            pair=pair,
            entry_price=float(snapshot.price),
            allocated_usdc=float(final_capital),
            stop_loss=float(risk_eval.stop_loss_price),
            take_profit=float(risk_eval.take_profit_price),
            confidence=float(final_confidence),
            reasons=signal_reasons,
        )

        logger.info(
            f"[Engine] BUY aprovado {pair} | "
            f"entry={signal.entry_price:.8f} | "
            f"capital={signal.allocated_usdc:.4f} | "
            f"conf={signal.confidence:.3f} | "
            f"regime={debug_info.regime} | "
            f"exp_profit={policy.expected_profit_pct:.4%} | "
            f"min_rr={policy.min_rr:.2f} | "
            f"slots={system_ctx.active_slots}/{system_ctx.max_slots} | "
            f"loss_streak={system_ctx.loss_streak} | "
            f"win_rate={system_ctx.win_rate_recent:.2%} | "
            f"drawdown={system_ctx.drawdown_pct:.2%}"
        )

        return signal

    def _build_alo_decision_input(
        self,
        snapshot: MarketSnapshot,
        system_ctx,
        dynamic_capital: float,
    ):
        from core.alo_decision import AloDecisionInput

        pair = str(getattr(snapshot, "pair", "")).strip().upper()

        profile = None
        if self.alo is not None:
            try:
                profile = self.alo.get_symbol_profile(pair)
            except Exception as e:
                logger.warning(f"[ALO DECISION INPUT ERROR] {e}")

        profile_exists = profile is not None

        total_events = 0
        execution_count = 0
        non_execution_count = 0
        structural_block_count = 0
        quality_filter_count = 0
        low_score_count = 0
        loss_count = 0
        win_count = 0
        block_bias = 0.0
        confidence_score = 0.0

        if profile is not None:
            total_events = int(getattr(profile, "total_events", 0) or 0)
            execution_count = int(getattr(profile, "execution_count", 0) or 0)
            non_execution_count = int(getattr(profile, "non_execution_count", 0) or 0)
            structural_block_count = int(
                getattr(profile, "structural_block_count", 0) or 0
            )
            quality_filter_count = int(getattr(profile, "quality_filter_count", 0) or 0)
            low_score_count = int(getattr(profile, "low_score_count", 0) or 0)
            loss_count = int(getattr(profile, "loss_count", 0) or 0)
            win_count = int(getattr(profile, "win_count", 0) or 0)
            block_bias = float(getattr(profile, "block_bias", 0.0) or 0.0)
            confidence_score = float(getattr(profile, "confidence_score", 0.0) or 0.0)

        market_state = str(getattr(snapshot, "market_state", "")).strip().upper()
        momentum = str(getattr(snapshot, "momentum", "")).strip().upper()
        trend = str(getattr(snapshot, "trend", "")).strip().upper()
        volume_state = str(getattr(snapshot, "volume_state", "")).strip().upper()

        mqii_state = ""
        mqii_score = 0.0
        liquidity_score = 0.0
        liquidity_label = ""

        try:
            mqii = getattr(self, "mqii_quality", None)
            if isinstance(mqii, dict):
                mqii_state = str(mqii.get("state", "")).strip().upper()
                mqii_score = float(mqii.get("score", 0.0) or 0.0)
                liquidity_score = float(mqii.get("liquidity_score", 0.0) or 0.0)
                liquidity_label = str(mqii.get("liquidity_label", "")).strip().upper()
        except Exception as e:
            logger.warning(f"[ALO DECISION MQII INPUT ERROR] {e}")

        return AloDecisionInput(
            symbol=pair,
            trend=trend,
            momentum=momentum,
            market_state=market_state,
            volume_state=volume_state,
            rsi=float(getattr(snapshot, "rsi", 0.0) or 0.0),
            volume_ratio=float(getattr(snapshot, "volume_ratio", 0.0) or 0.0),
            price=float(getattr(snapshot, "price", 0.0) or 0.0),
            ema_fast=float(getattr(snapshot, "ema_fast", 0.0) or 0.0),
            ema_slow=float(getattr(snapshot, "ema_slow", 0.0) or 0.0),
            market_score=float(getattr(snapshot, "market_score", 0.0) or 0.0),
            mqii_state=mqii_state,
            mqii_score=mqii_score,
            liquidity_score=liquidity_score,
            liquidity_label=liquidity_label,
            profile_exists=profile_exists,
            total_events=total_events,
            execution_count=execution_count,
            non_execution_count=non_execution_count,
            structural_block_count=structural_block_count,
            quality_filter_count=quality_filter_count,
            low_score_count=low_score_count,
            loss_count=loss_count,
            win_count=win_count,
            block_bias=block_bias,
            confidence_score=confidence_score,
            slot_id=None,
            available_capital=float(getattr(system_ctx, "balance", 0.0) or 0.0),
            base_capital=float(dynamic_capital),
            raw_profile=(
                profile.__dict__
                if profile is not None and hasattr(profile, "__dict__")
                else {}
            ),
            raw_analysis={
                "trend": trend,
                "momentum": momentum,
                "market_state": market_state,
                "volume_state": volume_state,
            },
            raw_snapshot={
                "pair": pair,
                "price": float(getattr(snapshot, "price", 0.0) or 0.0),
                "rsi": float(getattr(snapshot, "rsi", 0.0) or 0.0),
                "ema_fast": float(getattr(snapshot, "ema_fast", 0.0) or 0.0),
                "ema_slow": float(getattr(snapshot, "ema_slow", 0.0) or 0.0),
                "volume_ratio": float(getattr(snapshot, "volume_ratio", 0.0) or 0.0),
                "atr": float(getattr(snapshot, "atr", 0.0) or 0.0),
            },
        )

    # -------------------------------------------------------------------------
    # CONTEXT BUILDERS
    # -------------------------------------------------------------------------

    def _build_market_context(self, snapshot: MarketSnapshot) -> MarketContext:
        return MarketContext(
            pair=str(snapshot.pair).strip().upper(),
            price=float(snapshot.price or 0.0),
            rsi=float(snapshot.rsi or 0.0),
            ema_fast=float(snapshot.ema_fast or 0.0),
            ema_slow=float(snapshot.ema_slow or 0.0),
            volume_ratio=float(snapshot.volume_ratio or 0.0),
            atr=float(snapshot.atr or 0.0),
        )

    def _build_system_context(self) -> SystemContext:
        balance = 0.0
        active_slots = 0
        drawdown_pct = 0.0
        loss_streak = 0
        win_rate_recent = 0.50

        try:
            if self.risk is not None and hasattr(self.risk, "get_available_capital"):
                balance = float(self.risk.get_available_capital())
        except Exception:
            balance = 0.0

        max_slots = getattr(self.risk, "max_trades", 4) if self.risk is not None else 4

        provider = self.system_context_provider

        if provider is not None:

            try:
                if hasattr(provider, "get_active_positions"):
                    active_slots = int(provider.get_active_positions())
            except Exception:
                active_slots = 0

            try:
                if hasattr(provider, "get_system_loss_streak"):
                    loss_streak = int(provider.get_system_loss_streak())
            except Exception:
                loss_streak = 0

            try:
                if hasattr(provider, "get_recent_win_rate"):
                    win_rate_recent = float(provider.get_recent_win_rate())
            except Exception:
                win_rate_recent = 0.50

            try:
                if hasattr(provider, "get_drawdown_pct"):
                    drawdown_pct = float(provider.get_drawdown_pct())
            except Exception:
                drawdown_pct = 0.0

        if win_rate_recent < 0.0:
            win_rate_recent = 0.0
        elif win_rate_recent > 1.0:
            win_rate_recent = 1.0

        if drawdown_pct < 0.0:
            drawdown_pct = 0.0

        if active_slots < 0:
            active_slots = 0

        return SystemContext(
            balance=balance,
            active_slots=active_slots,
            max_slots=max_slots,
            drawdown_pct=drawdown_pct,
            loss_streak=loss_streak,
            win_rate_recent=win_rate_recent,
        )

    def _check_pre_movement_entry(self, snapshot: MarketSnapshot, policy):

        reasons: List[str] = []

        symbol = getattr(snapshot, "pair", "UNKNOWN")

        price = float(snapshot.price or 0.0)
        ema_fast = float(snapshot.ema_fast or 0.0)
        ema_slow = float(snapshot.ema_slow or 0.0)
        rsi = float(snapshot.rsi or 0.0)
        volume_ratio = float(snapshot.volume_ratio or 0.0)

        # ======================================================
        # 🔥 PRE-MOVEMENT V2 — BLOQUEIO DE SPIKE FRACO
        # ======================================================
        if volume_ratio < 1.0:
            reasons.append("PRE_V2: volume baixo")
            logger.info(
                f"[PRE V2] BLOQUEADO | {symbol} | volume baixo | vol={volume_ratio:.3f}"
            )
            return False, reasons, 0.0

        if rsi < 50:
            reasons.append("PRE_V2: RSI fraco")
            logger.info(f"[PRE V2] BLOQUEADO | {symbol} | RSI fraco | rsi={rsi:.2f}")
            return False, reasons, 0.0

        if price <= 0:
            reasons.append("Preço inválido")
            logger.info(f"[PRE-MOVEMENT] BLOQUEADO | {symbol} | preço inválido")
            return False, reasons, 0.0

        if ema_fast <= 0 or ema_slow <= 0:
            reasons.append("EMAs inválidas")
            logger.info(f"[PRE-MOVEMENT] BLOQUEADO | {symbol} | EMAs inválidas")
            return False, reasons, 0.0

        if ema_fast <= ema_slow:
            reasons.append("Sem inclinação positiva mínima")
            logger.info(
                f"[PRE-MOVEMENT] BLOQUEADO | {symbol} | "
                f"ema_fast={ema_fast:.8f} <= ema_slow={ema_slow:.8f}"
            )
            return False, reasons, 0.0

        ema_spread = abs(ema_fast - ema_slow) / price if price > 0 else 0.0

        regime = str(getattr(policy, "regime", "")).upper()

        if regime in ("AGGRESSIVE_OK", "AGGRESSIVE", "STRONG", "BULLISH_STRONG"):
            pre_min_spread = max(float(policy.min_ema_spread) * 0.60, 0.00012)
            pre_min_volume = max(float(policy.min_volume_ratio) * 0.75, 0.85)
            pre_min_rsi = max(float(policy.min_rsi) - 4.0, 44.0)

        elif regime in ("TRADE_OK", "MODERATE", "MODERADO"):
            pre_min_spread = max(float(policy.min_ema_spread) * 0.55, 0.00012)
            pre_min_volume = max(float(policy.min_volume_ratio) * 0.80, 0.90)
            pre_min_rsi = max(float(policy.min_rsi) - 3.0, 45.0)

        else:
            pre_min_spread = max(float(policy.min_ema_spread) * 0.85, 0.00020)
            pre_min_volume = max(float(policy.min_volume_ratio) * 0.90, 1.00)
            pre_min_rsi = max(float(policy.min_rsi) - 2.0, 46.0)

        if ema_spread < pre_min_spread:
            reasons.append(
                f"PRE: spread insuficiente ({ema_spread:.6f} < {pre_min_spread:.6f})"
            )
            logger.info(
                f"[PRE-MOVEMENT] BLOQUEADO | {symbol} | "
                f"spread={ema_spread:.6f} | min={pre_min_spread:.6f} | regime={regime}"
            )
            return False, reasons, 0.0

        if volume_ratio < pre_min_volume:
            reasons.append(
                f"PRE: volume insuficiente ({volume_ratio:.3f} < {pre_min_volume:.3f})"
            )
            logger.info(
                f"[PRE-MOVEMENT] BLOQUEADO | {symbol} | "
                f"vol={volume_ratio:.3f} | min={pre_min_volume:.3f} | regime={regime}"
            )
            return False, reasons, 0.0

        if rsi < pre_min_rsi:
            reasons.append(f"PRE: RSI insuficiente ({rsi:.2f} < {pre_min_rsi:.2f})")
            logger.info(
                f"[PRE-MOVEMENT] BLOQUEADO | {symbol} | "
                f"rsi={rsi:.2f} | min={pre_min_rsi:.2f} | regime={regime}"
            )
            return False, reasons, 0.0

        # ======================================================
        # 🔥 RSI CONTEXTUAL DINÂMICO — CONTINUAÇÃO FORTE
        # ======================================================

        rsi_max_ext = float(policy.max_rsi) + 3.0

        strong_continuation_context = (
            ema_fast > ema_slow
            and volume_ratio >= 1.35
            and ema_spread >= pre_min_spread
        )

        if strong_continuation_context:
            rsi_max_ext += 3.0  # permite continuação até faixa ~71/72

        if rsi > rsi_max_ext:
            reasons.append(f"PRE: RSI excessivo ({rsi:.2f})")
            logger.info(
                f"[PRE-MOVEMENT] BLOQUEADO | {symbol} | "
                f"rsi={rsi:.2f} | max_ext={rsi_max_ext:.2f} | "
                f"contextual={strong_continuation_context}"
            )
            return False, reasons, 0.0

        volume_score = min(volume_ratio / max(pre_min_volume * 1.5, 1.0), 1.0)
        spread_score = min(ema_spread / max(pre_min_spread * 1.8, 0.0003), 1.0)

        if rsi >= float(policy.min_rsi):
            rsi_score = 1.0
        elif rsi >= pre_min_rsi:
            rsi_score = 0.80
        else:
            rsi_score = 0.60

        confidence = (volume_score * 0.35) + (spread_score * 0.35) + (rsi_score * 0.30)
        confidence = round(min(max(confidence, 0.0), 1.0), 3)

        reasons.append(
            f"PRE_MOVEMENT_OK | rsi={rsi:.2f} | vol={volume_ratio:.3f} | "
            f"spread={ema_spread:.6f}"
        )

        logger.info(
            f"[PRE-MOVEMENT] APROVADO | {symbol} | "
            f"spread={ema_spread:.6f} | vol={volume_ratio:.3f} | "
            f"rsi={rsi:.2f} | conf={confidence:.3f} | regime={regime}"
        )

        return True, reasons, confidence

    # -------------------------------------------------------------------------
    # MOMENTUM / MCE / DYNAMIC POLICY
    # -------------------------------------------------------------------------

    def _check_momentum_buy(self, snapshot: MarketSnapshot, policy):

        logger.info("🔥 MCE FUNCTION EXECUTANDO 🔥")

        reasons: List[str] = []

        symbol = getattr(snapshot, "pair", "UNKNOWN")

        price = float(snapshot.price or 0.0)
        ema_fast = float(snapshot.ema_fast or 0.0)
        ema_slow = float(snapshot.ema_slow or 0.0)
        rsi = float(snapshot.rsi or 0.0)
        volume_ratio = float(snapshot.volume_ratio or 0.0)

        # ======================================================
        # 🔥 MCE V2 — BLOQUEIO DE ENTRADA PRECOCE (SIDEWAYS FRACO)
        # ======================================================
        market_state_raw = (
            str(getattr(snapshot, "market_state", "") or "").strip().upper()
        )
        trend_raw = str(getattr(snapshot, "trend", "") or "").strip().upper()
        momentum_raw = str(getattr(snapshot, "momentum", "") or "").strip().upper()
        volume_state_raw = (
            str(getattr(snapshot, "volume_state", "") or "").strip().upper()
        )

        if (
            market_state_raw == "SIDEWAYS"
            and momentum_raw == "NEUTRAL"
            and volume_state_raw == "LOW"
        ):

            reasons.append("MCE_V2: SIDEWAYS + NEUTRAL + LOW_VOLUME")
            logger.info(
                f"[MCE V2] BLOQUEADO | {symbol} | "
                f"market_state={market_state_raw} | "
                f"momentum={momentum_raw} | "
                f"volume_state={volume_state_raw} | "
                f"rsi={rsi:.2f} | vol={volume_ratio:.3f}"
            )
            return False, reasons, 0.0

        # ======================================================
        # 🔥 H&A PATCH — NEUTRAL PREMIUM LIBERATION (NOVO)
        # ======================================================
        neutral_premium = (
            market_state_raw in ("SIDEWAYS", "CAUTIOUS")
            and momentum_raw == "NEUTRAL"
            and trend_raw.endswith("UPTREND")
            and volume_ratio >= 2.5
            and 40 <= rsi <= 58
        )

        if neutral_premium:
            logger.info(
                f"[MCE PATCH] NEUTRAL PREMIUM LIBERADO | {symbol} | "
                f"rsi={rsi:.2f} | vol={volume_ratio:.2f}"
            )

        if price <= 0:
            reasons.append("Preço inválido")
            logger.info(f"[MCE] BLOQUEADO | {symbol} | preço inválido")
            return False, reasons, 0.0

        if ema_fast <= 0 or ema_slow <= 0:
            reasons.append("EMAs inválidas")
            logger.info(f"[MCE] BLOQUEADO | {symbol} | EMAs inválidas")
            return False, reasons, 0.0

        ema_spread = abs(ema_fast - ema_slow) / price if price > 0 else 0.0

        # -----------------------------------------------------
        # TENDÊNCIA / LATERAL OPERÁVEL
        # -----------------------------------------------------
        is_trending = ema_fast > ema_slow and ema_spread >= float(policy.min_ema_spread)

        is_sideways_tradable = (
            bool(policy.allow_sideways)
            and ema_fast > ema_slow
            and ema_spread >= float(policy.sideways_min_spread)
            and rsi >= float(policy.sideways_min_rsi)
            and volume_ratio >= float(policy.sideways_min_volume)
        )

        if not (is_trending or is_sideways_tradable):
            reasons.append("Sem tendência ou lateral não operável")
            logger.info(
                f"[MCE] BLOQUEADO | {symbol} | sem tendência/lateral operável "
                f"| ema_fast={ema_fast:.8f} | ema_slow={ema_slow:.8f} "
                f"| spread={ema_spread:.6f} | rsi={rsi:.2f} | vol={volume_ratio:.3f}"
            )
            return False, reasons, 0.0

        # -----------------------------------------------------
        # RSI DINÂMICO
        # -----------------------------------------------------
        if rsi < float(policy.min_rsi):
            reasons.append(
                f"RSI abaixo do mínimo dinâmico: {rsi:.2f} < {policy.min_rsi:.2f}"
            )
            logger.info(
                f"[MCE] BLOQUEADO | {symbol} | RSI baixo "
                f"| rsi={rsi:.2f} | min={float(policy.min_rsi):.2f}"
            )
            return False, reasons, 0.0

        if rsi > float(policy.max_rsi):
            reasons.append(f"RSI alto (continuação de tendência): {rsi:.2f}")

        # -----------------------------------------------------
        # VOLUME DINÂMICO
        # -----------------------------------------------------
        if volume_ratio < float(policy.min_volume_ratio):
            reasons.append(
                f"Volume abaixo do mínimo dinâmico: "
                f"{volume_ratio:.3f} < {policy.min_volume_ratio:.3f}"
            )
            logger.info(
                f"[MCE] BLOQUEADO | {symbol} | volume dinâmico insuficiente "
                f"| vol={volume_ratio:.3f} | min={float(policy.min_volume_ratio):.3f}"
            )
            return False, reasons, 0.0

        # -----------------------------------------------------
        # PREÇO ACIMA DA EMA RÁPIDA
        # -----------------------------------------------------
        if price < ema_fast:
            reasons.append("Preço abaixo da EMA (pullback)")
            logger.info(
                f"[MCE] ALERTA | {symbol} | preço abaixo da EMA rápida "
                f"| price={price:.8f} | ema_fast={ema_fast:.8f}"
            )

        # -----------------------------------------------------
        # 🔥 MCE — MOMENTUM CONFIRMATION ENTRY (DINÂMICO POR REGIME)
        # -----------------------------------------------------
        regime = str(getattr(policy, "regime", "")).upper()

        if regime in ("AGGRESSIVE_OK", "AGGRESSIVE", "STRONG", "BULLISH_STRONG"):
            spread_multiplier = 1.00
            volume_multiplier = 1.00
            spread_floor = 0.00020
            volume_floor = 0.90

        elif regime in ("TRADE_OK", "MODERATE", "MODERADO"):
            spread_multiplier = 1.10
            volume_multiplier = 1.05
            spread_floor = 0.00025
            volume_floor = 1.00

        else:
            # CAUTIOUS / fraco / fallback
            spread_multiplier = 1.20
            volume_multiplier = 1.20
            spread_floor = 0.00030
            volume_floor = 1.20

        mce_min_spread = max(
            float(policy.min_ema_spread) * spread_multiplier,
            spread_floor,
        )
        mce_min_volume = max(
            float(policy.min_volume_ratio) * volume_multiplier,
            volume_floor,
        )

        # spread mínimo mais forte para confirmação
        if ema_spread < mce_min_spread:
            reasons.append(
                f"MCE: spread insuficiente ({ema_spread:.6f} < {mce_min_spread:.6f})"
            )
            logger.info(
                f"[MCE] BLOQUEADO | {symbol} | spread insuficiente "
                f"| spread={ema_spread:.6f} | min={mce_min_spread:.6f} "
                f"| regime={regime}"
            )
            return False, reasons, 0.0

        # volume mais forte para entrada
        if volume_ratio < mce_min_volume:
            reasons.append(
                f"MCE: volume insuficiente para confirmação "
                f"({volume_ratio:.3f} < {mce_min_volume:.3f})"
            )
            logger.info(
                f"[MCE] BLOQUEADO | {symbol} | volume insuficiente para confirmação "
                f"| vol={volume_ratio:.3f} | min={mce_min_volume:.3f} "
                f"| regime={regime}"
            )
            return False, reasons, 0.0

        logger.info(
            f"[MCE] APROVADO | {symbol} | "
            f"spread={ema_spread:.6f} | volume={volume_ratio:.3f} | rsi={rsi:.2f}"
        )

        # -----------------------------------------------------
        # CONFIDENCE
        # -----------------------------------------------------
        volume_score = min(volume_ratio / 2.5, 1.0)

        rsi_mid = (float(policy.min_rsi) + float(policy.max_rsi)) / 2.0
        if rsi >= rsi_mid:
            rsi_score = 1.0
        elif rsi >= float(policy.min_rsi):
            rsi_score = 0.80
        else:
            rsi_score = 0.60

        spread_target = max(float(policy.min_ema_spread) * 2.0, 0.0006)
        trend_score = min(ema_spread / spread_target, 1.0)

        confidence = (volume_score * 0.4) + (rsi_score * 0.3) + (trend_score * 0.3)
        confidence = round(min(max(confidence, 0.0), 1.0), 3)

        reasons.append(
            f"DYNAMIC OK | rsi={rsi:.2f} | vol={volume_ratio:.3f} | "
            f"spread={ema_spread:.6f} | min_rsi={policy.min_rsi:.2f}"
        )

        logger.info(
            f"[MCE] CONFIDENCE | {symbol} | confidence={confidence:.3f} "
            f"| volume_score={volume_score:.3f} | rsi_score={rsi_score:.3f} "
            f"| trend_score={trend_score:.3f}"
        )

        # ======================================================
        # 🔥 PATCH — MQII CONTEXTUAL FILTER (CAUTIOUS)
        # ======================================================
        try:
            mqii = getattr(self, "mqii_quality", None)

            if isinstance(mqii, dict):
                mqii_state = str(mqii.get("state", "")).strip().upper()
                mqii_score = float(mqii.get("score", 0.0) or 0.0)

                if mqii_state == "CAUTIOUS":

                    trend_raw = str(getattr(snapshot, "trend", "")).upper()
                    momentum_raw = str(getattr(snapshot, "momentum", "")).upper()
                    volume_ratio = float(snapshot.volume_ratio or 0.0)

                    strong_confirmation = (
                        trend_raw.endswith("UPTREND")
                        and momentum_raw.endswith("BULLISH")
                        and volume_ratio >= 1.10
                        and confidence >= 0.70
                    )

                    premium_override = (
                        trend_raw.endswith("UPTREND")
                        and momentum_raw.endswith("BULLISH")
                        and volume_ratio >= 1.80
                        and confidence >= 0.80
                        and 52 <= rsi <= 72
                    )

                    if not strong_confirmation and not premium_override:
                        rejection_reason = (
                            "DECISION_BLOCK_MQII_CAUTIOUS_WEAK_CONFIRMATION"
                        )

                        logger.info(
                            f"[DECISION INTEL] {symbol} | "
                            f"reason={rejection_reason} | "
                            f"mqii={mqii_state} | mqii_score={mqii_score:.3f} | "
                            f"trend={trend_raw} | momentum={momentum_raw} | "
                            f"vol={volume_ratio:.2f} | conf={confidence:.3f}"
                        )

                        return False, [rejection_reason], 0.0

        except Exception as e:
            logger.warning(f"[MQII FILTER ERROR] {e}")

        return True, reasons, confidence
