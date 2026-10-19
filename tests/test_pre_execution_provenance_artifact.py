"""Expected-RED contracts for immutable 2B8B provenance artifacts."""

from importlib import import_module
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from core.market import governed_market_observation as market_observation


def _artifact_contract():
    try:
        return import_module("core.execution.pre_execution_provenance_artifact")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "EXPECTED_CONTRACT_RED::pre-execution provenance artifact module is "
            f"missing; missing={exc.name}"
        )


def _manifest_store_contract():
    try:
        return import_module("core.persistence.governance_artifact_manifest_store")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "EXPECTED_CONTRACT_RED::governance manifest store module is missing; "
            f"missing={exc.name}"
        )


def test_deterministic_provenance_identity_contract():
    module = _artifact_contract()

    assert hasattr(module, "PreExecutionProvenanceArtifact")
    assert hasattr(module, "provenance_artifact_id")
    assert getattr(module, "provenance_artifact_id")(
        {"symbol": "HYPEUSDC", "side": "BUY", "source_timestamp": "t1"}
    )


def test_provenance_identity_changes_with_timestamp_or_manifest_digest():
    module = _artifact_contract()
    identity = getattr(module, "provenance_artifact_id")
    base = {
        "symbol": "HYPEUSDC",
        "side": "BUY",
        "source_timestamp": "2026-01-01T00:00:00Z",
        "strategy_manifest_digest": "strategy-a",
    }

    assert identity(base) != identity({**base, "source_timestamp": "2026-01-01T00:01:00Z"})
    assert identity(base) != identity({**base, "strategy_manifest_digest": "strategy-b"})


def test_binding_status_and_static_dynamic_separation_contract():
    module = _artifact_contract()

    assert hasattr(module, "BindingStatus")
    assert {"BOUND", "UNBOUND", "INCOMPLETE"} <= {
        member.value for member in getattr(module, "BindingStatus")
    }
    assert hasattr(module, "build_provenance_artifact")


def test_manifest_store_is_read_only_at_runtime_and_rejects_secret_material():
    module = _manifest_store_contract()

    assert hasattr(module, "GovernanceArtifactManifestStore")
    store = getattr(module, "GovernanceArtifactManifestStore")
    assert not hasattr(store, "create_manifest")
    assert not hasattr(store, "approve_manifest")
    assert hasattr(module, "canonical_manifest_digest")
    assert hasattr(module, "SECRET_FIELDS")


def test_provenance_artifact_contract_is_immutable_and_decimal_safe():
    module = _artifact_contract()
    artifact = getattr(module, "PreExecutionProvenanceArtifact")
    assert getattr(artifact, "__dataclass_params__").frozen is True
    fields = artifact.__dataclass_fields__
    for field_name in (
        "candidate_id",
        "symbol",
        "side",
        "source_group_digests",
        "source_group_intervals",
        "requested_quote_amount",
        "binding_status",
        "canonical_semantic_digest",
    ):
        assert field_name in fields


def _dynamic_groups(*, include_all=True):
    values = {
        "PRICE_TECHNICAL": datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        "SELECTION_RADAR": datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
        "MARKET_CONTEXT": datetime(2026, 1, 1, 0, 3, tzinfo=timezone.utc),
    }
    if not include_all:
        values.pop("SELECTION_RADAR")
    return values


def _manifest_refs():
    return {
        name: f"{name.lower()}-manifest"
        for name in ("STRATEGY", "POLICY", "RISK", "CONFIGURATION", "FRESHNESS")
    }


def _build(module, **overrides):
    values = {
        "symbol": "HYPEUSDC",
        "candidate_evidence_identity": "candidate-2b8b",
        "source_group_timestamps": _dynamic_groups(),
        "source_group_digests": {
            "PRICE_TECHNICAL": "price-digest",
            "SELECTION_RADAR": "radar-digest",
            "MARKET_CONTEXT": "context-digest",
        },
        "source_group_intervals": {
            "PRICE_TECHNICAL": "1m",
            "SELECTION_RADAR": "5m",
            "MARKET_CONTEXT": "15m",
        },
        "ticker_value": Decimal("100.25"),
        "ticker_application_receipt_at": datetime(
            2026, 1, 1, 0, 4, tzinfo=timezone.utc
        ),
        "requested_quote_amount": Decimal("41.41"),
        "dynamic_policy_evidence": {"policy": {"thresholds": [1, 2]}},
        "static_manifest_references": _manifest_refs(),
    }
    values.update(overrides)
    return module.build_provenance_artifact(**values)


