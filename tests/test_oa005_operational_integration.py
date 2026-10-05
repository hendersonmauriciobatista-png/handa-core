"""OA005 operational integration falsifiers.

The application contract is intentionally absent at the start of this chain.
One boundary RED is allowed; downstream controls are semantic and become
reachable once the immutable application envelope exists.
"""

from importlib import import_module
import inspect
from types import SimpleNamespace

import pytest

from core.execution.execution_fact import normalize_external_execution
from core.position.position_effect_authority import PositionEffectResult


ADAPTER_MODULE = "core.execution.operational_effect_adapter"


def _adapter_module():
    return import_module(ADAPTER_MODULE)


def _application_binding_type():
    return getattr(_adapter_module(), "OperationalApplicationBinding", None)


def _require_application_contract():
    binding_type = _application_binding_type()
    if binding_type is None:
        pytest.skip("NOT_YET_REACHED: OperationalApplicationBinding is absent")
    return binding_type


def _raw_execution(
    *,
    order_id="order-oa005-1",
    trade_id="trade-oa005-1",
    quantity="0.4",
    non_overlapping=True,
):
    return {
        "symbol": "BTCUSDC",
        "side": "BUY",
        "orderId": order_id,
        "clientOrderId": f"client-{order_id}",
        "status": "PARTIALLY_FILLED",
        "executedQty": quantity,
        "cummulativeQuoteQty": "40",
        "fills": [
            {
                "tradeId": trade_id,
                "qty": quantity,
                "quoteQty": "40",
                "price": "100",
                "commission": "0",
                "commissionAsset": "USDT",
            }
        ],
        "nonOverlappingExtent": non_overlapping,
    }


def _fact(raw=None):
    return normalize_external_execution(raw or _raw_execution())


def _receipt(fact, *, extent_id=None, quantity=None):
    raw = _raw_execution(order_id=fact.external_order_id)
    return {
        "receipt_id": f"receipt-{fact.external_order_id}",
        "execution_extent_identity": (
            fact.execution_extent_identity if extent_id is None else extent_id
        ),
        "order_id": fact.external_order_id,
        "fills": raw["fills"],
        "executed_base_qty": (
            fact.executed_base_qty if quantity is None else quantity
        ),
        "status": "PARTIALLY_FILLED",
    }


def _binding(fact, *, effect_type="OPEN", intended_quantity=None, receipt=None):
    binding_type = _require_application_contract()
    return binding_type(
        effect_request_id="request-oa005-1",
        application_attempt_id="attempt-oa005-1",
        authority_contract_version="v1",
        claimant_id="oa005-worker",
        receipt=receipt or _receipt(fact),
        intended_quantity=intended_quantity,
    )


def _request(
    *,
    fact=None,
    semantic_state="RESOLVED",
    effect_type="OPEN",
    position_id=None,
    position_creation_id="position-creation-1",
    application_binding_marker=True,
    intended_quantity=None,
    receipt=None,
):
    module = _adapter_module()
    fact = fact or _fact()
    binding_type = _require_application_contract()
    application_binding = (
        binding_type(
            effect_request_id="request-oa005-1",
            application_attempt_id="attempt-oa005-1",
            authority_contract_version="v1",
            claimant_id="oa005-worker",
            receipt=receipt or _receipt(fact),
            intended_quantity=intended_quantity,
        )
        if application_binding_marker
        else None
    )
    return module.OperationalEffectRequest(
        execution_fact=fact,
        semantic_decision=SimpleNamespace(state=semantic_state),
        reconciliation_context_id="context-oa005",
        authority_decision_id="decision-oa005",
        decision_sequence=1,
        evidence_ids=("evidence-oa005",),
        effect_eligibility=module.EffectEligibility(
            effect_type=module.EffectType(effect_type),
            authority_decision_id="decision-oa005",
            reconciliation_context_id="context-oa005",
            decision_sequence=1,
            evidence_ids=("evidence-oa005",),
        ),
        logical_effect_identity=module.LogicalEffectIdentity(
            "intent-oa005", "logical-effect-oa005"
        ),
        position_binding=module.PositionBinding(
            position_id=position_id,
            position_creation_id=position_creation_id,
        ),
        application_binding=application_binding,
    )


