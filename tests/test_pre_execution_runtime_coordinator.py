from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
import inspect
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.capital_engine.capital_allocator import AllocationDecision
from core.decision.decision_engine import BuySignal, DecisionEngine, MarketSnapshot
from core.risk.risk_manager import RiskEvaluation
from core.radar.market_radar_engine import MarketRadarEngine
from core.market.governed_market_observation import (
    MARKET_CONTEXT,
    PRICE_TECHNICAL,
    SELECTION_RADAR,
    canonical_group_digest,
)
from core.governed_runtime_composition import (
    AuthoritySnapshot,
    BootResult,
    GOVERNED_INFRASTRUCTURE_READY,
    OBSERVE_ONLY,
    RuntimeCompositionConfig,
)
from core.execution.pre_execution_runtime_coordinator import (
    LINEAGE_CONFLICT,
    OBSERVE_ONLY_NOT_EVALUATED,
    PreExecutionRuntimeCoordinator,
    PreExecutionRuntimeProposal,
    PreExecutionRuntimeResult,
    TECHNICAL_FAILURE,
)


def _proposal(provenance=None):
    snapshot = MarketSnapshot(
        pair="HYPEUSDC",
        price=100.0,
        rsi=55.0,
        ema_fast=101.0,
        ema_slow=99.0,
        volume_ratio=2.0,
        atr=0.3,
        trend="UPTREND",
        momentum="BULLISH",
        market_state="TRADE_OK",
    )
    if provenance is not None:
        setattr(snapshot, "_governed_provenance", provenance)
    signal = BuySignal(
        pair="HYPEUSDC",
        entry_price=100.0,
        allocated_usdc=41.41,
        stop_loss=99.0,
        take_profit=102.0,
        confidence=0.9,
        reasons=["TEST_CANDIDATE"],
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    return PreExecutionRuntimeProposal.from_buy_signal(snapshot, signal).bind_slot("1")


def _trusted_provenance(*, marker="a", include_manifests=True):
    times = {
        PRICE_TECHNICAL: datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        SELECTION_RADAR: datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
        MARKET_CONTEXT: datetime(2026, 1, 1, 0, 3, tzinfo=timezone.utc),
    }
    identities = {
        group: f"{group}:HYPEUSDC:{marker}" for group in times
    }
    constituents = {
        group: [{
            "constituent_id": f"{group.lower()}:observation:{marker}",
            "semantic_digest": f"{group.lower()}-observation-{marker}",
            "trustworthy_market_time": True,
            "required_for_completeness": True,
        }]
        for group in times
    }
    intervals = {
        group: {"oldest": value, "newest": value}
        for group, value in times.items()
    }
    provenance = {
        "source_group_timestamps": times,
        "source_group_digests": {
            group: canonical_group_digest(
                group_type=group,
                group_identity=identities[group],
                constituents=constituents[group],
                market_oldest=times[group],
                market_newest=times[group],
                trust_class="TRUSTED",
            )
            for group in times
        },
        "source_group_intervals": intervals,
        "source_group_closure_statuses": {
            group: "CLOSED" for group in times
        },
        "source_group_server_times": {
            group: value.replace(second=value.second + 1)
            for group, value in times.items()
        },
        "source_group_constituent_digests": {
            group: (constituents[group][0]["semantic_digest"],)
            for group in times
        },
        "source_group_identities": identities,
        "source_group_constituents": constituents,
        "source_group_missing_evidence": {group: () for group in times},
        "source_group_trust": {group: "TRUSTED" for group in times},
        "ticker_value": Decimal("100.25"),
        "ticker_application_receipt_at": datetime(
            2026, 1, 1, 0, 4, tzinfo=timezone.utc
        ),
    }
    if include_manifests:
        provenance["static_manifest_references"] = {
            name: f"runtime-fabricated-{name.lower()}"
            for name in ("STRATEGY", "POLICY", "RISK", "CONFIGURATION", "FRESHNESS")
        }
    return provenance


def _manifest_bound_envelope(prefix):
    envelope = {"venue": "MOCK", "account_scope": "TEST"}
    envelope.update(
        {
            f"{name.lower()}_manifest_id": f"{prefix}-{name.lower()}"
            for name in ("STRATEGY", "POLICY", "RISK", "CONFIGURATION", "FRESHNESS")
        }
    )
    return envelope


def _bound_artifact(proposal, prefix):
    return proposal.provenance_artifact.with_static_manifest_references(
        {name: _manifest_bound_envelope(prefix)[f"{name.lower()}_manifest_id"] for name in (
            "STRATEGY", "POLICY", "RISK", "CONFIGURATION", "FRESHNESS"
        )}
    )


def _runtime_proposal_after_radar_producer(provenance):
    """Run the live radar-to-candidate provenance path used before analysis."""

    opportunity = {
        "symbol": "HYPEUSDC",
        "governed_provenance": dict(provenance),
        "analysis": {"market_state": "TRADE_OK"},
        "market_context": {},
    }
    radar = object.__new__(MarketRadarEngine)
    radar.market_quality = {"state": "TEST"}
    radar._attach_governed_provenance([opportunity])

    snapshot = MarketSnapshot(
        pair="HYPEUSDC",
        price=100.0,
        rsi=55.0,
        ema_fast=101.0,
        ema_slow=99.0,
        volume_ratio=2.0,
        atr=0.3,
        trend="UPTREND",
        momentum="BULLISH",
        market_state="TRADE_OK",
    )
    setattr(snapshot, "_governed_provenance", opportunity["governed_provenance"])
    signal = BuySignal(
        pair="HYPEUSDC",
        entry_price=100.0,
        allocated_usdc=41.41,
        stop_loss=99.0,
        take_profit=102.0,
        confidence=0.9,
        reasons=["TEST_CANDIDATE"],
        timestamp=datetime(2026, 1, 1, 0, 30, tzinfo=timezone.utc),
    )
    proposal = PreExecutionRuntimeProposal.from_buy_signal(snapshot, signal)
    return proposal.bind_slot("1")


def _runtime_source_provenance(*, price_time, selection_time=None, context_time=None):
    timestamps = {PRICE_TECHNICAL: price_time}
    digests = {PRICE_TECHNICAL: "price-runtime"}
    intervals = {PRICE_TECHNICAL: {"oldest": price_time, "newest": price_time}}
    if selection_time is not None:
        timestamps[SELECTION_RADAR] = selection_time
        digests[SELECTION_RADAR] = "radar-runtime"
        intervals[SELECTION_RADAR] = {
            "oldest": selection_time,
            "newest": selection_time,
        }
    if context_time is not None:
        timestamps[MARKET_CONTEXT] = context_time
        digests[MARKET_CONTEXT] = "context-runtime"
        intervals[MARKET_CONTEXT] = {
            "oldest": context_time,
            "newest": context_time,
        }
    return {
        "source_group_timestamps": timestamps,
        "source_group_digests": digests,
        "source_group_intervals": intervals,
        "ticker_value": Decimal("100.25"),
        "ticker_application_receipt_at": datetime(
            2026, 1, 1, 0, 20, tzinfo=timezone.utc
        ),
    }


def test_proposal_materializes_immutable_decimal_boundary():
    proposal = _proposal()

    assert proposal.requested_quote_amount == Decimal("41.41")
    assert proposal.evidence.symbol == "HYPEUSDC"
    with pytest.raises(Exception):
        proposal.requested_quote_amount = Decimal("1")


def test_observe_only_does_not_construct_persistence_or_evaluator():
    calls = []

    def forbidden(*_args, **_kwargs):
        calls.append("called")
        raise AssertionError("OBSERVE_ONLY must not construct persistence")

    coordinator = PreExecutionRuntimeCoordinator(
        RuntimeCompositionConfig(None, None),
        BootResult(posture=OBSERVE_ONLY, reason="AUTHORITY_STATE_OBSERVE_ONLY"),
        persistence_coordinator_factory=forbidden,
        evaluator_factory=forbidden,
    )

    result = coordinator.evaluate(_proposal())

    assert result.disposition == OBSERVE_ONLY_NOT_EVALUATED
    assert result.intent_id is None
    assert result.pre_execution_decision_id is None
    assert calls == []
    coordinator.close()
    coordinator.close()


def test_runtime_identity_derivation_is_stable_and_attempt_sequence_is_one():
    proposal = _proposal()
    bound_artifact = _bound_artifact(proposal, "stable")
    first = PreExecutionRuntimeCoordinator.derive_identity(
        proposal,
        venue="MOCK",
        account_scope="TEST",
        provenance_artifact=bound_artifact,
    )
    second = PreExecutionRuntimeCoordinator.derive_identity(
        proposal,
        venue="MOCK",
        account_scope="TEST",
        provenance_artifact=bound_artifact,
    )

    assert first == second
    assert first.attempt_sequence == 1
    assert first.intent_id.startswith("2b8b-intent-")
    assert first.attempt_id.startswith("2b8b-attempt-")
    assert first.evaluation_request_id.startswith("2b8b-eval-")
    assert first.evaluation_request_digest


def test_2b8b_runtime_identity_is_bound_to_trusted_provenance_semantics():
    first_proposal = _proposal(_trusted_provenance(marker="a"))
    second_proposal = _proposal(_trusted_provenance(marker="b"))
    first_artifact = _bound_artifact(first_proposal, "same")
    second_artifact = _bound_artifact(second_proposal, "same")
    first = PreExecutionRuntimeCoordinator.derive_identity(
        first_proposal,
        venue="MOCK",
        account_scope="TEST",
        provenance_artifact=first_artifact,
    )
    second = PreExecutionRuntimeCoordinator.derive_identity(
        second_proposal,
        venue="MOCK",
        account_scope="TEST",
        provenance_artifact=second_artifact,
    )

    assert first.intent_id.startswith("2b8b-intent-"), (
        "EXPECTED_CONTRACT_RED::runtime identity still uses the 2B7 namespace"
    )
    assert first.attempt_id.startswith("2b8b-attempt-")
    assert first.evaluation_request_id.startswith("2b8b-eval-")
    assert first.intent_id != second.intent_id, (
        "EXPECTED_CONTRACT_RED::trusted provenance is absent from 2B8B lineage identity"
    )


def test_runtime_cannot_bind_static_manifests_fabricated_inside_snapshot_provenance():
    proposal = _proposal(_trusted_provenance(include_manifests=True))

    assert proposal.provenance_artifact.binding_status.value == "UNBOUND", (
        "EXPECTED_CONTRACT_RED::manifest binding must come from the active authority envelope"
    )


def test_runtime_producer_does_not_fabricate_missing_multisource_timestamps():
    price_time = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
    proposal = _runtime_proposal_after_radar_producer(
        _runtime_source_provenance(price_time=price_time)
    )
    artifact = proposal.provenance_artifact
    timestamps = dict(artifact.source_group_timestamps)

    assert timestamps.get(PRICE_TECHNICAL) == price_time
    assert artifact.static_manifest_references == {}
    assert timestamps.get(SELECTION_RADAR) is None, (
        "EXPECTED_CONTRACT_RED::RUNTIME_MULTISOURCE_TIMESTAMP_FABRICATION"
    )
    assert timestamps.get(MARKET_CONTEXT) is None, (
        "EXPECTED_CONTRACT_RED::RUNTIME_MULTISOURCE_TIMESTAMP_FABRICATION"
    )
    assert timestamps.get(SELECTION_RADAR) != price_time
    assert timestamps.get(MARKET_CONTEXT) != price_time
    assert timestamps.get(SELECTION_RADAR) != datetime(
        2026, 1, 1, 0, 20, tzinfo=timezone.utc
    )
    assert timestamps.get(MARKET_CONTEXT) != datetime(
        2026, 1, 1, 0, 20, tzinfo=timezone.utc
    )
    assert timestamps.get(SELECTION_RADAR) != datetime(
        2026, 1, 1, 0, 30, tzinfo=timezone.utc
    )
    assert timestamps.get(MARKET_CONTEXT) != datetime(
        2026, 1, 1, 0, 30, tzinfo=timezone.utc
    )
    assert artifact.binding_status.value == "INCOMPLETE", (
        "EXPECTED_CONTRACT_RED::RUNTIME_MULTISOURCE_TIMESTAMP_FABRICATION"
    )


def test_runtime_producer_marks_missing_multisource_evidence_incomplete():
    proposal = _runtime_proposal_after_radar_producer(
        _runtime_source_provenance(
            price_time=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
        )
    )
    binding_status = proposal.provenance_artifact.binding_status.value

    assert binding_status != "BOUND"
    assert binding_status == "INCOMPLETE", (
        "EXPECTED_CONTRACT_RED::RUNTIME_MULTISOURCE_TIMESTAMP_FABRICATION"
    )


def test_runtime_producer_preserves_distinct_multisource_timestamp_groups():
    price_a = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
    price_b = datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc)
    selection_time = datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc)
    context_time = datetime(2026, 1, 1, 0, 3, tzinfo=timezone.utc)

    first = _runtime_proposal_after_radar_producer(
        _runtime_source_provenance(
            price_time=price_a,
            selection_time=selection_time,
            context_time=context_time,
        )
    ).provenance_artifact
    second = _runtime_proposal_after_radar_producer(
        _runtime_source_provenance(
            price_time=price_b,
            selection_time=selection_time,
            context_time=context_time,
        )
    ).provenance_artifact

    first_timestamps = dict(first.source_group_timestamps)
    second_timestamps = dict(second.source_group_timestamps)
    assert first_timestamps.get(PRICE_TECHNICAL) == price_a
    assert first_timestamps.get(SELECTION_RADAR) == selection_time, (
        "EXPECTED_CONTRACT_RED::RUNTIME_MULTISOURCE_TIMESTAMP_FABRICATION"
    )
    assert first_timestamps.get(MARKET_CONTEXT) == context_time, (
        "EXPECTED_CONTRACT_RED::RUNTIME_MULTISOURCE_TIMESTAMP_FABRICATION"
    )
    assert second_timestamps.get(PRICE_TECHNICAL) == price_b
    assert second_timestamps.get(SELECTION_RADAR) == selection_time, (
        "EXPECTED_CONTRACT_RED::RUNTIME_MULTISOURCE_TIMESTAMP_FABRICATION"
    )
    assert second_timestamps.get(MARKET_CONTEXT) == context_time, (
        "EXPECTED_CONTRACT_RED::RUNTIME_MULTISOURCE_TIMESTAMP_FABRICATION"
    )
    assert first_timestamps.get(SELECTION_RADAR) == second_timestamps.get(
        SELECTION_RADAR
    )
    assert first_timestamps.get(MARKET_CONTEXT) == second_timestamps.get(
        MARKET_CONTEXT
    )