def test_single_price_group_never_satisfies_complete_dynamic_binding():
    module = _artifact_contract()

    artifact = _build(
        module,
        source_group_timestamps={"PRICE_TECHNICAL": _dynamic_groups()["PRICE_TECHNICAL"]},
        source_group_digests={"PRICE_TECHNICAL": "price-digest"},
        source_group_intervals={"PRICE_TECHNICAL": "1m"},
    )

    assert artifact.binding_status.value == "INCOMPLETE", (
        "EXPECTED_CONTRACT_RED::all three trustworthy source groups are required"
    )


def test_missing_selection_timestamp_is_not_copied_from_price_and_blocks_bound():
    module = _artifact_contract()
    price_time = _dynamic_groups()["PRICE_TECHNICAL"]
    artifact = _build(
        module,
        source_group_timestamps={"PRICE_TECHNICAL": price_time},
        source_group_digests={"PRICE_TECHNICAL": "price-digest"},
        source_group_intervals={"PRICE_TECHNICAL": "1m"},
    )

    assert artifact.source_group_timestamps.get("SELECTION_RADAR") is None
    assert artifact.source_group_timestamps.get("SELECTION_RADAR") != price_time
    assert artifact.binding_status.value == "INCOMPLETE", (
        "EXPECTED_CONTRACT_RED::missing SELECTION_RADAR evidence was allowed to bind"
    )


def test_missing_market_context_timestamp_is_not_copied_from_price_and_blocks_bound():
    module = _artifact_contract()
    price_time = _dynamic_groups()["PRICE_TECHNICAL"]
    artifact = _build(
        module,
        source_group_timestamps={"PRICE_TECHNICAL": price_time},
        source_group_digests={"PRICE_TECHNICAL": "price-digest"},
        source_group_intervals={"PRICE_TECHNICAL": "1m"},
    )

    assert artifact.source_group_timestamps.get("MARKET_CONTEXT") is None
    assert artifact.source_group_timestamps.get("MARKET_CONTEXT") != price_time
    assert artifact.binding_status.value == "INCOMPLETE", (
        "EXPECTED_CONTRACT_RED::missing MARKET_CONTEXT evidence was allowed to bind"
    )


def test_missing_required_group_wins_over_all_static_manifest_references():
    module = _artifact_contract()

    artifact = _build(
        module,
        source_group_timestamps=_dynamic_groups(include_all=False),
    )

    assert artifact.binding_status.value == "INCOMPLETE", (
        "EXPECTED_CONTRACT_RED::incomplete dynamic provenance must win over manifests"
    )


@pytest.mark.parametrize(
    "closure_statuses, server_times, case_id",
    [
        ({}, {"PRICE_TECHNICAL": datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc)}, "missing-status"),
        (
            {"PRICE_TECHNICAL": market_observation.CLOSED},
            {},
            "missing-server-time",
        ),
        (
            {"PRICE_TECHNICAL": market_observation.CLOSED_UNPROVEN},
            {},
            "closed-unproven",
        ),
        ({"PRICE_TECHNICAL": market_observation.OPEN}, {}, "open"),
    ],
)
def test_price_technical_requires_trustworthy_closed_proof(
    closure_statuses, server_times, case_id
):
    artifact = _build(
        _artifact_contract(),
        candidate_evidence_identity=f"closure-{case_id}",
        source_group_closure_statuses=closure_statuses,
        source_group_server_times=server_times,
    )

    assert artifact.binding_status.value == "INCOMPLETE", (
        "EXPECTED_CONTRACT_RED::MISSING_CLOSURE_PROOF_BOUND"
    )


