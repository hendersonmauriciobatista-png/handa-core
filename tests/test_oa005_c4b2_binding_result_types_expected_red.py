"""C4B-2 expected-RED falsifiers for binding result vocabulary only.

The published ``LogicalEffectBinding`` is reused.  These controls do not add
lookup, binding persistence, transaction, replay, or adapter behavior.
"""

from dataclasses import fields, is_dataclass
from dataclasses import FrozenInstanceError
from enum import Enum
import importlib
import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import get_type_hints

import pytest


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_MODULE = "core.execution.operational_effect_adapter"
LEDGER_MODULE = "core.persistence.effect_application_ledger"

LOOKUP_VALUES = {
    "NOT_FOUND",
    "FOUND_VALID_BINDING",
    "FOUND_CONFLICTING_BINDING",
}
WRITE_VALUES = {
    "CREATED_CANONICAL_BINDING",
    "EXISTING_VALID_BINDING",
    "CONFLICTING_BINDING",
}


def _adapter_module():
    return importlib.import_module(ADAPTER_MODULE)


def _ledger_module():
    return importlib.import_module(LEDGER_MODULE)


def _binding_type():
    return _adapter_module().LogicalEffectBinding


def _enum_types():
    module = _adapter_module()
    return [
        candidate
        for _, candidate in inspect.getmembers(module, inspect.isclass)
        if issubclass(candidate, Enum)
    ]


def _enum_with_values(values):
    matches = []
    for candidate in _enum_types():
        if {item.value for item in candidate} == values:
            matches.append(candidate)
    return matches


def _lookup_disposition_type():
    matches = _enum_with_values(LOOKUP_VALUES)
    return matches[0] if matches else None


def _write_disposition_type():
    matches = _enum_with_values(WRITE_VALUES)
    return matches[0] if matches else None


def _public_ledger_methods():
    ledger_type = _ledger_module().EffectApplicationLedger
    return {
        name: member
        for name, member in inspect.getmembers(ledger_type, inspect.isfunction)
        if not name.startswith("_")
    }


def _has_c4_binding_write_capability():
    required = {
        "effect_request_id",
        "effect_type",
        "authority_decision_id",
        "reconciliation_context_id",
        "decision_sequence",
        "authority_contract_version",
    }
    for method in _public_ledger_methods().values():
        parameters = set(inspect.signature(method).parameters)
        if required <= parameters and ({"logical_effect_id", "logical_identity"} & parameters):
            return True
    return False


def _has_logical_lookup_capability():
    for method in _public_ledger_methods().values():
        parameters = set(inspect.signature(method).parameters)
        if {"logical_effect_id", "logical_identity"} & parameters:
            return "effect_request_id" not in parameters
    return False


def _binding():
    module = _adapter_module()
    return module.LogicalEffectBinding(
        logical_identity=module.LogicalEffectIdentity("intent-1", "logical-1"),
        effect_request_id="request-1",
        effect_type=module.EffectType.OPEN,
        authority_decision_id="decision-1",
        reconciliation_context_id="context-1",
        decision_sequence=1,
        authority_contract_version="v1",
    )


def test_c4b2001_published_binding_type_is_reused():
    binding_type = _binding_type()
    assert is_dataclass(binding_type)
    assert tuple(field.name for field in fields(binding_type)) == (
        "logical_identity",
        "effect_request_id",
        "effect_type",
        "authority_decision_id",
        "reconciliation_context_id",
        "decision_sequence",
        "authority_contract_version",
    )
    assert not any(
        name in _adapter_module().__dict__
        for name in (
            "PersistentLogicalEffectBinding",
            "LedgerLogicalBinding",
            "CanonicalLogicalBinding",
        )
    )


def test_c4b2002_published_binding_remains_frozen_and_non_rebindable():
    binding = _binding()
    with pytest.raises(FrozenInstanceError):
        binding.effect_request_id = "request-2"
    assert not any(
        callable(getattr(binding, name, None))
        for name in ("rebind", "overwrite", "replace_authority")
    )


def test_c4b2003_lookup_disposition_vocabulary_exists():
    if _lookup_disposition_type() is None:
        pytest.fail(
            "VALID_RED: lookup disposition vocabulary is absent; required "
            "values are NOT_FOUND, FOUND_VALID_BINDING, "
            "FOUND_CONFLICTING_BINDING"
        )


def test_c4b2004_write_disposition_vocabulary_exists():
    if _write_disposition_type() is None:
        pytest.fail(
            "VALID_RED: write disposition vocabulary is absent; required "
            "values are CREATED_CANONICAL_BINDING, EXISTING_VALID_BINDING, "
            "CONFLICTING_BINDING"
        )


def test_c4b2005_lookup_result_contract_exists():
    module = _adapter_module()
    result_type = module.LogicalBindingLookupResult
    binding_type = _binding_type()
    assert is_dataclass(result_type)
    assert tuple(field.name for field in fields(result_type)) == (
        "disposition",
        "binding",
    )
    hints = get_type_hints(result_type)
    assert hints["disposition"] is _lookup_disposition_type()
    assert hints["binding"] == binding_type | None
    assert result_type(_lookup_disposition_type().NOT_FOUND).binding is None