def test_lineage_scope_has_only_order_intent_and_submission_attempt_writes():
    from core.persistence.live_order_store import pre_execution_lineage_resource_scope

    scope = pre_execution_lineage_resource_scope()

    assert {resource.table for resource in scope.resources} == {
        "order_intent", "submission_attempt"
    }
    assert all(
        "exchange_order_id" not in resource.writable_columns
        and "transport_status" not in resource.writable_columns
        for resource in scope.resources
    )


def _ready_boot_result(active_envelope=None):
    return BootResult(
        posture=GOVERNED_INFRASTRUCTURE_READY,
        reason="TEST_ONLY",
        authority_snapshot=AuthoritySnapshot(
            state_s1={},
            active_envelope=active_envelope
            or {"venue": "MOCK", "account_scope": "TEST"},
            state_s2={},
        ),
    )


class _FakePersistenceCoordinator:
    def verify_ready(self):
        return None

    def transaction(self):
        class _Transaction:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def insert_returning(self, _table, values, columns):
                return {column: values.get(column) for column in columns}

        return _Transaction()

    def close(self):
        return None


class _TransactionCapableFakePersistenceCoordinator(_FakePersistenceCoordinator):
    pass


class _NoTransactionPersistenceCoordinator(_FakePersistenceCoordinator):
    transaction = None


