"""Falsification contract for the future evidence sufficiency policy.

These tests deliberately target a pure execution-layer contract.  They do not
implement policy rules, persistence, reconciliation, or position effects.
"""

from copy import deepcopy

import pytest

from core.execution.evidence_sufficiency_policy import EvidenceSufficiencyPolicy


def intent(*, intent_id="intent-1", client_order_id="client-1"):
    return {
        "intent_id": intent_id,
        "client_order_id": client_order_id,
        "symbol": "BTCUSDC",
    }


def observation(
    *,
    ref="obs-1",
    intent_id="intent-1",
    client_order_id="client-1",
    status="NEW",
    executed_qty=None,
    exchange_order_id="order-1",
):
    return {
        "evidence_ref": ref,
        "intent_id": intent_id,
        "symbol": "BTCUSDC",
        "exchange_order_id": exchange_order_id,
        "client_order_id_observed": client_order_id,
        "external_order_status": status,
        "executed_qty": executed_qty,
    }


def trade(*, ref="trade-1", intent_id="intent-1", qty="0.1000"):
    return {
        "trade_effect_ref": ref,
        "intent_id": intent_id,
        "symbol": "BTCUSDC",
        "exchange_order_id": "order-1",
        "exchange_trade_id": "exchange-trade-1",
        "trade_qty": qty,
    }


def evaluate(
    proposition,
    *,
    order_intent=None,
    external_observations=(),
    trade_effects=(),
    normalized_evidence=(),
):
    return EvidenceSufficiencyPolicy.evaluate(
        proposition=proposition,
        intent=order_intent or intent(),
        external_observations=external_observations,
        trade_effects=trade_effects,
        normalized_evidence=normalized_evidence,
    )


def test_no_evidence_is_insufficient_for_any_execution():
    result = evaluate("ANY_EXECUTION")
    assert result.classification == "INSUFFICIENT"


def test_ambiguous_transport_is_insufficient_for_any_execution():
    result = evaluate(
        "ANY_EXECUTION",
        normalized_evidence=[{"revision_id": "rev-1", "status": "UNKNOWN"}],
    )
    assert result.classification == "INSUFFICIENT"


def test_positive_trade_with_lineage_is_sufficient_for_any_execution():
    result = evaluate("ANY_EXECUTION", trade_effects=[trade()])
    assert result.classification == "SUFFICIENT"
    assert result.supporting_evidence_refs == ["trade-1"]


def test_positive_executed_quantity_is_sufficient_for_any_execution():
    result = evaluate(
        "ANY_EXECUTION",
        external_observations=[observation(status="NEW", executed_qty="0.001")],
    )
    assert result.classification == "SUFFICIENT"
    assert result.supporting_evidence_refs == ["obs-1"]


@pytest.mark.parametrize("status", ["PARTIALLY_FILLED", "FILLED"])
def test_positive_external_status_can_support_any_execution(status):
    result = evaluate(
        "ANY_EXECUTION",
        external_observations=[observation(status=status)],
    )
    assert result.classification == "SUFFICIENT"


def test_normalized_filled_without_external_support_is_insufficient():
    result = evaluate(
        "ANY_EXECUTION",
        normalized_evidence=[{"revision_id": "rev-1", "status": "FILLED"}],
    )
    assert result.classification == "INSUFFICIENT"


@pytest.mark.parametrize(
    "evidence",
    [(), (trade(),)],
)
def test_no_external_effect_never_claims_sufficiency_from_absence(evidence):
    result = evaluate("NO_EXTERNAL_EFFECT", trade_effects=evidence)
    assert result.classification == "INSUFFICIENT"


def test_full_execution_is_insufficient_without_completeness_basis():
    result = evaluate(
        "FULL_EXECUTION",
        external_observations=[observation(status="FILLED", executed_qty="0.001")],
    )
    assert result.classification == "INSUFFICIENT"


