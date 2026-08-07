# ============================================================
# core/exit/exit_manager.py
# Gerenciamento de saída de posições
# ============================================================


class ExitManager:

    def __init__(self):

        # -----------------------------------------------------
        # POLÍTICA OFICIAL H&A
        # -----------------------------------------------------

        # Take Profit: +0.45%
        self.take_profit = 0.45

        # Stop Loss: -0.35%
        self.stop_loss = -0.35

    # ---------------------------------------------------------
    # Verificar se deve sair da posição
    # ---------------------------------------------------------

    def should_exit(self, pnl_percent):

        # -----------------------------------------------------
        # TAKE PROFIT
        # -----------------------------------------------------

        if pnl_percent >= self.take_profit:
            return True, "TAKE_PROFIT"

        # -----------------------------------------------------
        # STOP LOSS
        # -----------------------------------------------------

        if pnl_percent <= self.stop_loss:
            return True, "STOP_LOSS"

        # -----------------------------------------------------
        # CONTINUAR NA POSIÇÃO
        # -----------------------------------------------------

        return False, None