def test_same_close_time_with_different_closure_proof_remains_distinguishable():
    module = _artifact_contract()
    close_time = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
    closed = _build(
        module,
        source_group_timestamps={
            "PRICE_TECHNICAL": close_time,
            "SELECTION_RADAR": close_time,
            "MARKET_CONTEXT": close_time,
        },
        source_group_digests={
            "PRICE_TECHNICAL": "kline-CLOSED-server-proven",
            "SELECTION_RADAR": "radar-digest",
            "MARKET_CONTEXT": "context-digest",
        },
    )
    unproven = _build(
        module,
        source_group_timestamps={
            "PRICE_TECHNICAL": close_time,
            "SELECTION_RADAR": close_time,
            "MARKET_CONTEXT": close_time,
        },
        source_group_digests={
            "PRICE_TECHNICAL": "kline-CLOSED_UNPROVEN-server-missing",
            "SELECTION_RADAR": "radar-digest",
            "MARKET_CONTEXT": "context-digest",
        },
    )

    assert closed.candidate_id != unproven.candidate_id
    assert closed.canonical_semantic_digest != unproven.canonical_semantic_digest


def test_nested_caller_mutation_cannot_change_record_or_semantic_digest():
    module = _artifact_contract()
    nested = {"policy": {"thresholds": [1, 2]}}
    artifact = _build(module, dynamic_policy_evidence=nested)
    record_before = deepcopy(artifact.as_record())
    digest_before = artifact.canonical_semantic_digest

    nested["policy"]["thresholds"].append(3)

    assert artifact.as_record() == record_before, (
        "EXPECTED_CONTRACT_RED::artifact retained caller-owned nested mutability"
    )
    assert artifact.canonical_semantic_digest == digest_before, (
        "EXPECTED_CONTRACT_RED::nested mutation changed semantic identity"
    )


def test_ticker_application_receipt_at_participates_in_semantic_identity():
    module = _artifact_contract()
    first = _build(
        module,
        ticker_application_receipt_at=datetime(
            2026, 1, 1, 0, 4, tzinfo=timezone.utc
        ),
    )
    second = _build(
        module,
        ticker_application_receipt_at=datetime(
            2026, 1, 1, 0, 5, tzinfo=timezone.utc
        ),
    )

    assert first.candidate_id != second.candidate_id, (
        "EXPECTED_CONTRACT_RED::ticker receipt is absent from 2B8B identity"
    )
    assert first.canonical_semantic_digest != second.canonical_semantic_digest


def test_closed_vs_unproven_kline_status_survives_artifact_and_as_record():
    close_time = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
    verified_server_time = datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc)
    kline = [
        datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        "99.0",
        "101.0",
        "98.0",
        "100.25",
        "12.5",
        close_time,
        "0",
        "0",
        "0",
        "0",
        "0",
    ]
    closed_observation = market_observation.capture_kline_observation(
        kline,
        symbol="HYPEUSDC",
        interval="1m",
        server_time=verified_server_time,
    )

    def unavailable_server_time():
        raise market_observation.BinanceServerTimeUnavailable("unverified")

    unproven_observation = market_observation.capture_kline_observation(
        kline,
        symbol="HYPEUSDC",
        interval="1m",
        server_time_provider=unavailable_server_time,
    )

    assert closed_observation.close_status == market_observation.CLOSED
    assert unproven_observation.close_status == market_observation.CLOSED_UNPROVEN
    assert closed_observation.close_time == unproven_observation.close_time == close_time

    common = {
        "source_group_timestamps": {
            "PRICE_TECHNICAL": close_time,
            "SELECTION_RADAR": datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
            "MARKET_CONTEXT": datetime(2026, 1, 1, 0, 3, tzinfo=timezone.utc),
        },
    }
    closed_artifact = _build(
        _artifact_contract(),
        **common,
        source_group_digests={
            "SELECTION_RADAR": "radar-digest",
            "MARKET_CONTEXT": "context-digest",
            "PRICE_TECHNICAL": closed_observation.canonical_digest,
        },
    )
    unproven_artifact = _build(
        _artifact_contract(),
        **common,
        source_group_digests={
            "SELECTION_RADAR": "radar-digest",
            "MARKET_CONTEXT": "context-digest",
            "PRICE_TECHNICAL": unproven_observation.canonical_digest,
        },
    )

    assert closed_artifact.candidate_id != unproven_artifact.candidate_id
    assert closed_artifact.canonical_semantic_digest != (
        unproven_artifact.canonical_semantic_digest
    )
    closed_record = closed_artifact.as_record()
    unproven_record = unproven_artifact.as_record()
    assert closed_record.get("source_group_closure_statuses", {}).get(
        "PRICE_TECHNICAL"
    ) == market_observation.CLOSED, (
        "EXPECTED_CONTRACT_RED::CLOSED proof was lost before as_record"
    )
    assert unproven_record.get("source_group_closure_statuses", {}).get(
        "PRICE_TECHNICAL"
    ) == market_observation.CLOSED_UNPROVEN, (
        "EXPECTED_CONTRACT_RED::CLOSED_UNPROVEN proof was lost before as_record"
    )


