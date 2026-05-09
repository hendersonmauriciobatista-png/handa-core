# ============================================================
# core/loop/auto_loop.py
# AutoLoop do sistema H&A
# SAFE COMPAT VERSION
# LOOP PURO — MULTI-SLOT REAL
# ============================================================

import time


class AutoLoop:

    def __init__(self, slot_controller, interval_seconds=5, on_cycle_update=None):
        self.slot_controller = slot_controller
        self.interval = interval_seconds
        self.on_cycle_update = on_cycle_update

        self.running = False

        # métricas usadas pela UI
        self.cycle = 0
        self.last_iter = None
        self.cycle_latency = 0
        self.market_latency = 0
        self.execution_latency = 0
        self.api_latency = 0

    # ---------------------------------------------------------
    # START
    # ---------------------------------------------------------

    def start(self):

        if self.running:
            print("AUTOLOOP já está em execução.")
            return

        print("\n===================================")
        print("   H&A AutoLoop iniciado")
        print("===================================\n")

        self.running = True

        while self.running:

            start_cycle = time.time()

            try:
                self.cycle += 1

                print(f"\n========== CICLO {self.cycle} ==========")

                # -----------------------------------------
                # API LATENCY
                # -----------------------------------------

                if getattr(self.slot_controller, "client", None):
                    try:
                        api_start = time.time()
                        self.slot_controller.client.get_server_time()
                        self.api_latency = int((time.time() - api_start) * 1000)
                    except Exception as e:
                        print("API LATENCY ERROR:", e)
                        self.api_latency = 0

                # -----------------------------------------
                # MARKET PHASE
                # -----------------------------------------

                market_start = time.time()

                self.slot_controller.run_cycle()

                # -----------------------------------------
                # ALO INTELIGENTE (ADVISORY MODE)
                # -----------------------------------------

                try:
                    from core.alo_intelligence.alo_core import ALOIntelligentCore
                    from core.alo_intelligence.alo_models import (
                        ALOMode,
                        TechnicalContext,
                        MacroMarketContext,
                        MemoryContext,
                        TemporalContext,
                    )

                    if not hasattr(self, "_alo_intelligent"):
                        self._alo_intelligent = ALOIntelligentCore(
                            mode=ALOMode.ADVISORY
                        )

                    # 🔥 PEGAR OPPORTUNITIES
                    opportunities = getattr(
                        self.slot_controller, "_last_opportunities", None
                    )

                    if not opportunities:
                        opportunities = getattr(
                            self.slot_controller, "last_opportunities", None
                        )

                    if not opportunities:
                        opportunities = getattr(
                            self.slot_controller, "opportunities", None
                        )

                    if opportunities:

                        # ======================================================
                        # 🔥 MULTI-SLOT DISPATCH REAL
                        # ======================================================

                        # 🔒 CONTAGEM REAL DE SLOTS OCUPADOS
                        slots = getattr(self.slot_controller, "slots", {})

                        occupied_slots = sum(
                            1
                            for s in slots.values()
                            if getattr(s, "state", "")
                            in ("ANALYZING", "READY", "RUNNING")
                        )

                        max_slots = getattr(self.slot_controller, "max_slots", 4)

                        available_slots = max(0, max_slots - occupied_slots)

                        if occupied_slots >= max_slots:
                            print(
                                f"[SLOT LIMIT] bloqueado | occupied={occupied_slots}/{max_slots}"
                            )

                        if available_slots > 0:
                            # ======================================================
                            # 🔒 SYMBOL DUPLICATION PROTECTION
                            # ======================================================

                            active_symbols = set()

                            # posições já abertas
                            try:
                                if hasattr(self.position_manager, "_positions"):
                                    active_symbols.update(
                                        str(sym).upper()
                                        for sym in self.position_manager._positions.keys()
                                    )
                            except Exception:
                                pass

                            # slots já ocupados/analisando
                            try:
                                for s in slots.values():

                                    slot_symbol = str(getattr(s, "symbol", "")).upper()

                                    slot_state = str(getattr(s, "state", "")).upper()

                                    if slot_symbol and slot_state in (
                                        "ANALYZING",
                                        "READY",
                                        "RUNNING",
                                    ):
                                        active_symbols.add(slot_symbol)

                            except Exception:
                                pass

                            filtered_ops = []

                            for op in opportunities:

                                symbol = str(op.get("symbol", "")).upper()

                                if symbol in active_symbols:

                                    print(
                                        f"[SYMBOL LOCK] {symbol} bloqueado "
                                        f"(duplicidade operacional)"
                                    )

                                    continue

                                active_symbols.add(symbol)
                                filtered_ops.append(op)

                            selected_ops = filtered_ops[:available_slots]

                    if opportunities:

                        # ======================================================
                        # 🔥 USAR PRIMEIRO OP PARA CONTEXTO (ALO)
                        # ======================================================

                        top = opportunities[0]

                        snapshot = top.get("snapshot")
                        analysis = top.get("analysis")
                        market_context = top.get("market_context")

                        if snapshot and analysis and market_context:

                            technical = TechnicalContext(
                                price=snapshot.price,
                                rsi=snapshot.rsi_14,
                                ema_fast=snapshot.ema_10,
                                ema_slow=snapshot.ema_20,
                                ema_trend=snapshot.ema_50,
                                volume_ratio=snapshot.volume_ratio,
                                trend=str(analysis.get("trend")),
                                momentum=str(analysis.get("momentum")),
                                market_state=str(analysis.get("market_state")),
                                selection_score=top.get("selection_score", 0.5),
                            )

                            macro = MacroMarketContext(
                                liquidity_score=market_context.get(
                                    "avg_volume_ratio", 0.5
                                ),
                                liquidity_label="AUTO",
                                liquidity_message="",
                                avg_volume_ratio=market_context.get(
                                    "avg_volume_ratio", 1.0
                                ),
                                uptrend_count=market_context.get("uptrend_count", 0),
                                refined_count=market_context.get("refined_count", 0),
                                approved_count=market_context.get("approved_count", 0),
                                total_assets=market_context.get("total_assets", 40),
                            )

                            # ======================================================
                            # 🔥 CONTEXTO DE MEMÓRIA / DRC
                            # ======================================================

                            pair = str(top.get("symbol", "UNKNOWN")).upper()

                            last_symbol = str(
                                getattr(self.slot_controller, "last_traded_symbol", "")
                            ).upper()

                            last_was_loss = getattr(
                                self.slot_controller,
                                "last_trade_was_loss",
                                False,
                            )

                            same_symbol_recent_failures = 0
                            fast_stop_flag = False

                            if pair == last_symbol and last_was_loss:
                                same_symbol_recent_failures = 1
                                fast_stop_flag = True

                            memory = MemoryContext(
                                same_symbol_recent_failures=same_symbol_recent_failures,
                                fast_stop_flag=fast_stop_flag,
                            )

                            temporal = TemporalContext(
                                minutes_since_last_failure=0 if fast_stop_flag else None
                            )

                            guidance = self._alo_intelligent.evaluate(
                                symbol=pair,
                                technical=technical,
                                macro=macro,
                                memory=memory,
                                temporal=temporal,
                            )

                            print(f"[ALO INTEL] {guidance.explainability_text}")

                    else:
                        print("[ALO INTEL] sem opportunities no ciclo")

                except Exception as e:
                    print(f"[ALO INTEL ERROR] {e}")

                self.market_latency = int((time.time() - market_start) * 1000)
                self.execution_latency = self.market_latency

                # -----------------------------------------
                # Atualização de saldo
                # -----------------------------------------

                if self.cycle % 5 == 0:
                    try:
                        executor = getattr(self.slot_controller, "executor", None)
                        if executor:
                            executor.get_balance("USDC")
                    except Exception as e:
                        print("Erro atualização saldo:", e)

                # -----------------------------------------
                # FINALIZAÇÃO
                # -----------------------------------------

                self.last_iter = time.strftime("%H:%M:%S")
                self.cycle_latency = int((time.time() - start_cycle) * 1000)

                # -----------------------------------------
                # Atualização UI
                # -----------------------------------------

                if self.on_cycle_update:
                    try:
                        self.on_cycle_update(
                            {
                                "cycle": self.cycle,
                                "last_iter": self.last_iter,
                                "cycle_latency": self.cycle_latency,
                                "market_latency": self.market_latency,
                                "execution_latency": self.execution_latency,
                                "api_latency": self.api_latency,
                            }
                        )
                    except Exception as e:
                        print("Erro callback UI:", e)

            except Exception as e:
                print("ERRO NO CICLO:", e)

            finally:
                print("AUTOLOOP SLEEP", self.interval)
                time.sleep(self.interval)

    # ---------------------------------------------------------
    # STOP
    # ---------------------------------------------------------

    def stop(self):
        self.running = False
