# ============================================================
# core/radar/market_radar_engine.py
# Radar contínuo de oportunidades do H&A
# FILTRO OPERACIONAL REFORÇADO
# ============================================================

import time
import threading
from typing import Dict, Iterable, Optional, Set, List

from core.radar.market_ranking_engine import MarketRankingEngine
from core.scanner.opportunity_scanner import OpportunityScanner
from core.market.market_liquidity_analyzer import MarketLiquidityAnalyzer
from core.scanner.token_ranker import TokenRanker
from core.mce.momentum_confirmation_engine import MomentumConfirmationEngine
from core.selection.selection_policy_engine import SelectionPolicyEngine
from core.market_quality.service import MarketQualityService


class MarketRadarEngine:
    """
    Radar de oportunidades com filtro operacional reforçado.

    Responsabilidades:
    - escanear e refinar ranking técnico
    - remover símbolos inelegíveis operacionalmente
    - aplicar penalty no score final
    - impedir que ativos bloqueados/laterais dominem o ranking
    """

    def __init__(self, client, scan_interval=15):
        self.client = client
        self.scan_interval = scan_interval

        self.scanner = OpportunityScanner(client)
        self.token_ranker = TokenRanker(client)

        self.mce = MomentumConfirmationEngine()
        self.selection_engine = SelectionPolicyEngine()
        self.lc1e = self.selection_engine.lc1e

        self.rank_engine = MarketRankingEngine(self.token_ranker, self.lc1e)

        self.running = False
        self.thread = None
        self.latest_ranking: List[dict] = []

        self.liquidity_analyzer = MarketLiquidityAnalyzer()

        # =========================================================
        # MQII — Market Quality Internal Indicator
        # =========================================================
        self.mqii = MarketQualityService()

        self.market_quality = {
            "state": "UNKNOWN",
            "label": "SEM DADOS",
            "score": 0.0,
            "message": "MQII não inicializado.",
            "total_assets": 0,
            "uptrend_count": 0,
            "bullish_momentum_count": 0,
            "bearish_count": 0,
            "high_volume_count": 0,
            "neutral_momentum_count": 0,
            "refined_count": 0,
            "approved_count": 0,
            "structural_block_count": 0,
            "avg_volume_ratio": 0.0,
            "avg_market_score": 0.0,
            "components": {},
            "timestamp": "",
        }

        self.market_liquidity = {
            "liquidity_score": 0.0,
            "liquidity_label": "SEM DADOS",
            "liquidity_message": "Sem dados suficientes.",
            "avg_volume_ratio": 0.0,
            "uptrend_count": 0,
            "refined_count": 0,
            "approved_count": 0,
        }

        self.market_liquidity_history = []
        self.max_liquidity_history = 100

        # ----------------------------------------------------
        # ESTADO OPERACIONAL
        # ----------------------------------------------------
        self.trade_cooldowns: Dict[str, int] = {}
        self.rejection_cooldowns: Dict[str, int] = {}
        self.penalty_map: Dict[str, int] = {}
        self.last_traded_symbol: Optional[str] = None

        # parâmetros operacionais
        self.max_penalty_allowed = 2
        self.penalty_score_weight = 0.20
        self.block_last_traded_symbol = True

        # parâmetros de qualidade
        self.min_market_score = 1.0
        self.min_volume_ratio = 0.65
        self.min_rsi = 45.0
        self.min_final_score = 0.30

        self._last_radar_summary = self._new_radar_summary()

    # ========================================================
    # HELPERS
    # ========================================================

    def _new_radar_summary(self) -> dict:
        return {
            "no_uptrend": 0,
            "score_baixo": 0,
            "quality_filter": 0,
            "rsi_extremo": 0,
            "volume_extremo": 0,
            "structural_block": 0,
        }

    def _reset_radar_summary(self):
        self._last_radar_summary = self._new_radar_summary()

    def _count_radar_rejection(self, reason: str):
        if not reason:
            return

        reason_norm = str(reason).strip().upper()

        mapping = {
            "NO_UPTREND": "no_uptrend",
            "SCORE_BAIXO": "score_baixo",
            "QUALITY_FILTER": "quality_filter",
            "RSI_EXTREMO": "rsi_extremo",
            "VOLUME_EXTREMO": "volume_extremo",
            "STRUCTURAL_BLOCK": "structural_block",
        }

        key = mapping.get(reason_norm)
        if key:
            self._last_radar_summary[key] += 1

    def _log_radar_summary(self):
        s = self._last_radar_summary
        print(
            "[RADAR SUMMARY] "
            f"no_uptrend={s['no_uptrend']} | "
            f"score_baixo={s['score_baixo']} | "
            f"quality_filter={s['quality_filter']} | "
            f"rsi_extremo={s['rsi_extremo']} | "
            f"volume_extremo={s['volume_extremo']} | "
            f"structural_block={s['structural_block']}"
        )

    def _safe_upper(self, value):
        if value is None:
            return ""

        try:
            if hasattr(value, "value"):
                return str(value.value).strip().upper()
            return str(value).strip().upper()
        except Exception:
            return ""

    def _to_float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default

    def _safe_symbol(self, symbol):
        if symbol is None:
            return ""
        try:
            return str(symbol).strip().upper()
        except Exception:
            return ""

    def _normalize_symbol_set(
        self, values: Optional[Iterable], default_cycles: int = 1
    ):
        normalized: Dict[str, int] = {}

        if not values:
            return normalized

        for value in values:
            if isinstance(value, tuple) and len(value) == 2:
                symbol = self._safe_symbol(value[0])
                try:
                    cycles = max(0, int(value[1]))
                except Exception:
                    cycles = default_cycles
            else:
                symbol = self._safe_symbol(value)
                cycles = default_cycles

            if symbol and cycles > 0:
                normalized[symbol] = cycles

        return normalized

    # ========================================================
    # API EXTERNA DE ESTADO OPERACIONAL
    # ========================================================

    def set_trade_cooldowns(self, symbols: Optional[Iterable]):
        self.trade_cooldowns = self._normalize_symbol_set(symbols)

    def set_rejection_cooldowns(self, symbols: Optional[Iterable]):
        self.rejection_cooldowns = self._normalize_symbol_set(symbols)

    def set_penalty_map(self, penalty_map: Optional[Dict[str, int]]):
        self.penalty_map = {}

        if not penalty_map:
            return

        for symbol, value in penalty_map.items():
            normalized_symbol = self._safe_symbol(symbol)
            if not normalized_symbol:
                continue

            try:
                penalty_value = int(value)
            except Exception:
                penalty_value = 0

            if penalty_value < 0:
                penalty_value = 0

            self.penalty_map[normalized_symbol] = penalty_value

    def set_last_traded_symbol(self, symbol: Optional[str]):
        normalized = self._safe_symbol(symbol)
        self.last_traded_symbol = normalized or None

    def register_trade_result(self, symbol: str, was_profit: bool):
        """
        Atualiza o penalty do símbolo com base no resultado do trade.
        Pode ser chamado externamente ao fechar uma posição.
        """
        normalized_symbol = self._safe_symbol(symbol)
        if not normalized_symbol:
            return

        current = self.penalty_map.get(normalized_symbol, 0)

        if was_profit:
            self.penalty_map[normalized_symbol] = max(0, current - 1)
        else:
            self.penalty_map[normalized_symbol] = current + 1

    def _consume_symbol_cooldown(
        self, cooldown_map: Dict[str, int], symbol: str
    ) -> bool:
        remaining = int(cooldown_map.get(symbol, 0) or 0)

        if remaining <= 0:
            cooldown_map.pop(symbol, None)
            return False

        remaining -= 1

        if remaining <= 0:
            cooldown_map.pop(symbol, None)
        else:
            cooldown_map[symbol] = remaining

        return True

        # ========================================================
        # FILTRO DE ELEGIBILIDADE
        # ========================================================

    def _is_symbol_blocked(self, symbol: str):
        if self._consume_symbol_cooldown(self.trade_cooldowns, symbol):
            return True

        if self._consume_symbol_cooldown(self.rejection_cooldowns, symbol):
            return True

        
        return False

    def _passes_operational_filter(self, item):
        if not isinstance(item, dict):
            return False

        symbol = self._safe_symbol(item.get("symbol"))
        if not symbol:
            return False

        if self._is_symbol_blocked(symbol):
            return False

        penalty = self.penalty_map.get(symbol, 0)
        if penalty >= self.max_penalty_allowed:
            return False

        return True

    def _passes_quality_filter(self, item):
        if not isinstance(item, dict):
            return False

        analysis = item.get("analysis") or {}
        snapshot = item.get("snapshot")
        symbol = self._safe_symbol(item.get("symbol"))

        if not symbol or snapshot is None:
            return False

        market_score = self._to_float(analysis.get("market_score", 0), default=0.0)
        volume_ratio = self._to_float(
            analysis.get("volume_ratio", getattr(snapshot, "volume_ratio", 0.0)),
            default=0.0,
        )
        rsi_value = self._to_float(
            analysis.get("rsi", getattr(snapshot, "rsi_14", 0.0)),
            default=0.0,
        )
        raw_score = self._to_float(item.get("score", 0.0), default=0.0)

        trend_state = self._safe_upper(analysis.get("trend"))
        momentum_state = self._safe_upper(analysis.get("momentum"))
        market_state = self._safe_upper(analysis.get("market_state"))

        if market_score < 0:
            self._count_radar_rejection("SCORE_BAIXO")
            return False

        if volume_ratio < 0:
            self._count_radar_rejection("VOLUME_EXTREMO")
            return False

        if rsi_value <= 0:
            self._count_radar_rejection("RSI_EXTREMO")
            return False

        if raw_score < 0:
            self._count_radar_rejection("SCORE_BAIXO")
            return False

        if market_score < self.min_market_score:
            self._count_radar_rejection("SCORE_BAIXO")
            return False

        if volume_ratio < 0.30:
            if trend_state != "UPTREND":
                self._count_radar_rejection("VOLUME_EXTREMO")
                return False

        if rsi_value < 35.0:
            self._count_radar_rejection("RSI_EXTREMO")
            return False

        if market_state == "SIDEWAYS":
            if not (volume_ratio >= 0.3 and rsi_value >= 45.0):
                self._count_radar_rejection("QUALITY_FILTER")
                return False

        if momentum_state == "NEUTRAL":
            if volume_ratio < 0.15:
                self._count_radar_rejection("VOLUME_EXTREMO")
                return False

            if trend_state == "UPTREND" and (42 <= rsi_value <= 65):
                pass
            else:
                self._count_radar_rejection("QUALITY_FILTER")
                return False

        if trend_state not in ("UPTREND", "STRONG_UPTREND"):
            self._count_radar_rejection("NO_UPTREND")
            return False

        return True

    def _apply_penalty_to_item(self, item):
        if not isinstance(item, dict):
            return item

        symbol = self._safe_symbol(item.get("symbol"))
        if not symbol:
            return item

        base_score = self._to_float(item.get("score", 0.0), default=0.0)
        penalty = self.penalty_map.get(symbol, 0)

        final_score = max(0.0, base_score - (penalty * self.penalty_score_weight))

        adjusted_item = dict(item)
        adjusted_item["base_score"] = base_score
        adjusted_item["penalty"] = penalty
        adjusted_item["score"] = final_score

        return adjusted_item

    def _build_mce_market_data(self, item):

        analysis = item.get("analysis") or {}
        snapshot = item.get("snapshot") or {}

        return {
            "symbol": item.get("symbol"),
            "rsi": self._to_float(analysis.get("rsi"), default=50.0),
            "volume_ratio": self._to_float(analysis.get("volume_ratio"), default=0.0),
            "momentum": self._safe_upper(analysis.get("momentum")),
            "trend": self._safe_upper(analysis.get("trend")),
            "ema_10": self._to_float(getattr(snapshot, "ema_10", None), default=0.0),
            "ema_20": self._to_float(getattr(snapshot, "ema_20", None), default=0.0),
            "ema_50": self._to_float(getattr(snapshot, "ema_50", None), default=0.0),
        }

    def _record_radar_non_execution(
        self,
        item,
        reason: str,
        summary: str,
        market_context: Optional[dict] = None,
    ) -> None:
        try:
            analysis = item.get("analysis", {}) or {}
            snapshot = item.get("snapshot")
            symbol = self._safe_symbol(item.get("symbol"))

            event = self.lc1e.build_event(
                symbol=symbol,
                reason=reason,
                analysis=analysis,
                snapshot=snapshot,
                market_context=market_context or {},
                event_type="NON_EXECUTION",
                source="market_radar_engine",
                summary=summary,
            )

            print(
                f"[DEBUG RADAR LC1E] symbol={self._safe_symbol(item.get('symbol'))} reason={reason}"
            )

            self.lc1e.record_event(event)

        except Exception as e:
            print(
                f"[LC1E RADAR ERROR] symbol={self._safe_symbol(item.get('symbol'))} | "
                f"reason={reason} | erro={e}"
            )

    def _filter_ranking(self, ranking):
        if not ranking:
            return []

        filtered = []

        for item in ranking:
            symbol = self._safe_symbol(item.get("symbol"))

            reason_flag = item.get("_radar_rejection_reason")
            if reason_flag:
                self._count_radar_rejection(reason_flag)

            if not self._passes_operational_filter(item):
                print(f"[RADAR FILTER] {symbol} REJEITADO no filtro operacional")

                self._record_radar_non_execution(
                    item=item,
                    reason="OPERATIONAL_FILTER_REJECTION",
                    summary="RADAR_OPERATIONAL_FILTER",
                    market_context={
                        "trade_cooldowns": sorted(self.trade_cooldowns),
                        "rejection_cooldowns": sorted(self.rejection_cooldowns),
                        "last_traded_symbol": self.last_traded_symbol,
                        "penalty_value": self.penalty_map.get(symbol, 0),
                    },
                )

                continue

            if not self._passes_quality_filter(item):
                analysis = item.get("analysis") or {}
                print(
                    f"[RADAR FILTER] {symbol} REJEITADO no filtro de qualidade | "
                    f"momentum={self._safe_upper(analysis.get('momentum'))} | "
                    f"volume={self._safe_upper(analysis.get('volume'))} | "
                    f"market_score={self._to_float(analysis.get('market_score', 0))}"
                )

                self._record_radar_non_execution(
                    item=item,
                    reason="QUALITY_FILTER_REJECTION",
                    summary="RADAR_QUALITY_FILTER",
                    market_context={
                        "raw_score": self._to_float(
                            item.get("score", 0.0), default=0.0
                        ),
                        "market_score": self._to_float(
                            analysis.get("market_score", 0), default=0.0
                        ),
                        "volume_ratio": self._to_float(
                            analysis.get(
                                "volume_ratio",
                                getattr(item.get("snapshot"), "volume_ratio", 0.0),
                            ),
                            default=0.0,
                        ),
                        "rsi": self._to_float(
                            analysis.get(
                                "rsi", getattr(item.get("snapshot"), "rsi_14", 0.0)
                            ),
                            default=0.0,
                        ),
                        "momentum": self._safe_upper(analysis.get("momentum")),
                        "volume_state": self._safe_upper(analysis.get("volume")),
                        "market_state": self._safe_upper(analysis.get("market_state")),
                        "trend": self._safe_upper(analysis.get("trend")),
                    },
                )

                continue

            adjusted_item = self._apply_penalty_to_item(item)

            # =========================================================
            # 🔥 INJETAR CONTEXTO DE MERCADO (CRÍTICO)
            # =========================================================
            market_context = {
                "mqii_state": self._safe_upper(self.market_quality.get("state")),
                "liquidity_score": self._to_float(self.market_liquidity.get("liquidity_score", 0.0)),
                "approved_count": int(self.market_liquidity.get("approved_count", 0) or 0),
                "uptrend_count": int(self.market_liquidity.get("uptrend_count", 0) or 0),
                "avg_volume_ratio": self._to_float(self.market_liquidity.get("avg_volume_ratio", 0.0)),
            }

            adjusted_item["market_context"] = market_context


            # =========================================================
            # SELECTION POLICY ENGINE (FILTRO SOBERANO)
            # =========================================================
            selection_decision = self.selection_engine.evaluate(item)
            adjusted_item["selection_score"] = selection_decision.final_score

            if not selection_decision.approved:
                analysis = adjusted_item.get("analysis") or {}
                snapshot = adjusted_item.get("snapshot")

                volume_ratio = self._to_float(
                    analysis.get(
                        "volume_ratio",
                        getattr(snapshot, "volume_ratio", 0.0) if snapshot else 0.0,
                    ),
                    default=0.0,
                )
                rsi_value = self._to_float(
                    analysis.get(
                        "rsi",
                        getattr(snapshot, "rsi_14", 0.0) if snapshot else 0.0,
                    ),
                    default=0.0,
                )
                trend_state = self._safe_upper(analysis.get("trend"))
                momentum_state = self._safe_upper(analysis.get("momentum"))

                selection_override_allowed = (
                    selection_decision.final_score >= 0.85
                    and trend_state in ("UPTREND", "STRONG_UPTREND")
                    and momentum_state in ("BULLISH", "NEUTRAL")
                    and volume_ratio >= 1.0
                    and 45 <= rsi_value <= 68
                )

                if not selection_override_allowed:
                    print(
                        f"[SELECTION FILTER] {symbol} REJEITADO | "
                        f"motivos={','.join(selection_decision.rejection_reasons)}"
                    )
                    continue
                else:
                    print(
                        f"[SELECTION FILTER] {symbol} LIBERAÇÃO CONTROLADA | "
                        f"selection_score={selection_decision.final_score:.4f} | "
                        f"trend={trend_state} | momentum={momentum_state} | "
                        f"volume_ratio={volume_ratio:.2f} | rsi={rsi_value:.2f}"
                    )

            # ========================================================
            # 🔥 MCE SOFT FILTER — NÃO BLOQUEAR TOTALMENTE
            # ========================================================
            mce_result = self.mce.confirm(adjusted_item)

            if not mce_result:
                print(f"[RADAR FILTER] {symbol} MCE fraco (seguindo para decisão)")

                # marca como fraco para o Decision decidir depois
                adjusted_item["mce_weak"] = True
            else:
                adjusted_item["mce_weak"] = False
            

            dynamic_min_final_score = self._get_dynamic_min_final_score()
            final_score = self._to_float(adjusted_item.get("score", 0.0), default=0.0)

            # ======================================================
            # 🔥 H&A PATCH — MCE V3 (CONFIRMAÇÃO DINÂMICA)
            # ======================================================

            mqii_state = self._safe_upper(self.market_quality.get("state"))
            liquidity_score = self._to_float(self.market_liquidity.get("liquidity_score", 0.0))

            # ======================================================
            # 🔥 FALLBACK — CONTEXTO INICIAL (MQII NÃO PRONTO)
            # ======================================================
            if mqii_state in ("", "UNKNOWN") or liquidity_score <= 0:
                mqii_state = "CAUTIOUS"
                liquidity_score = 0.40


            if adjusted_item.get("mce_weak", False):

                # ======================================================
                # 🔥 ALO LEARNING — MCE V3 WEAK CONFIRMATION
                # ======================================================
                self._record_radar_non_execution(
                    item=adjusted_item,
                    reason="MCE_V3_WEAK_CONFIRMATION",
                    summary="RADAR_MCE_WEAK",
                    market_context={
                        "mqii_state": mqii_state,
                        "liquidity_score": liquidity_score,
                        "final_score": final_score,
                        "dynamic_min_score": dynamic_min_final_score,
                        "mce_weak": True,
                    },
                )

                # ======================================================
                # 🔥 MCE V3.2 — BLOQUEIO DE MCE FRACO EM MERCADO CAUTELOSO
                # ======================================================
                selection_score = self._to_float(
                    adjusted_item.get("selection_score", 0.0),
                    default=0.0,
                )

                if (
                    mqii_state == "CAUTIOUS"
                    and final_score < 0.65
                    and selection_score < 0.90
                ):
                    print(
                        f"[MCE V3.2] {symbol} BLOQUEADO | "
                        f"mce_weak=True | final_score={final_score:.2f} | "
                        f"selection_score={selection_score:.2f} | "
                        f"mqii={mqii_state}"
                    )

                    self._record_radar_non_execution(
                        item=adjusted_item,
                        reason="MCE_V3_WEAK_BLOCKED_CAUTION",
                        summary="RADAR_MCE_WEAK_BLOCKED",
                        market_context={
                            "mqii_state": mqii_state,
                            "liquidity_score": liquidity_score,
                            "final_score": final_score,
                            "selection_score": selection_score,
                            "mce_weak": True,
                        },
                    )

                    continue

                # mercado forte → tolera mais
                if mqii_state in ("TRADE_OK", "AGGRESSIVE_OK") and liquidity_score >= 0.6:
                    dynamic_min_final_score += 0.04

            # mercado médio → exige mais confirmação
            elif mqii_state in ("CAUTIOUS", "SIDEWAYS"):
                  dynamic_min_final_score += 0.06

            # mercado fraco → bloqueia mais forte
            else:
                dynamic_min_final_score += 0.08

            print(
                f"[MCE V3] {symbol} ajuste dinâmico | "
                f"novo_min={dynamic_min_final_score:.2f} | "
                f"mqii={mqii_state} | liq={liquidity_score:.2f}"
            )

            if final_score < dynamic_min_final_score:
                print(
                    f"[RADAR FILTER] {symbol} REJEITADO após penalty | "
                    f"score_final={final_score:.2f} | "
                    f"min_dynamic={dynamic_min_final_score:.2f}"
                )

                self._record_radar_non_execution(
                    item=adjusted_item,
                    reason="POST_PENALTY_SCORE_BELOW_DYNAMIC_MIN",
                    summary="RADAR_POST_PENALTY_REJECTION",
                    market_context={
                        "base_score": self._to_float(
                            adjusted_item.get("base_score", 0.0), default=0.0
                        ),
                        "penalty": self._to_float(
                            adjusted_item.get("penalty", 0.0), default=0.0
                        ),
                        "final_score": final_score,
                        "min_final_score_static": self.min_final_score,
                        "min_final_score_dynamic": dynamic_min_final_score,
                        "liquidity_score": self._to_float(
                            self.market_liquidity.get("liquidity_score", 0.0),
                            default=0.0,
                        ),
                        "approved_count": int(
                            self.market_liquidity.get("approved_count", 0) or 0
                        ),
                        "refined_count": int(
                            self.market_liquidity.get("refined_count", 0) or 0
                        ),
                    },
                )

                continue

            filtered.append(adjusted_item)

        filtered.sort(
            key=lambda x: self._to_float(x.get("score", 0.0), default=0.0), reverse=True
        )

        return filtered

    def get_market_liquidity_trend(self):

        history = self.market_liquidity_history

        if len(history) < 20:
            return "SEM HISTÓRICO"

        recent = history[-10:]
        previous = history[-20:-10]

        recent_avg = sum(x.get("liquidity_score", 0.0) for x in recent) / len(recent)
        previous_avg = sum(x.get("liquidity_score", 0.0) for x in previous) / len(
            previous
        )

        delta = recent_avg - previous_avg

        if delta > 0.05:
            return "SUBINDO"
        elif delta < -0.05:
            return "CAINDO"
        else:
            return "ESTÁVEL"

    def _get_dynamic_min_final_score(self) -> float:
        liquidity_score = self._to_float(
            self.market_liquidity.get("liquidity_score", 0.0), default=0.0
        )

        approved_count = int(self.market_liquidity.get("approved_count", 0) or 0)
        refined_count = int(self.market_liquidity.get("refined_count", 0) or 0)

        mqii_score = self._to_float(self.market_quality.get("score", 0.0), default=0.0)
        mqii_state = self._safe_upper(self.market_quality.get("state", "UNKNOWN"))

        dynamic_score = self.min_final_score

        # Mercado forte
        if liquidity_score >= 0.75:
            dynamic_score = 0.29

        # Mercado saudável/moderado
        elif liquidity_score >= 0.55:
            dynamic_score = 0.27

        # Mercado em formação
        elif liquidity_score >= 0.40:
            dynamic_score = 0.25

        # Mercado fraco
        else:
            dynamic_score = 0.25

        # Respiro controlado se há mercado refinado, mas nada aprovado
        if refined_count > 0 and approved_count == 0:
            dynamic_score = min(dynamic_score, 0.24)

        # Modo oportunístico automático
        if self._is_opportunistic_mode_active():
            dynamic_score = min(dynamic_score, 0.22)

        # =====================================================
        # MQII — ajuste conservador por qualidade real de mercado
        # =====================================================
        if mqii_state == "NO_TRADE":
            dynamic_score = max(dynamic_score, 0.27)

        elif mqii_state == "CAUTIOUS":
            dynamic_score = max(dynamic_score, 0.25)

        elif mqii_state == "TRADE_OK":
            dynamic_score = min(dynamic_score, 0.24)

        elif mqii_state == "AGGRESSIVE_OK":
            dynamic_score = min(dynamic_score, 0.22)

        # ajuste fino complementar pelo score do MQII
        if mqii_score <= 0.10:
            dynamic_score = max(dynamic_score, 0.28)
        elif mqii_score >= 0.60:
            dynamic_score = min(dynamic_score, 0.23)

        return round(dynamic_score, 4)

    def _is_opportunistic_mode_active(self) -> bool:
        liquidity_score = self._to_float(
            self.market_liquidity.get("liquidity_score", 0.0), default=0.0
        )

        approved_count = int(self.market_liquidity.get("approved_count", 0) or 0)
        refined_count = int(self.market_liquidity.get("refined_count", 0) or 0)
        uptrend_count = int(self.market_liquidity.get("uptrend_count", 0) or 0)

        return (
            0.25 <= liquidity_score <= 0.45
            and approved_count == 0
            and refined_count > 0
            and uptrend_count >= 1
        )

    # ========================================================
    # LOOP PRINCIPAL
    # ========================================================

    def _radar_loop(self):
        while self.running:
            try:
                self._reset_radar_summary()

                raw_ranking = self.scanner.scan()
                refined, ranking_market_snapshot = self.rank_engine.refine(raw_ranking)

                ranking_summary = getattr(
                    self.rank_engine, "_radar_summary_local", None
                )

                if ranking_summary:
                    print(
                        "[RADAR SUMMARY] "
                        f"no_uptrend={ranking_summary.get('NO_UPTREND', 0)} | "
                        f"score_baixo={ranking_summary.get('SCORE_BAIXO', 0)} | "
                        f"quality_filter={ranking_summary.get('QUALITY_FILTER', 0)} | "
                        f"rsi_extremo={ranking_summary.get('RSI_EXTREMO', 0)} | "
                        f"volume_extremo={ranking_summary.get('VOLUME_EXTREMO', 0)} | "
                        f"structural_block={ranking_summary.get('STRUCTURAL_BLOCK', 0)}"
                    )

                filtered = self._filter_ranking(refined)

                self.latest_ranking = filtered

                print(
                    f"RADAR UPDATE: {len(filtered)} tokens aprovados "
                    f"(de {len(refined)} refinados)"
                )

                # =========================================================
                # MARKET LIQUIDITY
                # =========================================================
                liquidity_data = self.liquidity_analyzer.analyze(
                    all_analyses=raw_ranking,
                    refined_tokens=refined,
                    approved_tokens=filtered,
                    market_snapshot=ranking_market_snapshot,
                )

                # ============================================
                # CORREÇÃO — SINCRONIZA LIQUIDEZ NO SNAPSHOT
                # ============================================
                if isinstance(ranking_market_snapshot, dict):
                    ranking_market_snapshot["liquidity_score"] = liquidity_data.get("liquidity_score", 0.0)
                    ranking_market_snapshot["liquidity_label"] = liquidity_data.get("liquidity_label", "")
                    ranking_market_snapshot["liquidity_message"] = liquidity_data.get("liquidity_message", "")


                mqii_snapshot = self.mqii.evaluate_market(
                    all_analyses=raw_ranking,
                    refined_tokens=refined,
                    approved_tokens=filtered,
                    market_snapshot=ranking_market_snapshot,
                )

                if ranking_summary:
                    mqii_snapshot["structural_block_count"] = int(
                        ranking_summary.get("STRUCTURAL_BLOCK", 0)
                    )
                    mqii_snapshot["radar_summary"] = {
                        "no_uptrend": int(ranking_summary.get("NO_UPTREND", 0)),
                        "score_baixo": int(ranking_summary.get("SCORE_BAIXO", 0)),
                        "quality_filter": int(ranking_summary.get("QUALITY_FILTER", 0)),
                        "rsi_extremo": int(ranking_summary.get("RSI_EXTREMO", 0)),
                        "volume_extremo": int(ranking_summary.get("VOLUME_EXTREMO", 0)),
                        "structural_block": int(
                            ranking_summary.get("STRUCTURAL_BLOCK", 0)
                        ),
                    }

                print("[MARKET LIQUIDITY]", liquidity_data)
                print("[MQII]", mqii_snapshot)

                radar_summary = mqii_snapshot.get("radar_summary", {})
                if radar_summary:
                    print(
                        "[MQII RADAR SUMMARY] "
                        f"no_uptrend={radar_summary.get('no_uptrend', 0)} | "
                        f"score_baixo={radar_summary.get('score_baixo', 0)} | "
                        f"quality_filter={radar_summary.get('quality_filter', 0)} | "
                        f"rsi_extremo={radar_summary.get('rsi_extremo', 0)} | "
                        f"volume_extremo={radar_summary.get('volume_extremo', 0)} | "
                        f"structural_block={radar_summary.get('structural_block', 0)}"
                    )

                self.market_liquidity = liquidity_data

                # ============================================
                # SINCRONIZA LIQUIDEZ COM SNAPSHOT GLOBAL
                # ============================================
                if isinstance(ranking_market_snapshot, dict):
                    ranking_market_snapshot.update({
                        "liquidity_score": liquidity_data.get("liquidity_score", 0.0),
                        "liquidity_label": liquidity_data.get("liquidity_label", ""),
                        "liquidity_message": liquidity_data.get("liquidity_message", ""),
                    })

                self.market_quality = mqii_snapshot

                self.market_liquidity_history.append(liquidity_data.copy())

                if len(self.market_liquidity_history) > self.max_liquidity_history:
                    self.market_liquidity_history.pop(0)

                if filtered:
                    print(f"RADAR TOP: {filtered[0]}")
                else:
                    print("RADAR TOP: None")

            except Exception as e:
                print("Radar error:", e)

            time.sleep(self.scan_interval)

    # ========================================================
    # CONTROLE
    # ========================================================

    def start(self):
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._radar_loop, daemon=True)
        self.thread.start()

        print("MarketRadarEngine iniciado")

    def stop(self):
        self.running = False
        print("MarketRadarEngine parado")

    # ========================================================
    # ACESSO
    # ========================================================

    def get_top(self, n=10):
        return self.latest_ranking[:n]