class _RecordingProvenanceStore:
    def __init__(self):
        self.artifacts = []

    def persist(self, artifact):
        self.artifacts.append(artifact)
        return artifact.as_record()


def _coordinator_with_recording_provenance_store(envelope, recording_store):
    coordinator = PreExecutionRuntimeCoordinator(
        RuntimeCompositionConfig("postgresql://test", object()),
        _ready_boot_result(envelope),
        persistence_coordinator_factory=lambda *_args, **_kwargs: (
            _TransactionCapableFakePersistenceCoordinator()
        ),
        evaluator_factory=lambda _persistence: SimpleNamespace(),
    )
    coordinator._provenance_store = recording_store
    return coordinator


def test_lineage_uses_envelope_bound_provenance_identity_after_runtime_persistence():
    proposal = _proposal(_trusted_provenance(marker="same", include_manifests=False))
    first_store = _RecordingProvenanceStore()
    second_store = _RecordingProvenanceStore()
    first = _coordinator_with_recording_provenance_store(
        _manifest_bound_envelope("set-a"), first_store
    )
    second = _coordinator_with_recording_provenance_store(
        _manifest_bound_envelope("set-b"), second_store
    )

    first_artifact = first.persist_provenance_artifact(proposal)
    first_identity = first.derive_identity(
        proposal,
        venue="MOCK",
        account_scope="TEST",
        provenance_artifact=first_artifact,
    )
    second_artifact = second.persist_provenance_artifact(proposal)
    second_identity = second.derive_identity(
        proposal,
        venue="MOCK",
        account_scope="TEST",
        provenance_artifact=second_artifact,
    )

    assert first_store.artifacts[0].candidate_id != second_store.artifacts[0].candidate_id
    assert first_identity.intent_id != second_identity.intent_id, (
        "EXPECTED_CONTRACT_RED::LINEAGE_USES_PRE_BINDING_PROVENANCE"
    )
    assert first_identity.client_order_id != second_identity.client_order_id
    assert first_identity.attempt_id != second_identity.attempt_id
    assert first_identity.evaluation_request_id != second_identity.evaluation_request_id
    first.close()
    second.close()


