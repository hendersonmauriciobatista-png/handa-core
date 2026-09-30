"""Expected-RED falsifiers for the frozen Position Effect Authority contract.

The future authority boundary is intentionally absent at this stage.  These
tests name the minimum conceptual API without implementing it in fixtures.
"""

from importlib import import_module

import pytest


def _authority():
    """Load the future authority boundary; absence is the expected RED."""
    module = import_module("core.position.position_effect_authority")
    authority_type = getattr(module, "PositionEffectAuthority")
    return authority_type()


def _receipt(quantity=1, *, order_id="order-1"):
    return {
        "exchange": "TEST_EXCHANGE",
        "order_id": order_id,
        "client_order_id": f"client-{order_id}",
        "executed_base_qty": quantity,
        "executed_quote_qty": 100,
        "weighted_price": 100,
        "status": "FILLED",
        "fills": [{"trade_id": f"trade-{order_id}", "quantity": quantity}],
        "timestamp": "2026-01-01T00:00:00Z",
        "normalization_version": "1",
    }


def _authority_binding(**overrides):
    binding = {
        "intent_id": "intent-1",
        "reconciliation_context_id": "context-1",
        "semantic_decision_id": "decision-1",
        "decision_sequence": 1,
        "authority_contract_version": "3B4-position-v1",
        "effect_request_id": "effect-1",
    }
    binding.update(overrides)
    return binding


def test_pe001_partial_sell_cannot_full_close():
    authority = _authority()
    position = authority.apply_open(
        position_id="position-1", intended_quantity=10, receipt=_receipt(10), **_authority_binding()
    )
    result = authority.apply_reduction(
        position_id=position.position_id,
        applied_quantity=4,
        receipt=_receipt(4, order_id="sell-1"),
        **_authority_binding(effect_request_id="effect-2"),
    )
    assert result.status != "CLOSED"


def test_pe002_residual_quantity_is_preserved():
    authority = _authority()
    position = authority.apply_open(
        position_id="position-1", intended_quantity=10, receipt=_receipt(10), **_authority_binding()
    )
    reduced = authority.apply_reduction(
        position_id=position.position_id,
        applied_quantity=4,
        receipt=_receipt(4, order_id="sell-1"),
        **_authority_binding(effect_request_id="effect-2"),
    )
    assert reduced.residual_quantity == 6


def test_pe003_same_external_extent_cannot_be_applied_twice():
    authority = _authority()
    authority.apply_open(
        position_id="position-1",
        intended_quantity=10,
        receipt=_receipt(10, order_id="buy-1"),
        **_authority_binding(effect_request_id="effect-open"),
    )
    receipt = _receipt(4, order_id="sell-1")
    authority.apply_reduction(
        position_id="position-1",
        applied_quantity=4,
        receipt=receipt,
        **_authority_binding(effect_request_id="effect-reduce-1"),
    )
    with pytest.raises(Exception):
        authority.apply_reduction(
            position_id="position-1",
            applied_quantity=4,
            receipt=receipt,
            **_authority_binding(effect_request_id="effect-reduce-2"),
        )


def test_pe004_wrong_position_identity_is_rejected():
    authority = _authority()
    with pytest.raises(Exception):
        authority.apply_reduction(
            position_id="position-b", applied_quantity=1, receipt=_receipt(1), **_authority_binding()
        )


def test_pe005_stale_semantic_decision_is_rejected():
    authority = _authority()
    with pytest.raises(Exception):
        authority.apply_open(
            position_id="position-1",
            intended_quantity=1,
            receipt=_receipt(1),
            **_authority_binding(decision_sequence=0),
        )


def test_pe006_later_contradiction_blocks_application():
    authority = _authority()
    with pytest.raises(Exception):
        authority.apply_open(
            position_id="position-1",
            intended_quantity=1,
            receipt=_receipt(1),
            contradiction_state="PRESENT",
            **_authority_binding(),
        )


def test_pe007_reduction_greater_than_residual_is_rejected():
    authority = _authority()
    with pytest.raises(Exception):
        authority.apply_reduction(
            position_id="position-1", applied_quantity=11, receipt=_receipt(11), **_authority_binding()
        )


