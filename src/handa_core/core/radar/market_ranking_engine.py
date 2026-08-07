# ============================================================
# core/market/market_ranking_engine.py
# Motor de ranking do radar de mercado do H&A
# VERSÃO BALANCEADA + AJUSTE FINO CONSERVADOR
# + LC1E NON_EXECUTION NO REFINE
# ============================================================
from core.alo_profile import AloProfileUpdater


class MarketRankingEngine:
    """
    Refina e ordena as oportunidades detectadas pelo scanner.
    Mantém perfil conservador, priorizando ativos mais confiáveis,
    líquidos e com melhor confirmação técnica.
    """

    def __init__(self, token_ranker=None, lc1e=None):

        self.token_ranker = token_ranker
        self.lc1e = lc1e
        self.alo_profile_updater = AloProfileUpdater()

        self._radar_summary_local = {
            "STRUCTURAL_BLOCK": 0,
            "NO_UPTREND": 0,
            "SCORE_BAIXO": 0,
            "QUALITY_FILTER": 0,
            "VOLUME_EXTREMO": 0,
            "RSI_EXTREMO": 0,
        }

        # ----------------------------------------------------
        # BLOQUEIO ESTRUTURAL DE ATIVOS ESPECULATIVOS / FRACOS
        # ----------------------------------------------------
        self.blocked_keywords = {
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

        print("🔥 RANKING BALANCEADO + AJUSTE FINO CONSERVADOR ATIVO 🔥")

    # ========================================================
    # HELPERS
    # ========================================================

    def _get_enum_value(self, value):
        return getattr(value, "value", value)

    def _is_symbol_blocked(self, symbol: str) -> bool:
        symbol = str(symbol).strip().upper()
        return any(keyword in symbol for keyword in self.blocked_keywords)

    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default

    def _log_non_execution(self, token, reason, summary):

        if not self.lc1e:
            return

        try:
            analysis = token.get("analysis", {}) or {}
            snapshot = token.get("snapshot")
            symbol = str(token.get("symbol") or token.get("pair") or "").strip().upper()

            # ==========================================================
            # CONTEXTO MACRO (se vier acoplado no token)
            # ==========================================================
            market_context = token.get("market_context", {}) or {}

            liquidity_score = self._safe_float(
                market_context.get("liquidity_score", 0.0), 0.0
            )
            liquidity_label = str(market_context.get("liquidity_label", "") or "")
            avg_volume_ratio = self._safe_float(
                market_context.get("avg_volume_ratio", 0.0), 0.0
            )
            uptrend_count = int(market_context.get("uptrend_count", 0) or 0)
            refined_count = int(market_context.get("refined_count", 0) or 0)
            approved_count = int(market_context.get("approved_count", 0) or 0)

            event = self.lc1e.build_event(
                symbol=symbol,
                reason=reason,
                analysis=analysis,
                snapshot=snapshot,
                market_context={
                    "liquidity_score": liquidity_score,
                    "liquidity_label": liquidity_label,
                    "avg_volume_ratio": avg_volume_ratio,
                    "uptrend_count": uptrend_count,
                    "refined_count": refined_count,
                    "approved_count": approved_count,
                },
                event_type="NON_EXECUTION",
                source="market_ranking_engine",
                summary=summary,
            )

            print(f"[ALO PROFILE DEBUG] event_type_python={type(event)}")
            print(f"[ALO PROFILE DEBUG] is_dict={isinstance(event, dict)}")

            print(f"[LC1E RANKING] symbol={symbol} reason={reason}")

            self.lc1e.record_event(event)

            try:
                # 🔥 CONVERSÃO PARA DICT (ESSA É A CHAVE)
                if hasattr(event, "__dict__"):
                    event_dict = dict(event.__dict__)
                else:
                    event_dict = event

                updated_profile = self.alo_profile_updater.update_from_event(event_dict)

                if updated_profile is not None:
                    print(
                        f"[ALO PROFILE] atualizado: "
                        f"{updated_profile.symbol} | "
                        f"block_bias={updated_profile.block_bias:.2f} | "
                        f"non_exec={updated_profile.non_execution_count}"
                    )

            except Exception as e:
                print(f"[ALO PROFILE ERROR] {symbol} erro={e}")

        except Exception as e:
            print(f"[LC1E RANKING ERROR] symbol={token.get('symbol')} erro={e}")

    # ========================================================
    # REFINE
    # ========================================================

    def refine(self, opportunities):

        if not opportunities:
            return []

        # RESET DO SUMMARY POR CICLO
        self._radar_summary_local = {
            "STRUCTURAL_BLOCK": 0,
            "NO_UPTREND": 0,
            "SCORE_BAIXO": 0,
            "QUALITY_FILTER": 0,
            "VOLUME_EXTREMO": 0,
            "RSI_EXTREMO": 0,
        }

        ranked = []

        total_items = len(opportunities) if opportunities else 0

        uptrend_count_real = 0
        avg_volume_ratio_real = 0.0
        refined_count_real = 0
        approved_count_real = 0

        try:
            if total_items > 0:
                uptrend_count_real = sum(
                    1
                    for item in opportunities
                    if self._get_enum_value((item.get("analysis") or {}).get("trend"))
                    == "UPTREND"
                )

                avg_volume_ratio_real = (
                    sum(
                        self._safe_float(
                            (item.get("analysis") or {}).get("volume_ratio", 0.0),
                            0.0,
                        )
                        for item in opportunities
                    )
                    / total_items
                )
        except Exception:
            pass

        base_market_context = {
            "liquidity_score": 0.0,
            "liquidity_label": "",
            "avg_volume_ratio": round(avg_volume_ratio_real, 4),
            "uptrend_count": uptrend_count_real,
            "refined_count": 0,
            "approved_count": 0,
            "total_assets": total_items,
        }

        for token in opportunities:

            try:

                analysis = token.get("analysis", {})
                symbol = token.get("symbol") or token.get("pair") or ""
                symbol = str(symbol).strip().upper()

                if not symbol:
                    continue

                token["symbol"] = symbol

                token["market_context"] = dict(base_market_context)

                # ------------------------------------------------
                # BLOQUEIO ESTRUTURAL DE ATIVOS FRACOS / MEMECOINS
                # ------------------------------------------------
                if self._is_symbol_blocked(symbol):
                    print(f"[RADAR FILTER] {symbol} BLOQUEADO por qualidade estrutural")

                    self._radar_summary_local["STRUCTURAL_BLOCK"] += 1

                    # RADAR SUMMARY FLAG
                    token["_radar_rejection_reason"] = "STRUCTURAL_BLOCK"

                    self._log_non_execution(
                        token,
                        "STRUCTURAL_BLOCK",
                        "STRUCTURAL_REJECTION",
                    )

                    continue

                refined_count_real += 1

                # ------------------------------------------------
                # CAMPOS BASE
                # ------------------------------------------------
                trend = self._get_enum_value(analysis.get("trend"))
                momentum = self._get_enum_value(analysis.get("momentum"))
                market_state = self._get_enum_value(analysis.get("market_state"))
                volume_state = self._get_enum_value(analysis.get("volume"))
                market_score = self._safe_float(analysis.get("market_score", 0), 0.0)

                rsi = self._safe_float(analysis.get("rsi", 50), 50.0)
                volume_ratio = self._safe_float(analysis.get("volume_ratio", 0), 0.0)

                print(
                    "DEBUG RANKING:",
                    symbol,
                    trend,
                    momentum,
                    market_state,
                    rsi,
                    volume_ratio,
                )

                score = 0.0

                # ------------------------------------------------
                # FILTROS DUROS
                # ------------------------------------------------

                # Sobrecompra extrema
                if rsi > 75:
                    print(
                        f"[RADAR FILTER] {symbol} REJEITADO | motivo=RSI_EXTREMO | rsi={rsi:.2f}"
                    )

                    self._radar_summary_local["RSI_EXTREMO"] += 1

                    self._log_non_execution(
                        token,
                        "RSI_EXTREMO",
                        "OVERBOUGHT",
                    )

                    continue

                # Pump / volume anormal excessivo
                if volume_ratio >= 4.0:
                    print(
                        f"[RADAR FILTER] {symbol} REJEITADO | motivo=VOLUME_EXTREMO | "
                        f"volume_ratio={volume_ratio:.2f}"
                    )

                    self._radar_summary_local["VOLUME_EXTREMO"] += 1

                    self._log_non_execution(
                        token,
                        "VOLUME_EXTREMO",
                        "ABNORMAL_VOLUME",
                    )

                    continue

                # ------------------------------------------------
                # TREND OBRIGATÓRIO
                # ------------------------------------------------
                if trend == "UPTREND":
                    score += 0.35
                else:

                    self._radar_summary_local["NO_UPTREND"] += 1

                    self._log_non_execution(
                        token,
                        "NO_UPTREND",
                        "TREND_INVALID",
                    )
                    continue

                # ------------------------------------------------
                # MOMENTUM
                # ------------------------------------------------
                if momentum == "BULLISH":
                    score += 0.25
                elif momentum == "NEUTRAL":
                    score += 0.0
                else:
                    score += 0.0

                # ------------------------------------------------
                # RSI
                # ------------------------------------------------
                if 45 <= rsi <= 60:
                    score += 0.20
                elif 40 <= rsi < 45 or 60 < rsi <= 65:
                    score += 0.10
                elif 65 < rsi <= 72:
                    score += 0.05
                else:
                    score += 0.0

                # ------------------------------------------------
                # VOLUME
                # ------------------------------------------------
                if 1.2 <= volume_ratio < 3.0:
                    score += 0.15
                elif 1.0 <= volume_ratio < 1.2:
                    score += 0.10
                elif 0.6 <= volume_ratio < 1.0:
                    score += 0.05
                elif 0.3 <= volume_ratio < 0.6:
                    score += 0.02
                else:
                    score += 0.0

                # ------------------------------------------------
                # MARKET STATE
                # ------------------------------------------------
                if market_state == "SIDEWAYS":
                    score -= 0.15
                elif market_state in {"BULLISH_WEAK", "BULLISH"}:
                    score += 0.05

                # ------------------------------------------------
                # SCORE FINAL TÉCNICO
                # ------------------------------------------------
                score = max(min(score, 1.0), 0.0)

                if score < 0.30:
                    print(
                        f"[RADAR FILTER] {symbol} REJEITADO | motivo=SCORE_BAIXO | "
                        f"score={score:.4f}"
                    )

                    self._radar_summary_local["SCORE_BAIXO"] += 1

                    self._log_non_execution(
                        token,
                        "SCORE_BAIXO",
                        "LOW_SCORE",
                    )

                    continue

                # ------------------------------------------------
                # FILTRO FINAL DE QUALIDADE
                # Conservador, mas sem matar todo começo de movimento
                # ------------------------------------------------
                quality_ok = False

                # Caminho A — forte/preferencial
                if momentum == "BULLISH":
                    quality_ok = True

                # Caminho B — neutro, mas com confirmação real
                elif momentum == "NEUTRAL":
                    quality_ok = False

                if not quality_ok:
                    print(
                        f"[RADAR FILTER] {symbol} REJEITADO no filtro de qualidade | "
                        f"momentum={momentum} | volume={volume_state} | "
                        f"volume_ratio={volume_ratio:.2f} | rsi={rsi:.2f} | "
                        f"market_score={market_score:.2f}"
                    )

                    self._radar_summary_local["QUALITY_FILTER"] += 1

                    self._log_non_execution(
                        token,
                        "QUALITY_FILTER",
                        "QUALITY_REJECTION",
                    )

                    continue

                # ------------------------------------------------
                # APROVAÇÃO FINAL
                # ------------------------------------------------
                token["score"] = round(score, 4)

                approved_count_real += 1

                # 🔥 ATUALIZA CONTEXTO NO MOMENTO REAL DA APROVAÇÃO
                token["market_context"] = {
                    "liquidity_score": 0.0,
                    "liquidity_label": "",
                    "avg_volume_ratio": round(avg_volume_ratio_real, 4),
                    "uptrend_count": uptrend_count_real,
                    "refined_count": refined_count_real,
                    "approved_count": approved_count_real,
                }

                ranked.append(token)

            except Exception as e:
                print("Ranking error:", e)

        ranked.sort(key=lambda x: x.get("score", 0), reverse=True)

        final_market_snapshot = {
            "liquidity_score": 0.0,
            "liquidity_label": "",
            "avg_volume_ratio": round(avg_volume_ratio_real, 4),
            "uptrend_count": uptrend_count_real,
            "refined_count": refined_count_real,
            "approved_count": approved_count_real,
            "total_assets": total_items,
        }

        for token in ranked:
            try:
                token["market_context"] = dict(final_market_snapshot)
                print(
                    f"[MARKET CONTEXT APPLY] "
                    f"{token.get('symbol')} | "
                    f"refined={final_market_snapshot.get('refined_count', 0)} | "
                    f"approved={final_market_snapshot.get('approved_count', 0)} | "
                    f"uptrend={final_market_snapshot.get('uptrend_count', 0)} | "
                    f"avg_volume_ratio={final_market_snapshot.get('avg_volume_ratio', 0.0)}"
                )
            except Exception as e:
                print(f"[MARKET CONTEXT FINAL ERROR] {e}")

        print(f"[MARKET SNAPSHOT FINAL] {final_market_snapshot}")

        print(
            "[RANKING SUMMARY] "
            f"structural_block={self._radar_summary_local['STRUCTURAL_BLOCK']} | "
            f"no_uptrend={self._radar_summary_local['NO_UPTREND']} | "
            f"score_baixo={self._radar_summary_local['SCORE_BAIXO']} | "
            f"quality_filter={self._radar_summary_local['QUALITY_FILTER']} | "
            f"volume_extremo={self._radar_summary_local['VOLUME_EXTREMO']} | "
            f"rsi_extremo={self._radar_summary_local['RSI_EXTREMO']} | "
            f"approved={len(ranked)} | "
            f"total={total_items}"
        )

        return ranked, final_market_snapshot
