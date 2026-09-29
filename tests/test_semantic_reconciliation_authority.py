"""Expected-red contract tests for the future semantic authority.

These tests define the minimum pure authority seam without creating a
production stub.  The initial red is intentional while the capability is
absent.
"""

from copy import deepcopy

import pytest


def governed_input(**overrides):
    value = {
        "decision_scope": "ORDER_OUTCOME",
        "intent_id": "intent-1",
        "symbol": "BTCUSDC",
        "order_id": "order-1",
        "client_order_id": "client-1",
        "propositions": {
            "execution_occurred": True,
            "order_outcome_terminal": True,
            "execution_extent": "UNKNOWN",
            "final_partial_outcome": "UNKNOWN",
        },
        "evidence": [
            {
                "evidence_id": "obs-1",
                "source": "exchange_order_query",
                "status": "FILLED",
            }
        ],
    }
    value.update(overrides)
    return value


def authority_contract():
    from core.execution.semantic_reconciliation_authority import (
        GovernedSemanticDecisionInput,
        SemanticReconciliationAuthority,
    )

    return SemanticReconciliationAuthority, GovernedSemanticDecisionInput


def evaluate(value):
    authority, input_type = authority_contract()
    return authority.evaluate(input_type.from_mapping(value))


def test_r1_authority_capability_exists_as_the_declared_pure_seam():
    authority, input_type = authority_contract()

    assert authority is not None
    assert input_type is not None
    assert callable(authority.evaluate)


def test_r2_timeout_is_pending_not_no_effect():
    value = governed_input(
        propositions={
            "execution_occurred": "UNKNOWN",
            "order_outcome_terminal": "UNKNOWN",
            "execution_extent": "UNKNOWN",
            "final_partial_outcome": "UNKNOWN",
        },
        evidence=[{"evidence_id": "transport-1", "source": "timeout"}],
    )

    result = evaluate(value)

    assert result.state == "PENDING"
    assert result.propositions["execution_occurred"] == "UNKNOWN"
    assert result.propositions.get("no_effect_confirmed") is not True


def test_r3_required_unknown_extent_cannot_resolve():
    value = governed_input(
        decision_scope="QUANTITY_DEPENDENT",
        propositions={
            "execution_occurred": True,
            "order_outcome_terminal": True,
            "execution_extent": "UNKNOWN",
            "final_partial_outcome": "UNKNOWN",
        },
    )

    result = evaluate(value)

    assert result.state == "PENDING"
    assert result.propositions["execution_extent"] == "UNKNOWN"


def test_r4_positive_trade_and_zero_snapshot_are_blocked():
    value = governed_input(
        decision_scope="QUANTITY_DEPENDENT",
        propositions={
            "execution_occurred": "CONTRADICTORY",
            "order_outcome_terminal": True,
            "execution_extent": "UNKNOWN",
            "final_partial_outcome": "UNKNOWN",
        },
        evidence=[
            {"evidence_id": "trade-1", "source": "trade", "trade_qty": "0.1"},
            {
                "evidence_id": "obs-2",
                "source": "exchange_order_query",
                "status": "CANCELED",
                "executed_qty": "0",
            },
        ],
    )

    result = evaluate(value)

    assert result.state == "BLOCKED"
    assert result.lineage.evidence_ids == ["trade-1", "obs-2"]


def test_r5_normalizer_not_required_is_not_authority_input():
    value = governed_input(
        normalized_state="NOT_REQUIRED",
        propositions={
            "execution_occurred": "UNKNOWN",
            "order_outcome_terminal": "UNKNOWN",
            "execution_extent": "UNKNOWN",
            "final_partial_outcome": "UNKNOWN",
        },
        evidence=[],
    )

    result = evaluate(value)

    assert result.state != "NOT_REQUIRED"
    assert result.state in {"PENDING", "BLOCKED"}


def test_r6_authority_has_no_operational_side_effects():
    value = governed_input()
    before = deepcopy(value)

    result = evaluate(value)

    assert value == before
    assert result.side_effects == ()
    assert result.operations == ()


def test_r7_identical_governed_input_is_deterministic():
    value = governed_input()
    first = evaluate(deepcopy(value))
    second = evaluate(deepcopy(value))

    assert first == second


def test_identity_mismatch_blocks_attribution():
    value = governed_input(
        evidence=[
            {
                "evidence_id": "obs-identity-conflict",
                "source": "exchange_order_query",
                "status": "FILLED",
                "order_id": "different-order",
            }
        ]
    )

    result = evaluate(value)

    assert result.state == "BLOCKED"


