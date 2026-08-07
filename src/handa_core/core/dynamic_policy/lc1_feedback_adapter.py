# =============================================================================
# core/dynamic_policy/lc1_feedback_adapter.py
# H&A — LC1 Feedback Adapter
# =============================================================================

from core.dynamic_policy.policy_models import LC1Feedback


class LC1FeedbackAdapter:
    """
    Adaptador entre o histórico LC-1 e o DynamicPolicyCore.

    Responsável por transformar dados brutos de trades
    em métricas utilizáveis pela política dinâmica.
    """

    def __init__(self):
        self._memory = {}

    # -------------------------------------------------------------------------
    # REGISTRO
    # -------------------------------------------------------------------------

    def register_trade(
        self,
        pair: str,
        profit_pct: float,
        is_win: bool,
    ):
        pair = str(pair).strip().upper()

        if not pair:
            return

        if pair not in self._memory:
            self._memory[pair] = []

        self._memory[pair].append(
            {
                "profit_pct": float(profit_pct),
                "is_win": bool(is_win),
            }
        )

        # mantém histórico curto e útil
        if len(self._memory[pair]) > 100:
            self._memory[pair] = self._memory[pair][-100:]

    # -------------------------------------------------------------------------
    # FEEDBACK
    # -------------------------------------------------------------------------

    def build_feedback(self, pair: str) -> LC1Feedback:
        pair = str(pair).strip().upper()

        history = self._memory.get(pair, [])

        if not history:
            return LC1Feedback()

        wins = 0
        losses = 0
        total_profit = 0.0
        total_loss = 0.0

        current_loss_streak = 0

        for trade in history:
            profit = float(trade["profit_pct"])
            is_win = bool(trade["is_win"])

            if is_win:
                wins += 1
                total_profit += profit
                current_loss_streak = 0
            else:
                losses += 1
                total_loss += abs(profit)
                current_loss_streak += 1

        total = wins + losses
        win_rate = wins / total if total > 0 else 0.5
        avg_profit = total_profit / wins if wins > 0 else 0.0
        avg_loss = total_loss / losses if losses > 0 else 0.0

        return LC1Feedback(
            pair_win_rate=round(win_rate, 3),
            pair_loss_streak=current_loss_streak,
            avg_profit_pct=round(avg_profit, 5),
            avg_loss_pct=round(avg_loss, 5),
            sample_size=total,
        )

    # -------------------------------------------------------------------------
    # DEBUG
    # -------------------------------------------------------------------------

    def get_pair_history(self, pair: str):
        return self._memory.get(str(pair).strip().upper(), [])