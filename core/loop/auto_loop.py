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
                # ALO SUMMARY
                # -----------------------------------------

                try:
                    alo = getattr(self.slot_controller, "alo", None)

                    if alo:
                        summary = alo.get_learning_summary()

                        print(
                            f"[ALO] symbols={summary['total_symbols']} | "
                            f"approved={summary['approved_symbols']} | "
                            f"learning={summary['learning_symbols']} | "
                            f"blocked={summary['blocked_symbols']}"
                        )

                        for item in summary.get("top_symbols", [])[:3]:
                            print(
                                f"[ALO TOP] {item['symbol']} | "
                                f"score={item['confidence_score']:.2f} | "
                                f"attempts={item['attempts']} | "
                                f"status={item['status']}"
                            )

                except Exception as e:
                    print(f"[ALO ERROR] {e}")

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
                # ALO VISION (READ-ONLY OBSERVER)
                # -----------------------------------------

                try:
                    from core.alo import AloVisionEngine

                    if not hasattr(self, "_alo_vision"):
                        self._alo_vision = AloVisionEngine()

                    # snapshot atual (se existir)
                    snapshot = getattr(self.slot_controller, "last_snapshot", None)

                    # liquidez da UI / radar (se existir)
                    liquidity_data = getattr(
                        self.slot_controller, "market_liquidity", None
                    )

                    vision = self._alo_vision.analyze(
                        snapshot=snapshot,
                        liquidity_data=liquidity_data,
                    )

                    v = vision.inference

                    if getattr(vision, "extra", {}).get("loggable", False):
                        print(
                            f"[ALO VISION] {vision.symbol} | "
                            f"conf={v.confidence_label} | "
                            f"guide={v.guidance} | "
                            f"outcome={v.expected_outcome}"
                        )

                except Exception as e:
                    print(f"[ALO VISION ERROR] {e}")

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
