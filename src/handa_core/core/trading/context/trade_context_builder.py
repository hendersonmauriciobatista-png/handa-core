# ============================================================
# core/trading/context/trade_context_builder.py
# H&A - TradeContextBuilder v1.0
# Política Oficial Operação Autônoma v1.0 (Perfil Moderado)
# ============================================================

from datetime import datetime
from typing import Dict, Any

from core.trading.exit.trade_context import TradeContext


class TradeContextBuilder:
    """
    Responsável por construir o TradeContext a partir
    de dados organizados pelo SlotController.

    Não calcula indicadores.
    Não executa ordens.
    Apenas organiza e valida dados antes de instanciar o TradeContext.
    """

    @staticmethod
    def build(
        symbol: str,
        position_data: Dict[str, Any],
        indicator_data: Dict[str, Any],
        risk_data: Dict[str, Any],
    ) -> TradeContext:

        return TradeContext(
            # --- Identificação ---
            symbol=symbol,
            entry_price=position_data["entry_price"],
            current_price=position_data["current_price"],
            quantity=position_data["quantity"],
            entry_timestamp=position_data["entry_timestamp"],

            # --- Indicadores ---
            ema_10=indicator_data["ema_10"],
            ema_20=indicator_data["ema_20"],
            ema_50=indicator_data["ema_50"],
            rsi_14=indicator_data["rsi_14"],
            volume_ratio=indicator_data["volume_ratio"],
            atr_14=indicator_data["atr_14"],

            # --- Estado da posição ---
            highest_price=position_data["highest_price"],
            unrealized_pnl_percent=position_data["unrealized_pnl_percent"],
            ticks_in_trade=position_data["ticks_in_trade"],

            # --- Risco global ---
            consecutive_losses=risk_data["consecutive_losses"],
            daily_drawdown_percent=risk_data["daily_drawdown_percent"],
            draining_mode_active=risk_data["draining_mode_active"],
        )