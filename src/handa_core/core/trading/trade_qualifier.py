# ============================================================
# core/trading/trade_qualifier.py
# Trade Qualifier do H&A
# ============================================================


class TradeQualifier:

    @staticmethod
    def is_trade_allowed(snapshot, analysis, score):
        """
        Decide se um ativo pode virar trade.
        """

        trend = analysis["trend"]
        momentum = analysis["momentum"]
        volume = analysis["volume"]

        ema10 = snapshot.ema_10
        ema20 = snapshot.ema_20
        ema50 = snapshot.ema_50
        rsi = snapshot.rsi_14

        # ----------------------------------------------------

        if trend.name != "UPTREND":
            return False

        if not (ema10 > ema20 > ema50):
            return False

        if momentum.name == "BEARISH":
            return False

        if volume.name == "LOW":
            return False

        if score < 3:
            return False

        if rsi >= 65:
            return False

        return True