def test_governed_provenance_persistence_without_transaction_fails_closed():
    coordinator = PreExecutionRuntimeCoordinator(
        RuntimeCompositionConfig("postgresql://test", object()),
        _ready_boot_result(_manifest_bound_envelope("set-a")),
        persistence_coordinator_factory=lambda *_args, **_kwargs: _NoTransactionPersistenceCoordinator(),
        evaluator_factory=lambda _persistence: SimpleNamespace(),
    )

    with pytest.raises(RuntimeError, match="transaction|persistence"):
        coordinator.persist_provenance_artifact(
            _proposal(_trusted_provenance(marker="durability", include_manifests=False))
        )
    coordinator.close()


def test_persistence_initialization_failure_is_technical_and_authority_free():
    def failing_factory(*_args, **_kwargs):
        raise RuntimeError("test persistence failure")

    coordinator = PreExecutionRuntimeCoordinator(
        RuntimeCompositionConfig("postgresql://test", object()),
        _ready_boot_result(),
        persistence_coordinator_factory=failing_factory,
    )

    result = coordinator.evaluate(_proposal())

    assert result.disposition == TECHNICAL_FAILURE
    assert result.reason == "PERSISTENCE_INITIALIZATION_FAILED"
    assert result.submission_authority == "NONE"
    assert result.execution_authority == "NONE"
    coordinator.close()


def test_pre_execution_runtime_result_is_immutable():
    result = PreExecutionRuntimeResult("RECORDED_BLOCK")

    with pytest.raises(FrozenInstanceError):
        result.disposition = "RECORDED_ALLOW"


def test_recorded_allow_mapping_remains_authority_free_with_unit_fakes():
    class FakeEvaluator:
        def evaluate(self, **_kwargs):
            return SimpleNamespace(
                disposition=SimpleNamespace(value="RECORDED_ALLOW"),
                reason="TEST_ONLY_ALLOW_EVIDENCE",
                pre_execution_decision_id="decision-1",
                decision_outcome="ALLOW",
            )

    def fake_factory(*_args, **_kwargs):
        return _FakePersistenceCoordinator()

    coordinator = PreExecutionRuntimeCoordinator(
        RuntimeCompositionConfig("postgresql://test", object()),
        _ready_boot_result(),
        persistence_coordinator_factory=fake_factory,
        evaluator_factory=lambda _persistence: FakeEvaluator(),
    )
    coordinator._lineage_store = SimpleNamespace(
        ensure_pre_execution_lineage=lambda **_kwargs: SimpleNamespace(
            intent={"intent_id": "intent-1"},
            attempt={"attempt_id": "attempt-1"},
        )
    )

    result = coordinator.evaluate(_proposal())

    assert result.disposition == "RECORDED_ALLOW"
    assert result.submission_authority == "NONE"
    assert result.execution_authority == "NONE"
    coordinator.close()


@pytest.mark.parametrize(
    "failure_kind, expected_disposition",
    [("TECHNICAL", TECHNICAL_FAILURE), ("LINEAGE", LINEAGE_CONFLICT)],
)
def test_lineage_and_technical_failures_cannot_expose_authority(
    failure_kind, expected_disposition
):
    coordinator = PreExecutionRuntimeCoordinator(
        RuntimeCompositionConfig("postgresql://test", object()),
        _ready_boot_result(),
        persistence_coordinator_factory=lambda *_args, **_kwargs: _FakePersistenceCoordinator(),
        evaluator_factory=lambda _persistence: SimpleNamespace(),
    )
    if failure_kind == "LINEAGE":
        def raise_lineage_conflict(**_kwargs):
            raise ValueError("lineage conflict")

        coordinator._lineage_store = SimpleNamespace(
            ensure_pre_execution_lineage=raise_lineage_conflict
        )
        proposal = _proposal()
    else:
        proposal = object()

    result = coordinator.evaluate(proposal)

    assert result.disposition == expected_disposition
    assert result.submission_authority == "NONE"
    assert result.execution_authority == "NONE"
    coordinator.close()


