# ============================================================
# core/auto_loop.py
# AutoLoop do sistema H&A
# ============================================================

import time
import threading




class AutoLoop:

    def __init__(self, slot_controller, interval=4.0):

        self.slot_controller = slot_controller
        self.interval = interval
        
        self.running = False
        self.cycle = 0
        self.last_iter = None
        self.cycle_latency = 0
        self.market_latency = 0
        self.execution_latency = 0
        # -----------------------------------------------------
        # Inicializa UI conectada ao SlotController
        # -----------------------------------------------------

       
    # ---------------------------------------------------------

    def start(self):

        if self.running:
            print("[AutoLoop] já está rodando")
            return

        print("\n===================================")
        print("   H&A AutoLoop iniciado")
        print("===================================\n")

        self.running = True

        while self.running:

            start_time = time.time()

            try:

                self.cycle += 1
                self.last_iter = time.strftime("%H:%M:%S")

               
                print(f"\n========== CICLO {self.cycle} ==========")

                active_positions = self.slot_controller.get_active_positions()

                print(f"Posições ativas: {active_positions}")

                # executa ciclo do SlotController

                market_start = time.time()

                self.slot_controller.run_cycle()

                self.market_latency = int((time.time() - market_start) * 1000)

                exec_start = time.time()

                # execução simulada (por enquanto)
                self.execution_latency = int((time.time() - exec_start) * 1000)
                
                print(f"Hora: {self.last_iter}")
                print(f"Latência ciclo: {self.cycle_latency} ms")
                print(f"Latência mercado: {self.market_latency} ms")
                print(f"Latência execução: {self.execution_latency} ms")

            except Exception as e:

                print("[AutoLoop] erro no ciclo:", e)

            self.cycle_latency = int((time.time() - start_time) * 1000)

            elapsed = time.time() - start_time
            sleep_time = max(0, self.interval - elapsed)

            time.sleep(sleep_time)
    # ---------------------------------------------------------

    def stop(self):

        print("\n[AutoLoop] parada solicitada")

        self.running = False