def _complete_dynamic_contract():
    close_time = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
    return {
        "source_group_closure_statuses": {
            "PRICE_TECHNICAL": market_observation.CLOSED,
            "SELECTION_RADAR": "CAUSAL_ONLY",
            "MARKET_CONTEXT": "CAUSAL_ONLY",
        },
        "source_group_server_times": {
            "PRICE_TECHNICAL": datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
        },
        "source_group_constituent_digests": {
            "PRICE_TECHNICAL": ("price-observation",),
            "SELECTION_RADAR": ("radar-observation",),
            "MARKET_CONTEXT": ("context-observation",),
        },
        "source_group_intervals": {
            "PRICE_TECHNICAL": {"oldest": close_time, "newest": close_time},
            "SELECTION_RADAR": {"oldest": close_time, "newest": close_time},
            "MARKET_CONTEXT": {"oldest": close_time, "newest": close_time},
        },
    }


def _structured_manifest_refs(*, wrong_role=False, duplicate=False, secret=False):
    refs = {}
    for name in ("STRATEGY", "POLICY", "RISK", "CONFIGURATION", "FRESHNESS"):
        artifact_type = "POLICY" if wrong_role and name == "STRATEGY" else name
        artifact_id = "same-manifest" if duplicate else f"{name.lower()}-manifest"
        payload = {"threshold": 1}
        if secret and name == "POLICY":
            payload = {"api_key": "must-not-bind"}
        refs[name] = {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "artifact_version": "v1",
            "canonical_payload": payload,
            "canonical_payload_digest": "digest-v1",
            "schema_version": "schema-v1",
            "contract_version": "contract-v1",
        }
    return refs


def _valid_manifest_refs():
    from core.persistence.governance_artifact_manifest_store import (
        canonical_manifest_digest,
    )

    refs = {}
    for name in ("STRATEGY", "POLICY", "RISK", "CONFIGURATION", "FRESHNESS"):
        payload = {"role": name, "fixture": "post-final-audit"}
        refs[name] = {
            "artifact_id": f"bound-{name.lower()}",
            "artifact_type": name,
            "artifact_version": "v1",
            "canonical_payload": payload,
            "canonical_payload_digest": canonical_manifest_digest(payload),
            "schema_version": "schema-v1",
            "contract_version": "contract-v1",
        }
    return refs


def _fully_complete_dynamic_contract():
    times = {
        "PRICE_TECHNICAL": datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        "SELECTION_RADAR": datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
        "MARKET_CONTEXT": datetime(2026, 1, 1, 0, 3, tzinfo=timezone.utc),
    }
    identities = {
        group: f"{group}:HYPEUSDC:complete"
        for group in ("PRICE_TECHNICAL", "SELECTION_RADAR", "MARKET_CONTEXT")
    }
    constituents = {
        group: [
            {
                "constituent_id": f"{group.lower()}:observation",
                "source": "fixture",
                "semantic_digest": f"{group.lower()}-constituent",
                "trustworthy_market_time": True,
                "required_for_completeness": True,
            }
        ]
        for group in identities
    }
    intervals = {
        group: {"oldest": value, "newest": value}
        for group, value in times.items()
    }
    values = {
        "source_group_timestamps": times,
        "source_group_digests": {},
        "source_group_intervals": intervals,
        "source_group_closure_statuses": {
            "PRICE_TECHNICAL": market_observation.CLOSED,
            "SELECTION_RADAR": market_observation.CLOSED,
            "MARKET_CONTEXT": market_observation.CLOSED,
        },
        "source_group_server_times": {
            group: value.replace(second=value.second + 1)
            for group, value in times.items()
        },
        "source_group_constituent_digests": {
            group: (records[0]["semantic_digest"],)
            for group, records in constituents.items()
        },
        "source_group_identities": identities,
        "source_group_constituents": constituents,
        "source_group_missing_evidence": {group: () for group in identities},
        "source_group_trust": {group: "TRUSTED" for group in identities},
    }
    values["source_group_digests"] = {
        group: market_observation.canonical_group_digest(
            group_type=group,
            group_identity=identities[group],
            constituents=constituents[group],
            market_oldest=times[group],
            market_newest=times[group],
            missing_evidence=(),
            trust_class="TRUSTED",
        )
        for group in identities
    }
    return values