def test_runtime_coordinator_source_has_no_downstream_authority_imports():
    source = Path(
        "core/execution/pre_execution_runtime_coordinator.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "SubmissionAuthorizationIssuer",
        "SubmissionAuthorizationClaimer",
        "GovernedSubmissionGateway",
        "MockExecutor",
        "BinanceExecutor",
        "PositionManager",
        "EffectApplicationCoordinator",
    )

    assert all(token not in source for token in forbidden)


def test_runtime_coordinator_exposes_pre_analysis_provenance_boundary():
    assert hasattr(
        PreExecutionRuntimeCoordinator,
        "persist_provenance_artifact",
    ), "EXPECTED_CONTRACT_RED::runtime provenance persistence boundary is missing"


def test_observe_only_provenance_path_has_no_write_or_evaluator_capability():
    assert hasattr(
        PreExecutionRuntimeCoordinator,
        "observe_provenance",
    ), "EXPECTED_CONTRACT_RED::observe-only provenance boundary is missing"

    calls = []

    def forbidden(*_args, **_kwargs):
        calls.append("called")
        raise AssertionError("OBSERVE_ONLY must not persist provenance or evaluate")

    coordinator = PreExecutionRuntimeCoordinator(
        RuntimeCompositionConfig(None, None),
        BootResult(posture=OBSERVE_ONLY, reason="AUTHORITY_STATE_OBSERVE_ONLY"),
        persistence_coordinator_factory=forbidden,
        evaluator_factory=forbidden,
    )

    assert coordinator.observe_provenance(_proposal()) == 0
    assert calls == []
    coordinator.close()


def test_required_pre_analysis_persistence_capability_is_fail_closed_before_analysis():
    from core.slot_controller import SlotController

    source = inspect.getsource(SlotController.run_cycle)
    assert "pre_execution_runtime_required" in source
    assert "runtime_coordinator" in source
    assert "_contain_pre_execution_buy" in source, (
        "EXPECTED_CONTRACT_RED::missing pre-analysis provenance capability can bypass containment"
    )
    assert source.index("_contain_pre_execution_buy") < source.index(
        "slot.start_analysis()"
    ), (
        "EXPECTED_CONTRACT_RED::provenance failure must block before slot.start_analysis"
    )


def test_real_decision_engine_carries_all_material_dynamic_evidence_to_proposal():
    class Risk:
        max_trades = 4

        def get_available_capital(self):
            return 100.0

        def evaluate_entry(self, **_kwargs):
            return RiskEvaluation(
                approved=True,
                reason="Trade aprovado",
                stop_loss_price=99.0,
                take_profit_price=102.0,
                risk_reward_ratio=2.0,
                expected_profit_pct=0.0065,
            )

    class Allocator:
        def request_allocation(self, _pair):
            return AllocationDecision(True, allocated_usdc=40.0, reason="allocated")

    snapshot = MarketSnapshot(
        pair="HYPEUSDC",
        price=100.0,
        rsi=55.0,
        ema_fast=101.0,
        ema_slow=99.0,
        volume_ratio=2.0,
        atr=0.3,
        trend="UPTREND",
        momentum="BULLISH",
        market_state="TRADE_OK",
        volume_state="HIGH",
        selection_score=0.90,
        liquidity_score=0.90,
    )
    engine = DecisionEngine(Risk(), Allocator())
    signal = engine.evaluate_buy(snapshot)

    assert signal is not None, "EXPECTED_CONTRACT_RED::real decision path did not produce BUY"
    decision_evidence = getattr(signal, "pre_execution_dynamic_evidence", None)
    assert decision_evidence is not None, (
        "EXPECTED_CONTRACT_RED::DECISION_DYNAMIC_EVIDENCE_NOT_CAPTURED"
    )

    proposal = PreExecutionRuntimeProposal.from_buy_signal(snapshot, signal)
    assert proposal.evidence.provenance.get("decision_dynamic_evidence") == (
        decision_evidence
    ), "EXPECTED_CONTRACT_RED::decision evidence was not preserved into proposal"


def test_real_radar_path_emits_selection_and_context_constituent_evidence():
    radar = object.__new__(MarketRadarEngine)
    radar.market_quality = {
        "state": "TRADE_OK",
        "score": 0.9,
        "timestamp": "2026-01-01T00:10:00Z",
    }
    opportunity = {
        "symbol": "HYPEUSDC",
        "analysis": {
            "trend": "UPTREND",
            "momentum": "BULLISH",
            "market_state": "TRADE_OK",
            "volume_ratio": 2.0,
        },
        "selection_score": 0.9,
        "market_context": {
            "liquidity_score": 0.9,
            "approved_count": 2,
            "refined_count": 3,
        },
        "governed_provenance": {
            "source_group_timestamps": {
                PRICE_TECHNICAL: datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
            },
            "source_group_digests": {PRICE_TECHNICAL: "price-digest"},
            "source_group_constituent_digests": {
                PRICE_TECHNICAL: ("kline-digest",),
            },
        },
    }

    radar._attach_governed_provenance([opportunity])
    provenance = opportunity["governed_provenance"]

    constituents = provenance.get("source_group_constituents", {})
    missing_evidence = provenance.get("source_group_missing_evidence", {})
    assert constituents.get(SELECTION_RADAR), (
        "EXPECTED_CONTRACT_RED::SELECTION_RADAR_REAL_PRODUCER_MISSING"
    )
    assert constituents.get(MARKET_CONTEXT), (
        "EXPECTED_CONTRACT_RED::MARKET_CONTEXT_REAL_PRODUCER_MISSING"
    )
    assert missing_evidence.get(SELECTION_RADAR)
    assert missing_evidence.get(MARKET_CONTEXT)