def test_partially_filled_to_filled_is_compatible_progression():
    value = governed_input(
        evidence=[
            {
                "evidence_id": "obs-partial",
                "source": "exchange_order_query",
                "status": "PARTIALLY_FILLED",
                "executed_qty": "0.1",
            },
            {
                "evidence_id": "obs-filled",
                "source": "exchange_order_query",
                "status": "FILLED",
                "executed_qty": "1.0",
            },
        ]
    )

    result = evaluate(value)

    assert result.state != "BLOCKED"
    assert result.lineage.evidence_ids == ["obs-partial", "obs-filled"]


def test_partially_filled_to_canceled_with_positive_quantity_is_compatible():
    value = governed_input(
        evidence=[
            {
                "evidence_id": "obs-partial",
                "source": "exchange_order_query",
                "status": "PARTIALLY_FILLED",
                "executed_qty": "0.1",
            },
            {
                "evidence_id": "obs-canceled",
                "source": "exchange_order_query",
                "status": "CANCELED",
                "executed_qty": "0.1",
            },
        ]
    )

    result = evaluate(value)

    assert result.state != "BLOCKED"
    assert result.lineage.evidence_ids == ["obs-partial", "obs-canceled"]


def test_correlated_rejected_observation_is_positive_no_effect_evidence():
    value = governed_input(
        propositions={
            "execution_occurred": False,
            "order_outcome_terminal": True,
            "execution_extent": "UNKNOWN",
            "final_partial_outcome": False,
        },
        evidence=[
            {
                "evidence_id": "obs-rejected",
                "source": "exchange_order_query",
                "status": "REJECTED",
                "order_id": "order-1",
                "client_order_id": "client-1",
            }
        ],
    )

    result = evaluate(value)

    assert result.state == "RESOLVED"
    assert result.propositions["no_effect_confirmed"] is True


def test_distinct_evidence_identities_remain_in_lineage():
    value = governed_input(
        evidence=[
            {
                "evidence_id": "obs-1",
                "source": "exchange_order_query",
                "status": "PARTIALLY_FILLED",
            },
            {
                "evidence_id": "trade-1",
                "source": "trade",
                "trade_qty": "0.1",
            },
        ]
    )

    result = evaluate(value)

    assert result.lineage.evidence_ids == ["obs-1", "trade-1"]


def test_unknown_without_contradiction_remains_pending():
    result = evaluate(
        governed_input(
            propositions={
                "execution_occurred": "UNKNOWN",
                "order_outcome_terminal": "UNKNOWN",
                "execution_extent": "UNKNOWN",
                "final_partial_outcome": "UNKNOWN",
            },
            evidence=[{"evidence_id": "obs-unknown", "source": "exchange_order_query"}],
        )
    )

    assert result.state == "PENDING"


def test_material_contradiction_blocks_despite_otherwise_sufficient_input():
    result = evaluate(
        governed_input(
            propositions={
                "execution_occurred": "CONTRADICTORY",
                "order_outcome_terminal": True,
                "execution_extent": "FULL",
                "final_partial_outcome": False,
            },
            evidence=[{"evidence_id": "obs-filled", "status": "FILLED"}],
        )
    )

    assert result.state == "BLOCKED"


def test_rejected_with_positive_execution_is_blocked_not_no_effect():
    result = evaluate(
        governed_input(
            propositions={
                "execution_occurred": True,
                "order_outcome_terminal": True,
                "execution_extent": "PARTIAL",
                "final_partial_outcome": "UNKNOWN",
            },
            evidence=[
                {
                    "evidence_id": "obs-rejected",
                    "source": "exchange_order_query",
                    "status": "REJECTED",
                },
                {
                    "evidence_id": "trade-positive",
                    "source": "trade",
                    "trade_qty": "0.1",
                },
            ],
        )
    )

    assert result.state == "BLOCKED"
    assert result.propositions.get("no_effect_confirmed") is not True


def test_duplicate_evidence_identity_does_not_change_semantics():
    one_reference = evaluate(
        governed_input(
            evidence=[
                {
                    "evidence_id": "obs-1",
                    "source": "exchange_order_query",
                    "status": "FILLED",
                }
            ]
        )
    )
    duplicate_reference = evaluate(
        governed_input(
            evidence=[
                {
                    "evidence_id": "obs-1",
                    "source": "exchange_order_query",
                    "status": "FILLED",
                },
                {
                    "evidence_id": "obs-1",
                    "source": "exchange_order_query",
                    "status": "FILLED",
                },
            ]
        )
    )

    assert duplicate_reference.state == one_reference.state
    assert duplicate_reference.propositions == one_reference.propositions


