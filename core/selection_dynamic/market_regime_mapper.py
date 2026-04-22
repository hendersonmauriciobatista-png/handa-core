# =============================================================================
# core/selection_dynamic/market_regime_mapper.py
# H&A — Market Regime Mapper (Selection Dynamic)
# =============================================================================

from core.selection_dynamic.policy_modes import SelectionPolicyMode


class MarketRegimeMapper:
    """
    Responsável por traduzir o estado do mercado (MQII + Liquidez)
    em um modo de operação da Selection Policy.
    """

    def map_mode(self, market_data: dict) -> SelectionPolicyMode:
        """
        Espera receber um dict com:
        {
            "mqii_state": str,
            "liquidity_score": float,
            "approved_count": int,
            "uptrend_count": int,
            "avg_volume_ratio": float
        }
        """

        mqii_state = str(market_data.get("mqii_state", "")).upper()
        liquidity = float(market_data.get("liquidity_score", 0.0))
        approved = int(market_data.get("approved_count", 0))
        uptrend = int(market_data.get("uptrend_count", 0))
        avg_vol = float(market_data.get("avg_volume_ratio", 0.0))

        # ======================================================
        # 🔴 DEFENSIVE — mercado ruim / instável
        # ======================================================
        if (
            mqii_state in {"NO_TRADE", "FRACO"}
            or liquidity < 0.45
            or approved == 0
        ):
            return SelectionPolicyMode.DEFENSIVE

        # ======================================================
        # 🟡 BALANCED — mercado ok, mas sem força total
        # ======================================================
        if (
            mqii_state in {"CAUTIOUS", "MODERADO"}
            or approved == 1
            or avg_vol < 0.9
        ):
            return SelectionPolicyMode.BALANCED

        # ======================================================
        # 🟢 OPPORTUNITY — mercado saudável / operável
        # ======================================================
        if (
            mqii_state in {"TRADE_OK", "FORTE", "AGGRESSIVE_OK"}
            and approved >= 2
            and uptrend >= 10
            and liquidity >= 0.55
        ):
            return SelectionPolicyMode.OPPORTUNITY

        # fallback seguro
        return SelectionPolicyMode.BALANCED