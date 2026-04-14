# ============================================================
# tests/test_position.py
# QA-IA Formal - Position v1.0
# ============================================================

from datetime import datetime
from core.trading.position.position import Position


def test_position_update_and_snapshot():

    pos = Position(
        symbol="BTCUSDC",
        entry_price=100.0,
        quantity=1.0,
        entry_timestamp=datetime.utcnow(),
        highest_price=100.0,
    )

    # Atualiza preço para cima
    pos.update_price(102.0)

    assert pos.highest_price == 102.0
    assert round(pos.unrealized_pnl_percent, 2) == 2.00

    # Atualiza preço para baixo (não deve alterar highest)
    pos.update_price(101.0)

    assert pos.highest_price == 102.0
    assert round(pos.unrealized_pnl_percent, 2) == 1.00

    # Incrementa tick
    pos.increment_tick()
    assert pos.ticks_in_trade == 1

    snapshot = pos.snapshot(current_price=101.0)

    assert snapshot["entry_price"] == 100.0
    assert snapshot["highest_price"] == 102.0
    assert snapshot["unrealized_pnl_percent"] == 1.0
    assert snapshot["ticks_in_trade"] == 1