@pytest.mark.parametrize(
    "condition",
    [
        "missing_group_identity",
        "empty_constituents",
        "constituent_without_semantic_digest",
        "missing_group_interval",
        "interval_missing_oldest",
        "interval_missing_newest",
        "non_empty_missing_evidence",
        "market_dependent_without_trustworthy_ancestry",
        "invalid_trust_classification",
        "non_reproducible_group_digest",
    ],
)
def test_full_dynamic_completeness_rejects_each_falsified_required_condition(condition):
    values = _fully_complete_dynamic_contract()
    group = "SELECTION_RADAR"
    if condition == "missing_group_identity":
        values["source_group_identities"].pop(group)
    elif condition == "empty_constituents":
        values["source_group_constituents"][group] = []
    elif condition == "constituent_without_semantic_digest":
        values["source_group_constituents"][group][0].pop("semantic_digest")
    elif condition == "missing_group_interval":
        values["source_group_intervals"].pop(group)
    elif condition == "interval_missing_oldest":
        values["source_group_intervals"][group] = {
            "newest": values["source_group_timestamps"][group]
        }
    elif condition == "interval_missing_newest":
        values["source_group_intervals"][group] = {
            "oldest": values["source_group_timestamps"][group]
        }
    elif condition == "non_empty_missing_evidence":
        values["source_group_missing_evidence"][group] = ("required-input-missing",)
    elif condition == "market_dependent_without_trustworthy_ancestry":
        values["source_group_constituents"][group][0][
            "trustworthy_market_time"
        ] = False
    elif condition == "invalid_trust_classification":
        values["source_group_trust"][group] = "UNTRUSTED"
    elif condition == "non_reproducible_group_digest":
        values["source_group_digests"][group] = "tampered-group-digest"

    artifact = _build(
        _artifact_contract(),
        static_manifest_references=_valid_manifest_refs(),
        **values,
    )

    assert artifact.binding_status.value == "INCOMPLETE", (
        "EXPECTED_CONTRACT_RED::FULL_DYNAMIC_COMPLETENESS::" + condition
    )


def test_full_dynamic_group_requires_constituents_and_missing_evidence_contract():
    values = _complete_dynamic_contract()
    values["source_group_constituent_digests"]["SELECTION_RADAR"] = ()
    artifact = _build(_artifact_contract(), **values)

    assert artifact.binding_status.value == "INCOMPLETE", (
        "EXPECTED_CONTRACT_RED::empty required group constituents were allowed to bind"
    )


@pytest.mark.parametrize(
    "kwargs, identity",
    [
        ({"wrong_role": True}, "MANIFEST_ROLE_MISMATCH"),
        ({"duplicate": True}, "MANIFEST_DUPLICATE_ROLE_REUSE"),
        ({"secret": True}, "MANIFEST_SECRET_PAYLOAD"),
    ],
)
def test_manifest_binding_rejects_structural_role_and_secret_contracts(kwargs, identity):
    values = _complete_dynamic_contract()
    artifact = _build(
        _artifact_contract(),
        static_manifest_references=_structured_manifest_refs(**kwargs),
        **values,
    )

    assert artifact.binding_status.value != "BOUND", (
        f"EXPECTED_CONTRACT_RED::{identity}"
    )


