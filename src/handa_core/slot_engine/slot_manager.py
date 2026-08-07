"""
SlotManager
Responsável por gerenciar os ciclos dos slots de trading.

Regras:
- Só executa quando sistema está RUNNING
- DRAINING interrompe novos ciclos
"""

class SlotManager:

    def __init__(self):
        self._active = False

    # ==================================
    # CONTROLE
    # ==================================

    def start(self):
        self._active = True
        print("[SlotManager] STARTED")

    def stop(self):
        self._active = False
        print("[SlotManager] STOPPED")

    def drain(self):
        self._active = False
        print("[SlotManager] DRAINING...")

    # ==================================
    # CICLO
    # ==================================

    def tick(self):
        if not self._active:
            return

        print("[SlotManager] Running cycle...")
