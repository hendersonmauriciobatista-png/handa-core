"""Expected-RED falsifiers for the published operational effect boundary.

The public contract is present, but ``OperationalEffectAdapter.apply`` is
still intentionally unimplemented.  Every behavioral falsifier must cross
that same boundary before it can be classified; one shared boundary RED is
reported and downstream controls remain NOT_YET_REACHED.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = ROOT / "core" / "execution" / "operational_effect_adapter.py"


def _request(
    *,
    effect_type="OPEN",
    position_binding=None,
    semantic_state="RESOLVED",
    execution_fact=None,
):
    from core.execution.operational_effect_adapter import (
        EffectEligibility,
        EffectType,
        LogicalEffectIdentity,
        OperationalEffectRequest,
        PositionBinding,
    )

    if position_binding is None:
        position_binding = PositionBinding(position_creation_id="creation-1")
    if execution_fact is None:
        execution_fact = object()
    eligibility = EffectEligibility(
        effect_type=EffectType(effect_type),
        authority_decision_id="decision-1",
        reconciliation_context_id="context-1",
        decision_sequence=1,
        evidence_ids=("evidence-1",),
    )
    return OperationalEffectRequest(
        execution_fact=execution_fact,
        semantic_decision=SimpleNamespace(state=semantic_state),
        reconciliation_context_id="context-1",
        authority_decision_id="decision-1",
        decision_sequence=1,
        evidence_ids=("evidence-1",),
        effect_eligibility=eligibility,
        logical_effect_identity=LogicalEffectIdentity("intent-1", "effect-1"),
        position_binding=position_binding,
    )


def _invoke_behavioral_boundary(oa_id, request=None):
    from core.execution.operational_effect_adapter import OperationalEffectAdapter

    try:
        result = OperationalEffectAdapter().apply(request or _request())
    except NotImplementedError as exc:
        pytest.skip(
            f"NOT_YET_REACHED: next shared BOUNDARY_RED from OA-004; {oa_id} "
            f"terminated at OperationalEffectAdapter.apply: {exc}"
        )
    pytest.fail(
        f"UNEXPECTED_BEHAVIOR: {oa_id} crossed the published boundary with "
        f"result {result!r}"
    )


def _invoke_containment(oa_id, semantic_state, execution_fact=None):
    from core.execution.operational_effect_adapter import (
        OperationalEffectAdapter,
        OperationalEffectStatus,
    )

    result = OperationalEffectAdapter().apply(
        _request(
            semantic_state=semantic_state,
            execution_fact=execution_fact,
        )
    )
    assert result.status is OperationalEffectStatus(semantic_state)
    assert result.effect_request_id is None
    assert result.position_effect_result is None
    assert result.reconciliation_context_id == "context-1"
    assert result.authority_decision_id == "decision-1"
    assert result.evidence_ids == ("evidence-1",)
    return result


def _unknown_execution_fact():
    from core.execution.execution_fact import normalize_external_execution

    return normalize_external_execution(
        {
            "symbol": "BTCUSDC",
            "side": "BUY",
            "orderId": "unknown-order-1",
            "status": "FILLED",
            "executedQty": "1",
            "cummulativeQuoteQty": "100",
        }
    )


def _invoke_unknown_containment():
    from core.execution.operational_effect_adapter import (
        OperationalEffectAdapter,
        OperationalEffectStatus,
    )

    result = OperationalEffectAdapter().apply(
        _request(execution_fact=_unknown_execution_fact())
    )
    assert result.status is OperationalEffectStatus.OUTCOME_UNKNOWN
    assert result.effect_request_id is None
    assert result.position_effect_result is None
    assert result.reconciliation_context_id == "context-1"
    assert result.authority_decision_id == "decision-1"
    assert result.evidence_ids == ("evidence-1",)


def test_oa001_adapter_boundary_root_is_reached():
    """The published contract boundary remains present and callable."""
    assert ADAPTER_PATH.exists(), (
        "OA-001 contract boundary missing: operational_effect_adapter.py "
        "is not present"
    )
    from core.execution.operational_effect_adapter import OperationalEffectAdapter

    assert callable(OperationalEffectAdapter.apply)


def test_oa002_pending_cannot_mutate():
    _invoke_containment("OA-002", "PENDING", _unknown_execution_fact())


def test_oa003_blocked_cannot_mutate():
    _invoke_containment("OA-003", "BLOCKED", _unknown_execution_fact())


def test_oa004_unknown_cannot_mutate():
    _invoke_unknown_containment()


def test_oa005_same_effect_request_replay_is_idempotent():
    _invoke_behavioral_boundary("OA-005")


def test_oa006_extent_cannot_be_reused_across_requests():
    _invoke_behavioral_boundary("OA-006")


def test_oa007_cumulative_observation_cannot_become_extent():
    _invoke_behavioral_boundary("OA-007")


def test_oa008_partial_sell_cannot_close():
    _invoke_behavioral_boundary("OA-008", _request(effect_type="CLOSE"))


def test_oa009_open_replay_cannot_create_second_position():
    _invoke_behavioral_boundary("OA-009")


def test_oa010_atomic_rollback_leaves_no_residue():
    _invoke_behavioral_boundary("OA-010")


def test_oa011_post_commit_caller_loss_replays_safely():
    _invoke_behavioral_boundary("OA-011")


def test_oa012_adapter_cannot_submit_external_order():
    _invoke_behavioral_boundary("OA-012")


def test_oa013_adapter_cannot_retry_external_order():
    _invoke_behavioral_boundary("OA-013")


def test_oa014_ambiguous_position_binding_blocks():
    from core.execution.operational_effect_adapter import PositionBinding

    _invoke_behavioral_boundary("OA-014", _request(position_binding=PositionBinding()))


def test_oa015_accounting_follows_position_effect():
    _invoke_behavioral_boundary("OA-015")


def test_oa016_slot_transition_follows_governed_result():
    _invoke_behavioral_boundary("OA-016")


def test_oa017_ledger_and_position_share_transaction():
    _invoke_behavioral_boundary("OA-017")


def test_oa018_receipt_binds_exact_extent():
    _invoke_behavioral_boundary("OA-018")


def test_oa019_effect_type_requires_governed_eligibility():
    _invoke_behavioral_boundary("OA-019")


def test_oa020_logical_effect_identity_is_stable():
    _invoke_behavioral_boundary("OA-020")


def test_oa021_open_requires_creation_identity():
    from core.execution.operational_effect_adapter import PositionBinding

    _invoke_behavioral_boundary(
        "OA-021",
        _request(position_binding=PositionBinding(position_id="position-1")),
    )


def test_oa022_result_does_not_leak_authority():
    _invoke_behavioral_boundary("OA-022")


def test_oc001_request_rejects_identity_cross_binding():
    from core.execution.operational_effect_adapter import (
        EffectEligibility,
        EffectType,
        LogicalEffectIdentity,
        OperationalEffectRequest,
        PositionBinding,
    )

    mismatches = (
        ("authority_decision_id", "decision-request", "decision-eligibility"),
        ("reconciliation_context_id", "context-request", "context-eligibility"),
        ("decision_sequence", 1, 2),
    )
    accepted = []

    for field, request_value, eligibility_value in mismatches:
        eligibility_values = {
            "effect_type": EffectType.OPEN,
            "authority_decision_id": "decision-1",
            "reconciliation_context_id": "context-1",
            "decision_sequence": 1,
            "evidence_ids": ("evidence-1",),
        }
        request_values = {
            "execution_fact": object(),
            "semantic_decision": object(),
            "reconciliation_context_id": "context-1",
            "authority_decision_id": "decision-1",
            "decision_sequence": 1,
            "evidence_ids": ("evidence-1",),
            "effect_eligibility": EffectEligibility(**eligibility_values),
            "logical_effect_identity": LogicalEffectIdentity("intent-1", "effect-1"),
            "position_binding": PositionBinding(position_creation_id="creation-1"),
        }
        request_values[field] = request_value
        eligibility_values[field] = eligibility_value
        request_values["effect_eligibility"] = EffectEligibility(**eligibility_values)

        try:
            OperationalEffectRequest(**request_values)
        except (TypeError, ValueError):
            continue
        accepted.append(field)

    assert not accepted, f"identity cross-binding accepted: {accepted}"


def test_oc002_effect_applied_requires_effect_request_id():
    from core.execution.operational_effect_adapter import (
        OperationalEffectResult,
        OperationalEffectStatus,
    )

    try:
        OperationalEffectResult(
            status=OperationalEffectStatus.EFFECT_APPLIED,
            effect_request_id=None,
        )
    except (TypeError, ValueError):
        return

    raise AssertionError(
        "EFFECT_APPLIED accepted without effect_request_id"
    )