def test_manifest_digest_mismatch_fails_content_binding():
    values = _complete_dynamic_contract()
    refs = _structured_manifest_refs()
    refs["POLICY"]["canonical_payload_digest"] = "incorrect-digest"
    artifact = _build(
        _artifact_contract(),
        static_manifest_references=refs,
        **values,
    )

    assert artifact.binding_status.value != "BOUND", (
        "EXPECTED_CONTRACT_RED::MANIFEST_CANONICAL_DIGEST_MISMATCH"
    )


def test_static_manifest_content_identity_is_retained_per_role():
    values = _complete_dynamic_contract()
    artifact = _build(
        _artifact_contract(),
        static_manifest_references=_structured_manifest_refs(),
        **values,
    )

    strategy = artifact.static_manifest_references["STRATEGY"]
    assert strategy["artifact_type"] == "STRATEGY"
    assert strategy["canonical_payload_digest"] == "digest-v1"
    assert strategy["schema_version"] == "schema-v1"
    assert strategy["contract_version"] == "contract-v1"


def test_real_price_technical_trust_class_is_accepted_by_dynamic_completeness():
    from core.scanner.technical_scanner import TechnicalScanner

    class BinanceClient:
        def get_klines(self, *, symbol, interval, limit):
            base = datetime(2026, 1, 1, tzinfo=timezone.utc)
            return [
                [
                    (base.timestamp() + index * 60) * 1000,
                    "100",
                    "101",
                    "99",
                    str(100 + index * 0.01),
                    "10",
                    (base.timestamp() + (index + 1) * 60 - 1) * 1000,
                    "1000",
                    10,
                    "5",
                    "500",
                    "0",
                ]
                for index in range(limit)
            ]

        def get_server_time(self):
            return {"serverTime": datetime(2026, 1, 1, 2, tzinfo=timezone.utc)}

        def get_symbol_ticker(self, *, symbol):
            return {"price": "101.25"}

    real_provenance = TechnicalScanner(BinanceClient()).analyze_symbol(
        "HYPEUSDC", interval="1m", limit=100
    )["governed_provenance"]
    values = _fully_complete_dynamic_contract()
    for key in (
        "source_group_timestamps",
        "source_group_digests",
        "source_group_intervals",
        "source_group_closure_statuses",
        "source_group_server_times",
        "source_group_constituent_digests",
        "source_group_identities",
        "source_group_constituents",
        "source_group_missing_evidence",
        "source_group_trust",
    ):
        values[key]["PRICE_TECHNICAL"] = real_provenance[key]["PRICE_TECHNICAL"]

    artifact = _build(
        _artifact_contract(),
        static_manifest_references=_valid_manifest_refs(),
        **values,
    )
    assert values["source_group_trust"]["PRICE_TECHNICAL"] == (
        "TRUSTED_MARKET_TIME"
    )
    assert artifact.binding_status.value == "BOUND", (
        "EXPECTED_CONTRACT_RED::REAL_PRICE_TECHNICAL_TRUST_CLASS_REJECTED"
    )


def _real_mixed_price_technical_artifact():
    from core.scanner.technical_scanner import TechnicalScanner
    from core.slot_controller import SlotController

    class BinanceClient:
        def get_klines(self, *, symbol, interval, limit):
            base = datetime(2026, 1, 1, tzinfo=timezone.utc)
            return [
                [
                    (base.timestamp() + index * 60) * 1000,
                    "100",
                    "101",
                    "99",
                    str(100 + index * 0.01),
                    "10",
                    (base.timestamp() + (index + 1) * 60 - 1) * 1000,
                    "1000",
                    10,
                    "5",
                    "500",
                    "0",
                ]
                for index in range(limit)
            ]

        def get_server_time(self):
            return {"serverTime": datetime(2026, 1, 1, 2, tzinfo=timezone.utc)}

        def get_symbol_ticker(self, *, symbol):
            return {"price": "101.25"}

    client = BinanceClient()
    opportunity = TechnicalScanner(client).analyze_symbol(
        "HYPEUSDC", interval="1m", limit=100
    )
    snapshot = SlotController([], client=client)._build_snapshot_from_opportunity(
        opportunity
    )
    real_provenance = deepcopy(getattr(snapshot, "_governed_provenance"))
    values = _fully_complete_dynamic_contract()
    for key in (
        "source_group_timestamps",
        "source_group_digests",
        "source_group_intervals",
        "source_group_closure_statuses",
        "source_group_server_times",
        "source_group_constituent_digests",
        "source_group_identities",
        "source_group_constituents",
        "source_group_missing_evidence",
        "source_group_trust",
    ):
        values[key][market_observation.PRICE_TECHNICAL] = real_provenance[key][
            market_observation.PRICE_TECHNICAL
        ]
    artifact = _build(
        _artifact_contract(),
        static_manifest_references=_valid_manifest_refs(),
        **values,
    )
    return artifact, values