class _RecordingCoordinator:
    def __init__(self, outcomes=None):
        self.calls = []
        self.outcomes = list(outcomes or [])

    def apply(self, **kwargs):
        self.calls.append(kwargs)
        if self.outcomes:
            return self.outcomes.pop(0)
        position_result = PositionEffectResult(
            position_id=(
                kwargs.get("position_id")
                or kwargs["position_binding"].position_creation_id
            ),
            effect_type=kwargs["logical_binding"].effect_type.value,
            previous_quantity=0,
            applied_quantity=kwargs["applied_quantity"],
            resulting_quantity=kwargs["applied_quantity"],
            state="ACTIVE",
            effect_request_id=kwargs["logical_binding"].effect_request_id,
            execution_extent_identity=kwargs["receipt"]["execution_extent_identity"],
        )
        return position_result


def _replay_result(fact):
    position_result = PositionEffectResult(
        position_id="position-creation-1",
        effect_type="OPEN",
        previous_quantity=0,
        applied_quantity=fact.executed_base_qty,
        resulting_quantity=fact.executed_base_qty,
        state="ACTIVE",
        effect_request_id="request-oa005-1",
        execution_extent_identity=fact.execution_extent_identity,
    )
    return SimpleNamespace(
        effect_request_id="request-oa005-1",
        position_effect_result=position_result,
    )


def test_oa005_application_contract_boundary_exists():
    binding_type = _application_binding_type()
    assert binding_type is not None
    assert inspect.isclass(binding_type)
    assert {
        "effect_request_id",
        "application_attempt_id",
        "authority_contract_version",
        "claimant_id",
        "receipt",
        "intended_quantity",
    } <= set(inspect.signature(binding_type).parameters)


def test_oa005_operational_request_identity_is_explicit_and_not_generated():
    binding_type = _require_application_contract()
    with pytest.raises(TypeError):
        binding_type(
            application_attempt_id="attempt-oa005-1",
            authority_contract_version="v1",
            claimant_id="oa005-worker",
            receipt={},
        )

    fact = _fact()
    coordinator = _RecordingCoordinator()
    result = _adapter_module().OperationalEffectAdapter(
        coordinator=coordinator
    ).apply(_request(fact=fact, intended_quantity=fact.executed_base_qty))

    assert result.status is _adapter_module().OperationalEffectStatus.EFFECT_APPLIED
    assert coordinator.calls[0]["logical_binding"].effect_request_id == (
        "request-oa005-1"
    )
    assert coordinator.calls[0]["application_attempt_id"] == "attempt-oa005-1"


def test_oa005_extent001_canonical_execution_extent_reaches_position_result():
    _require_application_contract()
    fact = _fact()
    coordinator = _RecordingCoordinator()
    result = _adapter_module().OperationalEffectAdapter(
        coordinator=coordinator
    ).apply(_request(fact=fact, intended_quantity=fact.executed_base_qty))

    assert result.status is _adapter_module().OperationalEffectStatus.EFFECT_APPLIED
    assert result.position_effect_result.execution_extent_identity == fact.execution_extent_identity
    assert coordinator.calls[0]["receipt"]["execution_extent_identity"] == fact.execution_extent_identity


def test_oa005_extent002_same_canonical_execution_evidence_has_same_extent_identity():
    _require_application_contract()
    first_fact = _fact()
    second_fact = _fact(raw=_raw_execution())
    coordinator = _RecordingCoordinator()
    adapter = _adapter_module().OperationalEffectAdapter(coordinator=coordinator)

    first = adapter.apply(
        _request(fact=first_fact, intended_quantity=first_fact.executed_base_qty)
    )
    second = adapter.apply(
        _request(fact=second_fact, intended_quantity=second_fact.executed_base_qty)
    )

    assert first_fact.execution_extent_identity == second_fact.execution_extent_identity
    assert first.position_effect_result.execution_extent_identity == (
        second.position_effect_result.execution_extent_identity
    )
    assert coordinator.calls[0]["receipt"]["execution_extent_identity"] == (
        coordinator.calls[1]["receipt"]["execution_extent_identity"]
    )


