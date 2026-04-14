# ============================================================
# tests/test_exit_service.py
# QA-IA Formal - ExitService v1.0
# ============================================================

from datetime import datetime
from core.trading.exit.exit_service import ExitService
from core.trading.exit.exit_decision import ExitDecision


def test_exit_service_sell_tp():

    service = ExitService()

    position_data = {
        "entry_price": 100.0,
        "current_price": 100.6,
        "quantity": 1.0,
        "entry_timestamp": datetime.utcnow(),
        "highest_price": 100.6,
        "unrealized_pnl_percent": 0.6,
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

    result = service.evaluate(
        symbol="BTCUSDC",
        position_data=position_data,
        indicator_data=indicator_data,
        risk_data=risk_data,
    )

    assert result.decision == ExitDecision.SELL_TP
    assert result.is_exit() is True