def test_real_mixed_price_technical_with_causal_ticker_is_expected_red():
    artifact, values = _real_mixed_price_technical_artifact()
    records = values["source_group_constituents"][market_observation.PRICE_TECHNICAL]
    kline = next(
        record
        for record in records
        if record.get("constituent_kind")
        == market_observation.MARKET_OBSERVATION_CONSTITUENT
    )
    ticker = next(
        record
        for record in records
        if record.get("constituent_kind")
        == market_observation.CAUSAL_DERIVED_CONSTITUENT
    )

    assert values["source_group_trust"][market_observation.PRICE_TECHNICAL] == (
        "TRUSTED_MARKET_TIME"
    )
    assert kline["trustworthy_market_time"] is True
    assert ticker["trustworthy_market_time"] is False
    assert ticker["application_receipt_at"] > values["source_group_intervals"][
        market_observation.PRICE_TECHNICAL
    ]["newest"]
    assert values["source_group_timestamps"][market_observation.PRICE_TECHNICAL] == values[
        "source_group_intervals"
    ][market_observation.PRICE_TECHNICAL]["newest"]
    assert ticker["application_receipt_at"] != values["source_group_timestamps"][
        market_observation.PRICE_TECHNICAL
    ]
    assert artifact.binding_status.value == "BOUND", (
        "EXPECTED_CONTRACT_RED::MIXED_PRICE_TECHNICAL_CAUSAL_TICKER_REJECTED"
    )


@pytest.mark.parametrize(
    "mutation, case_id",
    [
        ("open", "OPEN_KLINE_FAIL_CLOSED"),
        ("closed_unproven", "CLOSED_UNPROVEN_FAIL_CLOSED"),
        ("missing_server_time", "MISSING_SERVER_TIME_FAIL_CLOSED"),
        ("untrusted_market_observation", "UNTRUSTED_MARKET_OBSERVATION_FAIL_CLOSED"),
    ],
)
def test_real_mixed_price_technical_negative_falsifiers_fail_closed(mutation, case_id):
    _artifact, values = _real_mixed_price_technical_artifact()
    if mutation == "open":
        values["source_group_closure_statuses"][market_observation.PRICE_TECHNICAL] = (
            market_observation.OPEN
        )
    elif mutation == "closed_unproven":
        values["source_group_closure_statuses"][market_observation.PRICE_TECHNICAL] = (
            market_observation.CLOSED_UNPROVEN
        )
    elif mutation == "missing_server_time":
        values["source_group_server_times"][market_observation.PRICE_TECHNICAL] = None
    elif mutation == "untrusted_market_observation":
        records = values["source_group_constituents"][market_observation.PRICE_TECHNICAL]
        kline = next(
            record
            for record in records
            if record.get("constituent_kind")
            == market_observation.MARKET_OBSERVATION_CONSTITUENT
        )
        kline["trustworthy_market_time"] = False
        interval = values["source_group_intervals"][market_observation.PRICE_TECHNICAL]
        values["source_group_digests"][market_observation.PRICE_TECHNICAL] = (
            market_observation.canonical_group_digest(
                group_type=market_observation.PRICE_TECHNICAL,
                group_identity=values["source_group_identities"][
                    market_observation.PRICE_TECHNICAL
                ],
                constituents=records,
                market_oldest=interval["oldest"],
                market_newest=interval["newest"],
                missing_evidence=(),
                trust_class="TRUSTED_MARKET_TIME",
            )
        )
    artifact = _build(
        _artifact_contract(),
        static_manifest_references=_valid_manifest_refs(),
        **values,
    )
    assert artifact.binding_status.value == "INCOMPLETE", (
        f"EXPECTED_CONTRACT_RED::{case_id}"
    )