def test_c4b2006_lookup_result_is_immutable():
    module = _adapter_module()
    result = module.LogicalBindingLookupResult(
        module.LogicalBindingLookupDisposition.NOT_FOUND
    )
    with pytest.raises(FrozenInstanceError):
        result.disposition = module.LogicalBindingLookupDisposition.FOUND_VALID_BINDING
    with pytest.raises(FrozenInstanceError):
        result.binding = _binding()


def test_c4b2007_not_found_cannot_carry_binding():
    module = _adapter_module()
    assert module.LogicalBindingLookupResult(
        module.LogicalBindingLookupDisposition.NOT_FOUND
    ).binding is None
    with pytest.raises(ValueError, match="NOT_FOUND cannot carry"):
        module.LogicalBindingLookupResult(
            module.LogicalBindingLookupDisposition.NOT_FOUND,
            _binding(),
        )


def test_c4b2008_found_lookup_requires_binding():
    module = _adapter_module()
    binding = _binding()
    for disposition in (
        module.LogicalBindingLookupDisposition.FOUND_VALID_BINDING,
        module.LogicalBindingLookupDisposition.FOUND_CONFLICTING_BINDING,
    ):
        assert module.LogicalBindingLookupResult(disposition, binding).binding == binding
        with pytest.raises(ValueError, match="requires binding"):
            module.LogicalBindingLookupResult(disposition)


def test_c4b2009_write_result_contract_exists():
    module = _adapter_module()
    result_type = module.LogicalBindingWriteResult
    binding_type = _binding_type()
    assert is_dataclass(result_type)
    assert tuple(field.name for field in fields(result_type)) == (
        "disposition",
        "binding",
    )
    hints = get_type_hints(result_type)
    assert hints["disposition"] is _write_disposition_type()
    assert hints["binding"] is binding_type
    binding = _binding()
    for disposition in module.LogicalBindingWriteDisposition:
        assert result_type(disposition, binding).binding == binding


def test_c4b2010_write_result_is_immutable():
    module = _adapter_module()
    result = module.LogicalBindingWriteResult(
        module.LogicalBindingWriteDisposition.CREATED_CANONICAL_BINDING,
        _binding(),
    )
    with pytest.raises(FrozenInstanceError):
        result.disposition = module.LogicalBindingWriteDisposition.EXISTING_VALID_BINDING
    with pytest.raises(FrozenInstanceError):
        result.binding = _binding()


def test_c4b2011_lookup_and_write_vocabularies_are_separate():
    lookup_type = _lookup_disposition_type()
    write_type = _write_disposition_type()
    if lookup_type is None or write_type is None:
        pytest.skip("NOT_YET_REACHED: one or both disposition boundaries are absent")
    assert {item.value for item in lookup_type} != {item.value for item in write_type}


def test_c4b2012_binding_does_not_allocate_request_ids():
    source = inspect.getsource(_binding_type())
    assert all(token not in source.lower() for token in ("uuid", "random", "hash"))
    assert _binding().effect_request_id == "request-1"


def test_c4b2013_types_have_no_database_behavior():
    source = inspect.getsource(_adapter_module())
    forbidden = (
        "psycopg",
        "EffectApplicationLedger",
        "execute(",
        "handa_live.effect_request",
        "transaction",
        "cursor",
    )
    assert all(token not in source for token in forbidden)


def test_c4b2014_no_public_logical_lookup_behavior_exists():
    assert not _has_logical_lookup_capability()


def test_c4b2015_no_canonical_binding_write_behavior_exists():
    assert not _has_c4_binding_write_capability()


def test_c4b2016_no_c4c_data_is_present_in_binding_types():
    source = inspect.getsource(_adapter_module())
    forbidden = (
        "AppliedEffectReplayRecord",
        "receipt_id",
        "receipt_hash",
        "PositionEffectResult",
        "resulting_quantity",
        "remaining_quantity",
        "execution_extent_identity",
    )
    assert all(token not in source for token in forbidden)


def test_c4b2017_no_c4d_or_oa005_authority_is_present():
    source = inspect.getsource(_adapter_module())
    forbidden = (
        "claim_application",
        "mark_applied",
        "outer transaction",
        "retry",
        "resubmit",
        "order_market",
        "PositionEffectAuthority",
    )
    assert all(token not in source for token in forbidden)


def test_c4b2018_generic_ledger_semantics_are_preserved():
    ledger_module = _ledger_module()
    signature = inspect.signature(ledger_module.EffectApplicationLedger.create_effect_request)
    annotation = signature.parameters["effect_type"].annotation
    assert annotation in (str, "str")
    source = inspect.getsource(ledger_module)
    assert "operational_effect_adapter" not in source
    assert "EffectType" not in source