def test_input_order_permutation_has_identical_semantic_result():
    first = evaluate(
        governed_input(
            evidence=[
                {
                    "evidence_id": "obs-1",
                    "source": "exchange_order_query",
                    "status": "PARTIALLY_FILLED",
                },
                {"evidence_id": "trade-1", "source": "trade", "trade_qty": "0.1"},
            ]
        )
    )
    second = evaluate(
        governed_input(
            evidence=[
                {"evidence_id": "trade-1", "source": "trade", "trade_qty": "0.1"},
                {
                    "evidence_id": "obs-1",
                    "source": "exchange_order_query",
                    "status": "PARTIALLY_FILLED",
                },
            ]
        )
    )

    assert second.state == first.state
    assert second.propositions == first.propositions
    assert set(second.lineage.evidence_ids) == set(first.lineage.evidence_ids)


def test_authority_result_exposes_no_operational_permission():
    result = evaluate(governed_input())

    assert not hasattr(result, "retry")
    assert not hasattr(result, "resubmit")
    assert not hasattr(result, "release_containment")
    assert not hasattr(result, "position_effect")
    assert not hasattr(result, "slot_effect")


def test_no_effect_confirmation_does_not_expose_retry_permission():
    result = evaluate(
        governed_input(
            propositions={
                "execution_occurred": False,
                "order_outcome_terminal": True,
                "execution_extent": "UNKNOWN",
                "final_partial_outcome": False,
            },
            evidence=[
                {
                    "evidence_id": "obs-rejected",
                    "source": "exchange_order_query",
                    "status": "REJECTED",
                    "order_id": "order-1",
                    "client_order_id": "client-1",
                }
            ],
        )
    )

    assert result.propositions["no_effect_confirmed"] is True
    assert not hasattr(result, "retry")
    assert not hasattr(result, "resubmit")


def test_active_partial_execution_is_not_final_partial():
    result = evaluate(
        governed_input(
            propositions={
                "execution_occurred": True,
                "order_outcome_terminal": False,
                "execution_extent": "PARTIAL",
                "final_partial_outcome": False,
            },
            evidence=[
                {
                    "evidence_id": "obs-partial-active",
                    "source": "exchange_order_query",
                    "status": "PARTIALLY_FILLED",
                    "executed_qty": "0.1",
                }
            ],
        )
    )

    assert result.propositions["execution_occurred"] is True
    assert result.propositions["final_partial_outcome"] is False


def test_filled_with_extent_required_and_unknown_remains_pending():
    result = evaluate(
        governed_input(
            decision_scope="QUANTITY_DEPENDENT",
            propositions={
                "execution_occurred": True,
                "order_outcome_terminal": True,
                "execution_extent": "UNKNOWN",
                "final_partial_outcome": "UNKNOWN",
            },
            evidence=[
                {
                    "evidence_id": "obs-filled",
                    "source": "exchange_order_query",
                    "status": "FILLED",
                }
            ],
        )
    )

    assert result.state == "PENDING"


def test_filled_with_extent_outside_scope_does_not_invent_full_extent():
    result = evaluate(
        governed_input(
            decision_scope="ORDER_OUTCOME",
            propositions={
                "execution_occurred": True,
                "order_outcome_terminal": True,
                "execution_extent": "UNKNOWN",
                "final_partial_outcome": "UNKNOWN",
            },
            evidence=[
                {
                    "evidence_id": "obs-filled",
                    "source": "exchange_order_query",
                    "status": "FILLED",
                }
            ],
        )
    )

    assert result.state in {"RESOLVED", "NOT_REQUIRED"}
    assert result.propositions["execution_extent"] != "FULL"


@pytest.mark.parametrize(
    "value",
    [
        governed_input(),
        governed_input(
            propositions={
                "execution_occurred": "UNKNOWN",
                "order_outcome_terminal": "UNKNOWN",
                "execution_extent": "UNKNOWN",
                "final_partial_outcome": "UNKNOWN",
            },
            evidence=[],
        ),
        governed_input(
            propositions={
                "execution_occurred": "CONTRADICTORY",
                "order_outcome_terminal": True,
                "execution_extent": "UNKNOWN",
                "final_partial_outcome": "UNKNOWN",
            }
        ),
        governed_input(
            evidence=[
                {
                    "evidence_id": "obs-identity-conflict",
                    "source": "exchange_order_query",
                    "status": "FILLED",
                    "order_id": "different-order",
                }
            ]
        ),
    ],
)
def test_authority_output_domain_excludes_not_required(value):
    result = evaluate(value)

    assert result.state in {"RESOLVED", "PENDING", "BLOCKED"}
    assert result.state != "NOT_REQUIRED"


