"""C4A expected-RED falsifiers for result and identity contracts only.

These controls define no persistence, lookup, replay, claim, transaction, or
position-effect behavior.  Missing shared contract surfaces are reported once
and dependent controls remain NOT_YET_REACHED.
"""

from dataclasses import MISSING, fields, is_dataclass
from importlib import import_module
import inspect

import pytest


ADAPTER_MODULE = "core.execution.operational_effect_adapter"


def _adapter_module():
    return import_module(ADAPTER_MODULE)


def _logical_effect_binding_type():
    return getattr(_adapter_module(), "LogicalEffectBinding", None)


def _require_logical_effect_binding():
    binding_type = _logical_effect_binding_type()
    if binding_type is None:
        pytest.skip(
            "NOT_YET_REACHED: shared C4A-001 BOUNDARY_RED; "
            "LogicalEffectBinding contract is absent"
        )
    return binding_type


def _failed_without_effect_status():
    status_type = _adapter_module().OperationalEffectStatus
    return getattr(status_type, "FAILED_WITHOUT_EFFECT", None)


def _require_failed_without_effect_status():
    status = _failed_without_effect_status()
    if status is None:
        pytest.skip(
            "NOT_YET_REACHED: shared C4A-007 VALID_RED; "
            "OperationalEffectStatus.FAILED_WITHOUT_EFFECT is absent"
        )
    return status


def test_c4a001_logical_effect_binding_contract_exists():
    assert _logical_effect_binding_type() is not None, (
        "BOUNDARY_RED[shared]: LogicalEffectBinding is absent; "
        "C4A-002..C4A-004 are not independently reached"
    )


def test_c4a002_binding_uses_only_canonical_logical_key():
    binding_type = _require_logical_effect_binding()
    annotations = getattr(binding_type, "__annotations__", {})
    assert "logical_identity" in annotations
    assert "effect_request_id" in annotations
    assert "effect_type" in annotations

    identity_annotations = _adapter_module().LogicalEffectIdentity.__annotations__
    assert tuple(identity_annotations) == ("intent_id", "logical_effect_id")

    forbidden_substitutes = {
        "observation_identity",
        "external_order_id",
        "execution_extent_identity",
        "symbol",
        "side",
        "quantity",
        "position_id",
    }
    assert forbidden_substitutes.isdisjoint(annotations)

    has_authority_reference = any(
        name in annotations
        for name in ("effect_eligibility", "authority_binding")
    )
    has_direct_authority_lineage = {
        "authority_decision_id",
        "reconciliation_context_id",
        "decision_sequence",
    } <= set(annotations)
    assert has_authority_reference or has_direct_authority_lineage


def test_c4a003_binding_is_immutable_without_mutable_defaults():
    binding_type = _require_logical_effect_binding()
    assert is_dataclass(binding_type)
    assert binding_type.__dataclass_params__.frozen is True
    for field in fields(binding_type):
        if field.default is not MISSING:
            assert not isinstance(field.default, (dict, list, set))


def test_c4a004_candidate_effect_request_id_is_explicit_input():
    binding_type = _require_logical_effect_binding()
    request_id_field = next(
        field for field in fields(binding_type) if field.name == "effect_request_id"
    )
    assert request_id_field.default is MISSING
    assert request_id_field.default_factory is MISSING


def test_c4a005_adapter_effect_type_vocabulary_is_canonical_and_bounded():
    effect_type = _adapter_module().EffectType
    assert {item.value for item in effect_type} == {"OPEN", "REDUCE", "CLOSE"}


def test_c4a006_ledger_remains_generic_and_not_effect_type_authority():
    ledger_module = import_module("core.persistence.effect_application_ledger")
    signature = inspect.signature(
        ledger_module.EffectApplicationLedger.create_effect_request
    )
    annotation = signature.parameters["effect_type"].annotation
    assert annotation in (str, "str")


def test_c4a007_failed_without_effect_status_exists():
    assert _failed_without_effect_status() is not None, (
        "VALID_RED: OperationalEffectStatus.FAILED_WITHOUT_EFFECT is absent; "
        "C4A-008..C4A-009 are not independently reached"
    )


def test_c4a008_failed_without_effect_requires_effect_request_id():
    module = _adapter_module()
    status = _require_failed_without_effect_status()
    with pytest.raises((TypeError, ValueError)):
        module.OperationalEffectResult(status=status, effect_request_id=None)


def test_c4a009_failed_without_effect_has_no_position_result_or_retry_authority():
    module = _adapter_module()
    status = _require_failed_without_effect_status()
    result = module.OperationalEffectResult(
        status=status,
        effect_request_id="effect-request-1",
    )
    assert result.position_effect_result is None
    assert "retry" not in module.OperationalEffectResult.__annotations__
    assert "retry_authority" not in module.OperationalEffectResult.__annotations__


def test_c4a010_existing_operational_result_semantics_are_preserved():
    module = _adapter_module()
    statuses = module.OperationalEffectStatus
    existing = {
        statuses.EFFECT_APPLIED,
        statuses.CONTAINED,
        statuses.PENDING,
        statuses.BLOCKED,
        statuses.OUTCOME_UNKNOWN,
    }
    with pytest.raises((TypeError, ValueError)):
        module.OperationalEffectResult(
            status=statuses.EFFECT_APPLIED,
            effect_request_id=None,
        )
    for status in existing - {statuses.EFFECT_APPLIED}:
        result = module.OperationalEffectResult(status=status)
        assert result.effect_request_id is None


def test_c4a011_logical_effect_identity_contract_is_preserved():
    identity_type = _adapter_module().LogicalEffectIdentity
    assert tuple(identity_type.__annotations__) == (
        "intent_id",
        "logical_effect_id",
    )
    assert is_dataclass(identity_type)
    assert identity_type.__dataclass_params__.frozen is True


def test_c4a012_c4a_types_do_not_implement_replay_or_operational_behavior():
    module = _adapter_module()
    apply_source = inspect.getsource(module.OperationalEffectAdapter.apply)
    forbidden = (
        "LogicalEffectBinding",
        "EffectApplicationLedger",
        "claim_application",
        "get_application_state",
        "PositionEffectAuthority",
        "apply_open",
        "apply_reduction",
        "apply_close",
        "order_market",
        "retry",
        "resubmit",
    )
    assert all(token not in apply_source for token in forbidden)
