# ============================================================
# tests/test_exit_engine.py
# QA-IA Formal - ExitEngine v1.0
# Política Oficial Operação Autônoma v1.0 (Perfil Moderado)
# ============================================================

from datetime import datetime
from core.trading.exit.trade_context import TradeContext
from core.trading.exit.exit_engine import ExitEngine
from core.trading.exit.exit_decision import ExitDecision


def build_base_context(**overrides):
    base = dict(
        symbol="BTCUSDC",
        entry_price=100.0,
        current_price=100.0,
        quantity=1.0,
        entry_timestamp=datetime.utcnow(),

        ema_10=101,
        ema_20=100,
        ema_50=99,
        rsi_14=55,
        volume_ratio=1.2,
        atr_14=0.5,

        highest_price=100.0,
        unrealized_pnl_percent=0.0,
        ticks_in_trade=5,

        consecutive_losses=0,
        daily_drawdown_percent=0.0,
        draining_mode_active=False,
    )

    base.update(overrides)
    return TradeContext(**base)


def test_sell_sl():
    engine = ExitEngine()
    context = build_base_context(
        current_price=99.5,
        unrealized_pnl_percent=-0.5
    )

    result = engine.evaluate(context)
    assert result.decision == ExitDecision.SELL_SL


def test_sell_tp():
    engine = ExitEngine()
    context = build_base_context(
        current_price=100.6,
        highest_price=100.6,
        unrealized_pnl_percent=0.6
    )

    result = engine.evaluate(context)
    assert result.decision == ExitDecision.SELL_TP


def test_sell_trailing():
    engine = ExitEngine()
    context = build_base_context(
        current_price=101.2,
        highest_price=102.0,
        atr_14=0.8,
        unrealized_pnl_percent=1.2
    )

    result = engine.evaluate(context)
    assert result.decision == ExitDecision.SELL_TRAILING


def test_sell_reversal():
    engine = ExitEngine()
    context = build_base_context(
        current_price=100.2,
        highest_price=100.3,
        unrealized_pnl_percent=0.2,
        ema_10=99,
        ema_20=100,
        rsi_14=40,
        volume_ratio=0.8
    )

    result = engine.evaluate(context)
    assert result.decision == ExitDecision.SELL_REVERSAL


def test_block_risk():
    engine = ExitEngine()
    context = build_base_context(
        unrealized_pnl_percent=1.0,
        consecutive_losses=3
    )

    result = engine.evaluate(context)
    assert result.decision == ExitDecision.BLOCK_RISK


def test_hold():
    engine = ExitEngine()
    context = build_base_context(
        current_price=100.1,
        highest_price=100.2,
        unrealized_pnl_percent=0.1
    )

    result = engine.evaluate(context)
    assert result.decision == ExitDecision.HOLD