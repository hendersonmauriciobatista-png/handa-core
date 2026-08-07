# ============================================================
# core/slot.py
# Slot lógico do H&A
# SAFE COMPAT VERSION
# ============================================================

class Slot:
    """
    Slot lógico do H&A.

    Ciclo:

    IDLE
      ↓
    ANALYZING
      ↓
    READY
      ↓
    RUNNING
      ↓
    DONE
      ↓
    IDLE
    """

    def __init__(self, slot_id: int):

        self.slot_id = slot_id

        # -------------------------------------------------
        # ESTADO
        # -------------------------------------------------

        self._state = "IDLE"

        # -------------------------------------------------
        # ANÁLISE
        # -------------------------------------------------

        self.analysis_strength = None
        self.pair = None

        # -------------------------------------------------
        # DADOS DO TRADE
        # -------------------------------------------------

        self.entry_price = None
        self.exit_price = None
        self.quantity = None

        # -------------------------------------------------
        # CONTROLE INTERNO
        # -------------------------------------------------

        self._analysis_ticks = 0
        self._analysis_required = 6

    # =====================================================
    # PROPRIEDADE DE ESTADO
    # =====================================================

    @property
    def state(self):
        return self._state

    # =====================================================
    # HELPERS
    # =====================================================

    def _clear_runtime_data(self):
        self.analysis_strength = None
        self.pair = None
        self.entry_price = None
        self.exit_price = None
        self.quantity = None
        self._analysis_ticks = 0

    # =====================================================
    # AÇÕES CONTROLADAS
    # =====================================================

    def start_analysis(self):

        if self._state != "IDLE":
            return

        self._state = "ANALYZING"
        self.analysis_strength = None
        self.entry_price = None
        self.exit_price = None
        self.quantity = None
        self._analysis_ticks = 0

    def mark_ready(self):

        if self._state != "ANALYZING":
            return

        self._state = "READY"

    def mark_running(self):

        if self._state != "READY":
            return

        self._state = "RUNNING"

    def mark_done(self):

        if self._state != "RUNNING":
            return

        self._state = "DONE"

    def force_done(self):
        self._state = "DONE"

    def reset(self):
        """
        Reset seguro e amplo.
        Pode ser usado tanto após DONE quanto em erros operacionais.
        """
        self._state = "IDLE"
        self._clear_runtime_data()

    def abort(self):
        """
        Abort explícito para falhas operacionais.
        """
        self.reset()

    # =====================================================
    # CICLO
    # =====================================================

    def tick(self):

        # -------------------------------------------------
        # ANALYZING
        # -------------------------------------------------

        if self._state == "ANALYZING":

            self._analysis_ticks += 1

            if self._analysis_ticks >= self._analysis_required:
                self._finish_analysis()

        # -------------------------------------------------
        # READY → RUNNING
        # -------------------------------------------------

        elif self._state == "READY":
            self.mark_running()

        # -------------------------------------------------
        # RUNNING
        # -------------------------------------------------

        elif self._state == "RUNNING":
            # agora quem decide o fim do trade
            # é o SlotController / PositionManager
            pass

        # -------------------------------------------------
        # DONE → IDLE
        # -------------------------------------------------

        elif self._state == "DONE":
            self.reset()

    # =====================================================
    # FINALIZA ANÁLISE
    # =====================================================

    def _finish_analysis(self):

        self.analysis_strength = 90  # força READY para teste

        # não força pair artificialmente;
        # quem define isso é o SlotController / radar
        if not self.pair:
            self._state = "IDLE"
            return

        self._state = "READY"

    # =====================================================
    # SNAPSHOT
    # =====================================================

    def snapshot(self):

        return {
            "slot_id": self.slot_id,
            "analysis_state": self._state,
            "analysis_strength": self.analysis_strength,
            "pair": self.pair,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
        }