def test_pe008_zero_extent_is_rejected():
    authority = _authority()
    with pytest.raises(Exception):
        authority.apply_reduction(
            position_id="position-1", applied_quantity=0, receipt=_receipt(0), **_authority_binding()
        )


def test_pe009_negative_extent_is_rejected():
    authority = _authority()
    with pytest.raises(Exception):
        authority.apply_reduction(
            position_id="position-1", applied_quantity=-1, receipt=_receipt(-1), **_authority_binding()
        )


def test_pe010_unknown_extent_is_rejected():
    authority = _authority()
    with pytest.raises(Exception):
        authority.apply_reduction(
            position_id="position-1", applied_quantity=None, receipt=_receipt(None), **_authority_binding()
        )


def test_pe011_unknown_outcome_cannot_close():
    authority = _authority()
    with pytest.raises(Exception):
        authority.apply_close(
            position_id="position-1",
            receipt={"status": "UNKNOWN", "executed_base_qty": None},
            outcome="OUTCOME_UNKNOWN",
            **_authority_binding(),
        )


def test_pe012_open_uses_actual_executed_quantity():
    authority = _authority()
    position = authority.apply_open(
        position_id="position-1", intended_quantity=10, receipt=_receipt(3), **_authority_binding()
    )
    assert position.quantity == 3


def test_pe013_multiple_reductions_preserve_identity_and_residual():
    authority = _authority()
    position = authority.apply_open(
        position_id="position-1", intended_quantity=10, receipt=_receipt(10), **_authority_binding()
    )
    first = authority.apply_reduction(
        position_id=position.position_id,
        applied_quantity=3,
        receipt=_receipt(3, order_id="sell-1"),
        **_authority_binding(effect_request_id="effect-2"),
    )
    second = authority.apply_reduction(
        position_id=position.position_id,
        applied_quantity=2,
        receipt=_receipt(2, order_id="sell-2"),
        **_authority_binding(effect_request_id="effect-3"),
    )
    assert second.position_id == first.position_id == position.position_id
    assert second.residual_quantity == 5


def test_pe014_close_requires_zero_residual():
    authority = _authority()
    with pytest.raises(Exception):
        authority.apply_close(
            position_id="position-1", receipt=_receipt(4), **_authority_binding()
        )


def test_pe015_effect_request_identity_is_idempotent():
    authority = _authority()
    first = authority.apply_open(
        position_id="position-1", intended_quantity=1, receipt=_receipt(1), **_authority_binding()
    )
    second = authority.apply_open(
        position_id="position-1", intended_quantity=1, receipt=_receipt(1), **_authority_binding()
    )
    assert second.position_id == first.position_id
    assert len(authority.get_position_history("position-1")) == 1


def test_pe016_receipt_identity_is_bound_to_position_mutation():
    authority = _authority()
    with pytest.raises(Exception):
        authority.apply_open(
            position_id="position-1",
            intended_quantity=1,
            receipt=_receipt(1, order_id="unbound-order"),
            external_order_id="different-order",
            **_authority_binding(),
        )


def test_pe017_ambiguous_local_mutation_remains_outcome_unknown():
    authority = _authority()
    result = authority.reconcile_local_mutation(
        effect_request_id="effect-1", mutation_status="UNKNOWN", evidence=[]
    )
    assert result.state == "OUTCOME_UNKNOWN"


def test_pe018_same_symbol_cannot_merge_distinct_positions():
    authority = _authority()
    first = authority.apply_open(
        position_id="position-1", symbol="BTCUSDC", intended_quantity=1,
        receipt=_receipt(1, order_id="buy-1"), **_authority_binding()
    )
    second = authority.apply_open(
        position_id="position-2", symbol="BTCUSDC", intended_quantity=2,
        receipt=_receipt(2, order_id="buy-2"),
        **_authority_binding(effect_request_id="effect-2", intent_id="intent-2"),
    )
    assert first.position_id != second.position_id
