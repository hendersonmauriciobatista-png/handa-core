from decimal import Decimal

import pytest

from core.position.position_effect_authority import (
    PositionEffectAuthority,
    PositionEffectError,
)


def receipt(quantity, order_id):
    return {
        "order_id": order_id,
        "executed_base_qty": quantity,
        "executed_quote_qty": Decimal("100"),
        "weighted_price": Decimal("100"),
        "status": "FILLED",
        "fills": [{"trade_id": f"trade-{order_id}", "quantity": quantity}],
    }


def binding(effect_request_id):
    return {
        "intent_id": "intent-1",
        "symbol": "BTCUSDC",
        "effect_request_id": effect_request_id,
    }


def opened(authority):
    return authority.apply_open(
        position_id="position-1",
        intended_quantity=Decimal("10"),
        receipt=receipt(10, "buy-1"),
        **binding("effect-open"),
    )


def test_open_uses_actual_quantity_and_creates_distinct_identity():
    authority = PositionEffectAuthority()
    result = authority.apply_open(
        position_id="position-1",
        intended_quantity=Decimal("10"),
        receipt=receipt(3, "buy-1"),
        **binding("effect-open"),
    )
    assert result.resulting_quantity == Decimal("3")
    assert authority.get_position("position-1").state == "ACTIVE"


def test_reduce_preserves_residual_and_position_identity():
    authority = PositionEffectAuthority()
    opened(authority)
    result = authority.apply_reduction(
        position_id="position-1",
        applied_quantity=4,
        receipt=receipt(4, "sell-1"),
        **binding("effect-reduce"),
    )
    assert result.position_id == "position-1"
    assert result.resulting_quantity == Decimal("6")


def test_close_requires_full_residual_and_is_terminal():
    authority = PositionEffectAuthority()
    opened(authority)
    with pytest.raises(PositionEffectError):
        authority.apply_close(
            position_id="position-1",
            receipt=receipt(4, "sell-1"),
            **binding("effect-close-invalid"),
        )
    result = authority.apply_close(
        position_id="position-1",
        receipt=receipt(10, "sell-2"),
        **binding("effect-close"),
    )
    assert result.state == "CLOSED"
    assert authority.get_position("position-1").quantity == Decimal("0")


def test_extent_and_request_idempotency_are_independent():
    authority = PositionEffectAuthority()
    first = opened(authority)
    assert authority.apply_open(
        position_id="position-1",
        intended_quantity=10,
        receipt=receipt(10, "buy-1"),
        **binding("effect-open"),
    ) == first
    with pytest.raises(PositionEffectError):
        authority.apply_reduction(
            position_id="position-1",
            applied_quantity=2,
            receipt=receipt(10, "buy-1"),
            **binding("effect-reduce"),
        )


def test_wrong_position_identity_is_rejected_after_valid_open():
    authority = PositionEffectAuthority()
    opened(authority)
    with pytest.raises(PositionEffectError):
        authority.apply_reduction(
            position_id="position-unknown",
            applied_quantity=1,
            receipt=receipt(1, "sell-unknown"),
            **binding("effect-wrong-position"),
        )


@pytest.mark.parametrize("quantity", [Decimal("0"), Decimal("-1"), None])
def test_invalid_reduction_extent_is_rejected_after_valid_open(quantity):
    authority = PositionEffectAuthority()
    opened(authority)
    with pytest.raises(PositionEffectError):
        authority.apply_reduction(
            position_id="position-1",
            applied_quantity=quantity,
            receipt=receipt(quantity, f"sell-invalid-{quantity}"),
            **binding(f"effect-invalid-{quantity}"),
        )


def test_reduction_greater_than_residual_is_rejected_after_valid_open():
    authority = PositionEffectAuthority()
    opened(authority)
    with pytest.raises(PositionEffectError):
        authority.apply_reduction(
            position_id="position-1",
            applied_quantity=11,
            receipt=receipt(11, "sell-too-large"),
            **binding("effect-too-large"),
        )


def test_multiple_reductions_preserve_identity_and_residual():
    authority = PositionEffectAuthority()
    opened(authority)
    first = authority.apply_reduction(
        position_id="position-1", applied_quantity=3,
        receipt=receipt(3, "sell-1"), **binding("effect-reduce-1")
    )
    second = authority.apply_reduction(
        position_id="position-1", applied_quantity=2,
        receipt=receipt(2, "sell-2"), **binding("effect-reduce-2")
    )
    assert second.position_id == first.position_id
    assert second.resulting_quantity == Decimal("5")


def test_unknown_outcome_cannot_close():
    authority = PositionEffectAuthority()
    opened(authority)
    with pytest.raises(PositionEffectError):
        authority.apply_close(
            position_id="position-1",
            receipt={"status": "UNKNOWN", "executed_base_qty": None},
            outcome="OUTCOME_UNKNOWN",
            **binding("effect-close"),
        )