def test_real_radar_producer_preserves_material_results_and_observation_ids():
    radar = object.__new__(MarketRadarEngine)
    radar.market_quality = {"state": "TRADE_OK", "score": 0.9}
    observation_id = "binance:kline:HYPEUSDC:observation-001"
    observation_digest = "kline-semantic-digest-001"
    opportunity = {
        "symbol": "HYPEUSDC",
        "ranking_evidence": {"rank": 1, "score": 0.91},
        "selection_decision": {"approved": True, "reason": "ranked"},
        "mce_result": {"confirmed": True, "state": "BULLISH"},
        "rra_state": {"premium": True, "score": 0.8},
        "lc1_result": {"used_for_buy": False},
        "market_context": {
            "raw_ranking_set": ["HYPEUSDC", "BTCUSDC"],
            "refined_set": ["HYPEUSDC"],
            "approved_set": ["HYPEUSDC"],
            "liquidity": {"score": 0.9},
            "mqii": {"score": 0.8, "computed_at": "2026-01-01T00:10:00Z"},
            "macro_context": {"risk_on": True},
        },
        "governed_provenance": {
            "source_group_timestamps": {
                PRICE_TECHNICAL: datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
            },
            "source_group_digests": {PRICE_TECHNICAL: "price-digest"},
            "source_group_constituents": {
                PRICE_TECHNICAL: [
                    {
                        "constituent_id": observation_id,
                        "semantic_digest": observation_digest,
                        "trustworthy_market_time": True,
                    }
                ]
            },
            "source_group_constituent_digests": {
                PRICE_TECHNICAL: (observation_digest,),
            },
        },
    }

    radar._attach_governed_provenance([opportunity])
    provenance = opportunity["governed_provenance"]
    selection_records = provenance["source_group_constituents"][SELECTION_RADAR]
    context_records = provenance["source_group_constituents"][MARKET_CONTEXT]

    selection_roles = {record.get("role") for record in selection_records}
    context_roles = {record.get("role") for record in context_records}
    missing_selection_roles = {
        "ranking_result", "selection_result", "mce_result", "rra_state"
    } - selection_roles
    missing_context_roles = {
        "raw_ranking_set",
        "refined_set",
        "approved_set",
        "liquidity",
        "mqii",
        "macro_context",
    } - context_roles
    upstream_identity_failures = [
        record.get("role")
        for record in selection_records + context_records
        if observation_id not in record.get("upstream_market_observation_ids", ())
        or observation_digest in record.get("upstream_market_observation_ids", ())
    ]
    assert (
        not missing_selection_roles
        and not missing_context_roles
        and not upstream_identity_failures
    ), (
        "EXPECTED_CONTRACT_RED::SELECTION_RADAR_PRODUCER_PARTIAL::"
        f"missing_selection={sorted(missing_selection_roles)};"
        "EXPECTED_CONTRACT_RED::MARKET_CONTEXT_PRODUCER_PARTIAL::"
        f"missing_context={sorted(missing_context_roles)};"
        "EXPECTED_CONTRACT_RED::UPSTREAM_OBSERVATION_IDENTITY_CONFUSED_WITH_DIGEST::"
        f"roles={upstream_identity_failures}"
    )

    for record in selection_records + context_records:
        assert observation_id in record.get("upstream_market_observation_ids", ()), (
            "EXPECTED_CONTRACT_RED::UPSTREAM_OBSERVATION_IDENTITY_CONFUSED_WITH_DIGEST"
        )
        assert observation_digest not in record.get(
            "upstream_market_observation_ids", ()
        ), "EXPECTED_CONTRACT_RED::UPSTREAM_OBSERVATION_IDENTITY_CONFUSED_WITH_DIGEST"

    assert "LC1" not in selection_roles, (
        "EXPECTED_CONTRACT_RED::LC1_WAS_NOT_MATERIALLY_USED_BY_BUY"
    )


