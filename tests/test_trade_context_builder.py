# ============================================================
# tests/test_trade_context_builder.py
# QA-IA Formal - TradeContextBuilder v1.0
# ============================================================

from datetime import datetime
from core.trading.context.trade_context_builder import TradeContextBuilder


def test_trade_context_builder_success():

    position_data = {
        "entry_price": 100.0,
        "current_price": 101.0,
        "quantity": 1.0,
        "entry_timestamp": datetime.utcnow(),
        "highest_price": 102.0,
        "unrealized_pnl_percent": 1.0,
        "ticks_in_trade": 10,
    }

    indicator_data = {
        "ema_10": 101.0,
        "ema_20": 100.0,
        "ema_50": 99.0,
        "rsi_14": 60.0,
        "volume_ratio": 1.2,
        "atr_14": 0.5,
    }

    risk_data = {
        "consecutive_losses": 0,
        "daily_drawdown_percent": 0.0,
        "draining_mode_active": False,
    }

    context = TradeContextBuilder.build(
        symbol="BTCUSDC",
        position_data=position_data,
        indicator_data=indicator_data,
        risk_data=risk_data,
    )

    assert context.symbol == "BTCUSDC"
    assert context.entry_price == 100.0
    assert context.current_price == 101.0
    assert context.highest_price == 102.0
    assert context.unrealized_pnl_percent == 1.0
    assert context.ema_10 == 101.0
    assert context.rsi_14 == 60.0
    assert context.consecutive_losses == 0
    assert context.draining_mode_active is False