def test_oa005_extent003_materially_distinct_execution_extents_remain_distinct():
    _require_application_contract()
    first_fact = _fact(
        raw=_raw_execution(order_id="order-oa005-extent-a", trade_id="trade-a")
    )
    second_fact = _fact(
        raw=_raw_execution(
            order_id="order-oa005-extent-b",
            trade_id="trade-b",
            quantity="0.3",
        )
    )
    coordinator = _RecordingCoordinator()
    adapter = _adapter_module().OperationalEffectAdapter(coordinator=coordinator)

    first = adapter.apply(
        _request(fact=first_fact, intended_quantity=first_fact.executed_base_qty)
    )
    second = adapter.apply(
        _request(fact=second_fact, intended_quantity=second_fact.executed_base_qty)
    )

    assert first_fact.execution_extent_identity != second_fact.execution_extent_identity
    assert first.position_effect_result.execution_extent_identity != (
        second.position_effect_result.execution_extent_identity
    )


def test_oa005_app001_resolved_open_reaches_c4d_and_applies_once():
    _require_application_contract()
    fact = _fact()
    coordinator = _RecordingCoordinator()
    result = _adapter_module().OperationalEffectAdapter(
        coordinator=coordinator
    ).apply(_request(fact=fact, intended_quantity=fact.executed_base_qty))

    assert result.status is _adapter_module().OperationalEffectStatus.EFFECT_APPLIED
    assert len(coordinator.calls) == 1
    call = coordinator.calls[0]
    assert call["logical_binding"].effect_type is _adapter_module().EffectType.OPEN
    assert call["position_binding"].position_creation_id == "position-creation-1"
    assert call["applied_quantity"] == fact.executed_base_qty
    assert call["intended_quantity"] == fact.executed_base_qty


def test_oa005_app002_same_request_replay_returns_durable_result_without_second_mutation():
    _require_application_contract()
    fact = _fact()
    coordinator = _RecordingCoordinator(
        outcomes=[
            _RecordingCoordinator().apply(
                logical_binding=SimpleNamespace(effect_request_id="request-oa005-1", effect_type=SimpleNamespace(value="OPEN")),
                position_binding=SimpleNamespace(position_creation_id="position-creation-1"),
                position_id=None,
                receipt=_receipt(fact),
                applied_quantity=fact.executed_base_qty,
            ),
            _replay_result(fact),
        ]
    )
    adapter = _adapter_module().OperationalEffectAdapter(coordinator=coordinator)
    first = adapter.apply(_request(fact=fact, intended_quantity=fact.executed_base_qty))
    second = adapter.apply(_request(fact=fact, intended_quantity=fact.executed_base_qty))

    assert first.status is _adapter_module().OperationalEffectStatus.EFFECT_APPLIED
    assert second.status is _adapter_module().OperationalEffectStatus.EFFECT_APPLIED
    assert second.position_effect_result.execution_extent_identity == fact.execution_extent_identity
    assert len(coordinator.calls) == 2


def test_oa005_app003_reduce_uses_canonical_existing_position():
    _require_application_contract()
    fact = _fact()
    coordinator = _RecordingCoordinator()
    request = _request(
        fact=fact,
        effect_type="REDUCE",
        position_id="position-existing-1",
        position_creation_id=None,
    )
    _adapter_module().OperationalEffectAdapter(coordinator=coordinator).apply(request)
    call = coordinator.calls[0]
    assert call["position_id"] == "position-existing-1"
    assert call["position_binding"].position_id == "position-existing-1"
    assert call["position_binding"].position_creation_id is None