def _actual_radar_filter_once():
    radar = object.__new__(MarketRadarEngine)
    radar.market_quality = {"state": "TRADE_OK", "score": 0.91}
    radar.market_liquidity = {
        "liquidity_score": 0.91,
        "approved_count": 3,
        "refined_count": 4,
        "uptrend_count": 2,
        "avg_volume_ratio": 1.8,
    }
    radar.trade_cooldowns = {}
    radar.rejection_cooldowns = {}
    radar.penalty_map = {}
    radar.operational_state = {}
    radar.max_penalty_allowed = 2
    radar.penalty_score_weight = 0.20
    radar.last_traded_symbol = None
    radar.block_last_traded_symbol = True
    radar.min_market_score = 1.0
    radar.min_volume_ratio = 0.65
    radar.min_rsi = 45.0
    radar.min_final_score = 0.30
    radar.selection_rejection_awareness = {}
    radar.rra_selection_rejection_ttl_seconds = 45
    radar.rra_selection_score_penalties = {1: 0.02, 2: 0.04, 3: 0.06}
    radar.rra_selection_score_penalty_cap = 0.06
    radar.rra_premium_score_threshold = 0.85
    radar.rra_premium_penalty_cap = 0.03

    selection_result = {
        "decision_id": "selection-decision-unique-2b8b",
        "approved": True,
        "final_score": 0.91,
        "approval_reasons": ["UNIQUE_SELECTION_REASON"],
    }
    mce_result = {
        "confirmation_id": "mce-confirmation-unique-2b8b",
        "state": "CONFIRMED_UNIQUE",
        "used_for_buy": True,
    }
    radar.selection_engine = SimpleNamespace(
        evaluate=lambda _item: SimpleNamespace(**selection_result)
    )
    radar.mce = SimpleNamespace(confirm=lambda _item: mce_result)

    item = {
        "symbol": "HYPEUSDC",
        "score": 0.91,
        "analysis": {
            "trend": "UPTREND",
            "momentum": "BULLISH",
            "market_state": "TRADE_OK",
            "volume": "HIGH",
            "volume_ratio": 2.0,
            "rsi": 55.0,
            "market_score": 2.0,
        },
        "snapshot": SimpleNamespace(rsi_14=55.0, volume_ratio=2.0),
    }
    radar.selection_rejection_awareness["HYPEUSDC"] = {
        "expires_at": time.time() + 60,
        "context_signature": radar._rra_context_signature(item),
        "rejection_count": 2,
    }

    filtered = radar._filter_ranking([item])
    assert len(filtered) == 1, "EXPECTED_CONTRACT_RED::REAL_RADAR_FLOW_DID_NOT_PRODUCE_CANDIDATE"
    radar._attach_governed_provenance(filtered)
    return filtered[0], radar, selection_result, mce_result


def test_actual_selection_result_is_preserved_from_real_filter_flow():
    item, _radar, selection_result, _mce_result = _actual_radar_filter_once()
    records = item["governed_provenance"]["source_group_constituents"][SELECTION_RADAR]
    assert any(record.get("carrier") == selection_result for record in records), (
        "EXPECTED_CONTRACT_RED::REAL_SELECTION_DECISION_NOT_PRESERVED"
    )


def test_actual_mce_result_is_preserved_from_real_filter_flow():
    item, _radar, _selection_result, mce_result = _actual_radar_filter_once()
    records = item["governed_provenance"]["source_group_constituents"][SELECTION_RADAR]
    assert any(record.get("carrier") == mce_result for record in records), (
        "EXPECTED_CONTRACT_RED::REAL_MCE_RESULT_NOT_PRESERVED"
    )


def test_actual_rra_context_is_preserved_from_real_filter_flow():
    item, _radar, _selection_result, _mce_result = _actual_radar_filter_once()
    records = item["governed_provenance"]["source_group_constituents"][SELECTION_RADAR]
    actual_rra_context = item["rra_context"]
    assert any(record.get("carrier") == actual_rra_context for record in records), (
        "EXPECTED_CONTRACT_RED::REAL_RRA_CONTEXT_NOT_PRESERVED"
    )