def test_normalizer_not_required_never_propagates_as_authority_state():
    result = evaluate(
        governed_input(
            normalized_state="NOT_REQUIRED",
            propositions={
                "execution_occurred": True,
                "order_outcome_terminal": True,
                "execution_extent": "UNKNOWN",
                "final_partial_outcome": "UNKNOWN",
            },
        )
    )

    assert result.state in {"RESOLVED", "PENDING", "BLOCKED"}
    assert result.state != "NOT_REQUIRED"


@pytest.mark.parametrize("decision_scope", ["ORDER_OUTCOME", "QUANTITY_DEPENDENT"])
def test_current_recognized_scopes_never_produce_not_required(decision_scope):
    result = evaluate(
        governed_input(
            decision_scope=decision_scope,
            propositions={
                "execution_occurred": True,
                "order_outcome_terminal": True,
                "execution_extent": "UNKNOWN",
                "final_partial_outcome": "UNKNOWN",
            },
        )
    )

    assert result.state in {"RESOLVED", "PENDING", "BLOCKED"}
    assert result.state != "NOT_REQUIRED"


def test_decision_type_rejects_historical_not_required_output_state():
    from core.execution.semantic_reconciliation_authority import (
        SemanticEvidenceLineage,
        SemanticReconciliationDecision,
    )

    with pytest.raises(ValueError):
        SemanticReconciliationDecision(
            state="NOT_REQUIRED",
            propositions={},
            lineage=SemanticEvidenceLineage(evidence_ids=[]),
        )


def test_rejected_with_positive_executed_qty_is_material_contradiction():
    result = evaluate(
        governed_input(
            propositions={
                "execution_occurred": True,
                "order_outcome_terminal": True,
                "execution_extent": "UNKNOWN",
                "final_partial_outcome": "UNKNOWN",
            },
            evidence=[
                {
                    "evidence_id": "obs-rejected-positive-qty",
                    "source": "exchange_order_query",
                    "status": "REJECTED",
                    "executed_qty": "0.1",
                    "order_id": "order-1",
                    "client_order_id": "client-1",
                }
            ],
        )
    )

    assert result.state == "BLOCKED"
    assert result.propositions.get("no_effect_confirmed") is not True


def test_rejected_with_explicit_zero_quantity_preserves_no_effect_behavior():
    result = evaluate(
        governed_input(
            propositions={
                "execution_occurred": False,
                "order_outcome_terminal": True,
                "execution_extent": "UNKNOWN",
                "final_partial_outcome": False,
            },
            evidence=[
                {
                    "evidence_id": "obs-rejected-zero-qty",
                    "source": "exchange_order_query",
                    "status": "REJECTED",
                    "executed_qty": "0",
                    "order_id": "order-1",
                    "client_order_id": "client-1",
                }
            ],
        )
    )

    assert result.state == "RESOLVED"
    assert result.propositions["no_effect_confirmed"] is True


def test_positive_executed_qty_alone_proves_occurrence_only():
    result = evaluate(
        governed_input(
            propositions={
                "execution_occurred": True,
                "order_outcome_terminal": False,
                "execution_extent": "UNKNOWN",
                "final_partial_outcome": False,
            },
            evidence=[
                {
                    "evidence_id": "obs-positive-qty",
                    "source": "exchange_order_query",
                    "status": "NEW",
                    "executed_qty": "0.1",
                }
            ],
        )
    )

    assert result.propositions["execution_occurred"] is True
    assert result.propositions["execution_extent"] == "UNKNOWN"
    assert result.propositions["final_partial_outcome"] is False


@pytest.mark.parametrize("decision_scope", ["ORDER_OUTCOME", "QUANTITY_DEPENDENT"])
def test_known_supported_scope_remains_evaluable(decision_scope):
    result = evaluate(governed_input(decision_scope=decision_scope))

    assert result.state in {"RESOLVED", "PENDING", "BLOCKED"}


def test_unknown_decision_scope_is_rejected_as_invalid_input():
    with pytest.raises(ValueError):
        evaluate(governed_input(decision_scope="UNRECOGNIZED_SCOPE"))


def test_unsupported_quantitative_scope_is_rejected_as_invalid_input():
    with pytest.raises(ValueError):
        evaluate(governed_input(decision_scope="QUOTE_QUANTITATIVE"))