def test_oa005_app004_close_preserves_full_residual_authority():
    _require_application_contract()
    fact = _fact()
    coordinator = _RecordingCoordinator()
    request = _request(
        fact=fact,
        effect_type="CLOSE",
        position_id="position-existing-close",
        position_creation_id=None,
    )
    _adapter_module().OperationalEffectAdapter(coordinator=coordinator).apply(request)
    call = coordinator.calls[0]
    assert call["logical_binding"].effect_type is _adapter_module().EffectType.CLOSE
    assert call["applied_quantity"] == fact.executed_base_qty


def test_oa005_app005_cumulative_observation_cannot_apply():
    _require_application_contract()
    fact = _fact(
        raw={
            **_raw_execution(non_overlapping=False),
            "fills": [],
        }
    )
    coordinator = _RecordingCoordinator()
    result = _adapter_module().OperationalEffectAdapter(
        coordinator=coordinator
    ).apply(_request(fact=fact, application_binding_marker=False))

    assert fact.execution_extent_identity is None
    assert result.status is _adapter_module().OperationalEffectStatus.OUTCOME_UNKNOWN
    assert not coordinator.calls


def test_oa005_app006_receipt_extent_mismatch_fails_closed():
    _require_application_contract()
    fact = _fact()
    coordinator = _RecordingCoordinator()
    result = _adapter_module().OperationalEffectAdapter(
        coordinator=coordinator
    ).apply(
        _request(
            fact=fact,
            intended_quantity=fact.executed_base_qty,
            receipt=_receipt(fact, extent_id="wrong-canonical-extent"),
        )
    )

    assert result.status is _adapter_module().OperationalEffectStatus.CONTAINED
    assert not coordinator.calls


def test_oa005_app007_missing_application_binding_cannot_apply():
    _require_application_contract()
    fact = _fact()
    coordinator = _RecordingCoordinator()
    result = _adapter_module().OperationalEffectAdapter(
        coordinator=coordinator
    ).apply(_request(fact=fact, application_binding_marker=False))

    assert result.status is _adapter_module().OperationalEffectStatus.CONTAINED
    assert not coordinator.calls


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("PENDING", "PENDING"),
        ("BLOCKED", "BLOCKED"),
        ("RESOLVED", "OUTCOME_UNKNOWN"),
    ],
)
def test_oa005_app008_containment_never_calls_coordinator(state, expected):
    _require_application_contract()
    fact = _fact(
        raw=(
            _raw_execution(non_overlapping=False)
            if expected == "OUTCOME_UNKNOWN"
            else _raw_execution()
        )
    )
    coordinator = _RecordingCoordinator()
    result = _adapter_module().OperationalEffectAdapter(
        coordinator=coordinator
    ).apply(
        _request(
            fact=fact,
            semantic_state=state,
            application_binding_marker=False,
        )
    )

    assert result.status is _adapter_module().OperationalEffectStatus(expected)
    assert not coordinator.calls


def test_oa005_app009_recovery_required_does_not_retry_or_recover():
    _require_application_contract()
    fact = _fact()
    coordinator = _RecordingCoordinator(
        outcomes=[
            SimpleNamespace(
                effect_request_id="request-oa005-1",
                classification="RECOVERY_REQUIRED",
            )
        ]
    )
    result = _adapter_module().OperationalEffectAdapter(
        coordinator=coordinator
    ).apply(_request(fact=fact, intended_quantity=fact.executed_base_qty))

    assert result.status is _adapter_module().OperationalEffectStatus.CONTAINED
    assert len(coordinator.calls) == 1


def test_oa005_app010_adapter_has_no_external_submission_or_retry_authority():
    source = inspect.getsource(_adapter_module())
    forbidden = (
        "order_market",
        "submit_order",
        "resubmit",
        "retry_order",
        "recover_application",
    )
    assert all(token not in source for token in forbidden)