def _actual_radar_cycle_with_mutable_context(monkeypatch):
    import core.radar.market_radar_engine as market_radar_module

    radar = object.__new__(MarketRadarEngine)
    context_a = {"state": "CONSUMED_A", "score": 0.91}
    liquidity_a = {
        "liquidity_score": 0.91,
        "approved_count": 3,
        "refined_count": 4,
        "uptrend_count": 2,
        "avg_volume_ratio": 1.8,
    }
    context_b = {"state": "POST_HOC_B", "score": 0.11}
    liquidity_b = {
        "liquidity_score": 0.11,
        "approved_count": 99,
        "refined_count": 100,
        "uptrend_count": 0,
        "avg_volume_ratio": 0.1,
    }
    candidate = {
        "symbol": "HYPEUSDC",
        "score": 0.91,
        "analysis": {
            "trend": "UPTREND",
            "momentum": "BULLISH",
            "market_state": "TRADE_OK",
            "volume": "HIGH",
            "volume_ratio": 2.0,
            "rsi": 55.0,
            "market_score": 2.0,
        },
        "snapshot": SimpleNamespace(rsi_14=55.0, volume_ratio=2.0),
    }
    raw_ranking = [
        candidate,
        *[
            {
                "symbol": symbol,
                "analysis": {"trend": "UPTREND", "momentum": "BULLISH", "market_state": "TRADE_OK"},
            }
            for symbol in ("BTCUSDC", "ETHUSDC", "BNBUSDC")
        ],
    ]
    ranking_snapshot = {"ranking_snapshot_id": "ranking-snapshot-a"}
    cycle_inputs = {}

    radar.market_quality = context_a
    radar.market_liquidity = liquidity_a
    radar.market_liquidity_history = []
    radar.max_liquidity_history = 100
    radar.trade_cooldowns = {}
    radar.rejection_cooldowns = {}
    radar.penalty_map = {}
    radar.operational_state = {}
    radar.max_penalty_allowed = 2
    radar.penalty_score_weight = 0.20
    radar.last_traded_symbol = None
    radar.block_last_traded_symbol = True
    radar.min_market_score = 1.0
    radar.min_volume_ratio = 0.65
    radar.min_rsi = 45.0
    radar.min_final_score = 0.30
    radar.selection_rejection_awareness = {}
    radar.rra_selection_rejection_ttl_seconds = 45
    radar.rra_selection_score_penalties = {1: 0.02, 2: 0.04, 3: 0.06}
    radar.rra_selection_score_penalty_cap = 0.06
    radar.rra_premium_score_threshold = 0.85
    radar.rra_premium_penalty_cap = 0.03
    radar.latest_ranking = []
    radar.running = True
    radar.scan_interval = 0

    radar.selection_engine = SimpleNamespace(
        evaluate=lambda _item: SimpleNamespace(
            approved=True, final_score=0.91, rejection_reasons=[]
        )
    )
    radar.mce = SimpleNamespace(confirm=lambda _item: True)
    radar.scanner = SimpleNamespace(
        scan=lambda: raw_ranking,
        technical_scanner=SimpleNamespace(analyze_symbol=lambda _symbol: None),
    )
    radar.rank_engine = SimpleNamespace(
        _radar_summary_local=None,
        refine=lambda _raw, rra_awareness_snapshot: ([candidate], ranking_snapshot),
    )

    def liquidity_analyze(*, all_analyses, refined_tokens, approved_tokens, market_snapshot):
        cycle_inputs["raw"] = all_analyses
        cycle_inputs["refined"] = refined_tokens
        cycle_inputs["approved"] = approved_tokens
        cycle_inputs["ranking_snapshot"] = market_snapshot
        return dict(liquidity_b)

    class Liquidity:
        analyze = staticmethod(liquidity_analyze)

    class MQII:
        @staticmethod
        def evaluate_market(*, all_analyses, refined_tokens, approved_tokens, market_snapshot):
            cycle_inputs["mqii_inputs"] = {
                "raw": all_analyses,
                "refined": refined_tokens,
                "approved": approved_tokens,
                "ranking_snapshot": market_snapshot,
            }
            return dict(context_b)

    radar.liquidity_analyzer = Liquidity()
    radar.mqii = MQII()
    monkeypatch.setattr(
        market_radar_module.time,
        "sleep",
        lambda _seconds: setattr(radar, "running", False),
    )

    radar._radar_loop()
    return radar.latest_ranking[0], cycle_inputs, context_a, liquidity_a, context_b, liquidity_b


def test_actual_market_context_inputs_are_bound_at_cycle_use_point(monkeypatch):
    item, cycle_inputs, _context_a, _liquidity_a, _context_b, _liquidity_b = (
        _actual_radar_cycle_with_mutable_context(monkeypatch)
    )
    assert cycle_inputs["raw"] and cycle_inputs["refined"] and cycle_inputs["approved"]
    roles = {
        record.get("role")
        for record in item["governed_provenance"]["source_group_constituents"][MARKET_CONTEXT]
    }
    assert {
        "raw_ranking_set",
        "refined_set",
        "approved_set",
        "liquidity",
        "mqii",
        "macro_context",
    } <= roles, "EXPECTED_CONTRACT_RED::MARKET_CONTEXT_ACTUAL_INPUTS_NOT_BOUND"


def test_actual_market_context_does_not_substitute_post_hoc_mutable_state(monkeypatch):
    item, _cycle_inputs, context_a, liquidity_a, context_b, liquidity_b = (
        _actual_radar_cycle_with_mutable_context(monkeypatch)
    )
    carriers = [
        record.get("carrier")
        for record in item["governed_provenance"]["source_group_constituents"][MARKET_CONTEXT]
    ]
    assert any(carrier == context_a for carrier in carriers), (
        "EXPECTED_CONTRACT_RED::MARKET_CONTEXT_POST_HOC_MUTABLE_STATE_SUBSTITUTION"
    )
    assert any(carrier == liquidity_a for carrier in carriers), (
        "EXPECTED_CONTRACT_RED::MARKET_CONTEXT_POST_HOC_MUTABLE_STATE_SUBSTITUTION"
    )
    assert context_b not in carriers and liquidity_b not in carriers, (
        "EXPECTED_CONTRACT_RED::MARKET_CONTEXT_POST_HOC_MUTABLE_STATE_SUBSTITUTION"
    )


def test_lineage_context_is_separate_from_intent_policy_compatibility(monkeypatch):
    import core.execution.pre_execution_runtime_coordinator as runtime_module

    assert getattr(runtime_module, "INTENT_POLICY_CONTEXT_COMPAT", None) == (
        "handa-2b7-pre-execution-v1"
    )
    assert getattr(runtime_module, "LINEAGE_CONTRACT_CONTEXT", None) == (
        "handa-2b8b-pre-execution-provenance-v1"
    ), "EXPECTED_CONTRACT_RED::LINEAGE_CONTEXT_CONSTANT_MISSING"

    proposal = _proposal()
    artifact = _bound_artifact(proposal, "context")
    first = PreExecutionRuntimeCoordinator.derive_identity(
        proposal,
        venue="MOCK",
        account_scope="TEST",
        provenance_artifact=artifact,
    )
    monkeypatch.setattr(
        runtime_module,
        "LINEAGE_CONTRACT_CONTEXT",
        "handa-2b8b-altered-lineage-context",
    )
    second = PreExecutionRuntimeCoordinator.derive_identity(
        proposal,
        venue="MOCK",
        account_scope="TEST",
        provenance_artifact=artifact,
    )
    assert first.intent_id != second.intent_id, (
        "EXPECTED_CONTRACT_RED::lineage digest ignores lineage contract context"
    )