def test_partial_execution_is_insufficient_when_trade_does_not_prove_extent():
    result = evaluate("PARTIAL_EXECUTION", trade_effects=[trade()])
    assert result.classification == "INSUFFICIENT"


def test_explicit_partial_order_can_support_partial_execution():
    result = evaluate(
        "PARTIAL_EXECUTION",
        external_observations=[
            observation(status="PARTIALLY_FILLED", executed_qty="0.001")
        ],
    )
    assert result.classification == "SUFFICIENT"


def test_matching_client_identity_is_sufficient():
    result = evaluate(
        "IDENTITY_MATCH",
        external_observations=[observation(client_order_id="client-1")],
    )
    assert result.classification == "SUFFICIENT"


def test_missing_observed_client_identity_is_not_a_match():
    result = evaluate(
        "IDENTITY_MATCH",
        external_observations=[observation(client_order_id=None)],
    )
    assert result.classification == "INSUFFICIENT"


def test_explicit_client_identity_mismatch_is_sufficient_contradiction():
    result = evaluate(
        "IDENTITY_CONTRADICTION",
        external_observations=[observation(client_order_id="other-client")],
    )
    assert result.classification == "SUFFICIENT"
    assert result.contradiction_refs == ["obs-1"]


def test_client_mismatch_is_not_erased_by_matching_exchange_order_id():
    result = evaluate(
        "IDENTITY_MATCH",
        external_observations=[
            observation(client_order_id="other-client", exchange_order_id="order-1")
        ],
    )
    assert result.classification == "INSUFFICIENT"


def test_cross_intent_evidence_cannot_satisfy_the_current_intent():
    result = evaluate(
        "ANY_EXECUTION",
        external_observations=[observation(intent_id="other-intent")],
        trade_effects=[trade(intent_id="other-intent")],
    )
    assert result.classification == "INSUFFICIENT"


def test_incompatible_sources_are_contradictory_and_lineaged():
    result = evaluate(
        "ANY_EXECUTION",
        external_observations=[observation(ref="obs-1", status="FILLED")],
        trade_effects=[trade(ref="trade-1", qty="0")],
    )
    assert result.classification == "CONTRADICTORY"
    assert result.contradiction_refs == ["obs-1", "trade-1"]


def test_compatible_repeated_observations_preserve_lineage_without_contradiction():
    result = evaluate(
        "ANY_EXECUTION",
        external_observations=[
            observation(ref="obs-1", status="PARTIALLY_FILLED", executed_qty="0.001"),
            observation(ref="obs-2", status="PARTIALLY_FILLED", executed_qty="0.001"),
        ],
    )
    assert result.classification == "SUFFICIENT"
    assert result.supporting_evidence_refs == ["obs-1", "obs-2"]
    assert result.contradiction_refs == []


def test_time_or_cycle_metadata_alone_does_not_change_classification():
    result = evaluate(
        "ANY_EXECUTION",
        normalized_evidence=[
            {"revision_id": "rev-1", "status": "UNKNOWN", "observed_at": "t1"},
            {"revision_id": "rev-2", "status": "UNKNOWN", "observed_at": "t2"},
        ],
    )
    assert result.classification == "INSUFFICIENT"


def test_identical_immutable_input_produces_identical_result():
    evidence = [observation(status="PARTIALLY_FILLED", executed_qty="0.001")]
    before = deepcopy(evidence)
    first = evaluate("ANY_EXECUTION", external_observations=evidence)
    second = evaluate("ANY_EXECUTION", external_observations=evidence)
    assert first == second
    assert evidence == before


def test_sufficient_result_contains_exact_lineage_and_reason():
    result = evaluate("ANY_EXECUTION", trade_effects=[trade()])
    assert result.supporting_evidence_refs == ["trade-1"]
    assert result.supporting_normalized_revision_ids == []
    assert result.contradiction_refs == []
    assert isinstance(result.reason_code, str)
