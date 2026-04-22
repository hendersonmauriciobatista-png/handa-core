# ============================================================
# core/loop/auto_loop.py
# AutoLoop do sistema H&A
# SAFE COMPAT VERSION
# LOOP PURO — SEM SELL PARALELO
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
                    from core.alo_intelligence.alo_models import ALOMode, TechnicalContext, MacroMarketContext

                    if not hasattr(self, "_alo_intelligent"):
                        self._alo_intelligent = ALOIntelligentCore(mode=ALOMode.ADVISORY)

                    # 🔥 PEGAR OPPORTUNITIES REAIS
                    opportunities = getattr(self.slot_controller, "_last_opportunities", None)

                    if not opportunities:
                        opportunities = getattr(self.slot_controller, "last_opportunities", None)

                    if not opportunities:
                        opportunities = getattr(self.slot_controller, "opportunities", None)

                    # 🔥 SE EXISTE OPORTUNIDADE
                    if opportunities:
                        top = opportunities[0]

                        snapshot = top.get("snapshot")
                        analysis = top.get("analysis")
                        market_context = top.get("market_context")

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
                            liquidity_score=market_context.get("avg_volume_ratio", 0.5),
                            liquidity_label="AUTO",
                            liquidity_message="",
                            avg_volume_ratio=market_context.get("avg_volume_ratio", 1.0),
                            uptrend_count=market_context.get("uptrend_count", 0),
                            refined_count=market_context.get("refined_count", 0),
                            approved_count=market_context.get("approved_count", 0),
                            total_assets=market_context.get("total_assets", 40),
                        )

                        guidance = self._alo_intelligent.evaluate(
                            symbol=top.get("symbol", "UNKNOWN"),
                            technical=technical,
                            macro=macro,
                        )

                        print(f"[ALO INTEL] {guidance.explainability_text}")

                    else:
                        print("[ALO INTEL] sem opportunities no ciclo")

                except Exception as e:
                    print(f"[ALO INTEL ERROR] {e}")

                
                self.market_latency = int((time.time() - market_start) * 1000)

                # EXECUTION LATENCY = MARKET (por enquanto)
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
