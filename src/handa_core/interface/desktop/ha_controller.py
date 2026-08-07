# ============================================================
# interface/desktop/ha_controller.py
# H&A — Desktop Controller Layer
# ============================================================

import threading


class HAController:

    def __init__(
        self,
        auto_loop,
        slot_controller,
        executor=None,
        position_manager=None,
    ):
        self.auto_loop = auto_loop
        self.slot_controller = slot_controller
        self.executor = executor
        self.position_manager = position_manager

        self._locked = False
        self._thread = None

        print("[HAController] inicializado")

    # ========================================================
    # START
    # ========================================================

    def start(self):
        if self._locked:
            print("[HAController] START bloqueado (LOCK ativo)")
            return

        if self.auto_loop.running:
            print("[HAController] AutoLoop já está rodando")
            return

        print("[HAController] START")

        self._thread = threading.Thread(
            target=self.auto_loop.start,
            daemon=True,
        )
        self._thread.start()

    # ========================================================
    # DRAIN
    # ========================================================

    def drain(self):
        print("[HAController] DRAIN")

        if self.auto_loop:
            self.auto_loop.stop()

    # ========================================================
    # RESET
    # ========================================================

    def reset(self):
        print("[HAController] RESET")

        try:
            if self.auto_loop:
                self.auto_loop.stop()

            if self.slot_controller:
                for slot in self.slot_controller.get_slots().values():
                    slot.reset()

            if self.position_manager:
                self.position_manager.reset()

        except Exception as e:
            print(f"[HAController] RESET ERROR: {e}")

    # ========================================================
    # LOCK / UNLOCK
    # ========================================================

    def lock(self):
        print("[HAController] LOCK")
        self._locked = True

    def unlock(self):
        print("[HAController] UNLOCK")
        self._locked = False

    def get_balance(self, asset="USDC"):
        try:
            if self.executor and hasattr(self.executor, "get_balance"):
                return float(self.executor.get_balance(asset))
        except Exception as e:
            print(f"[HAController] BALANCE ERROR: {e}")

        return 0.0

    def get_trade_history(self):
        if self.position_manager:
            return self.position_manager.get_history()
        return []

    # ========================================================
    # HELPERS
    # ========================================================

    def get_slots(self):
        if self.slot_controller:
            return self.slot_controller.get_slots()
        return {}