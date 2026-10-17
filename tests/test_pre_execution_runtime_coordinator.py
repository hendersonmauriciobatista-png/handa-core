from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.decision.decision_engine import BuySignal, MarketSnapshot
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


def _proposal():
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
    first = PreExecutionRuntimeCoordinator.derive_identity(
        _proposal(), venue="MOCK", account_scope="TEST"
    )
    second = PreExecutionRuntimeCoordinator.derive_identity(
        _proposal(), venue="MOCK", account_scope="TEST"
    )

    assert first == second
    assert first.attempt_sequence == 1
    assert first.intent_id.startswith("2b7-intent-")
    assert first.attempt_id.startswith("2b7-attempt-")
    assert first.evaluation_request_id.startswith("2b7-eval-")
    assert first.evaluation_request_digest


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


def _ready_boot_result():
    return BootResult(
        posture=GOVERNED_INFRASTRUCTURE_READY,
        reason="TEST_ONLY",
        authority_snapshot=AuthoritySnapshot(
            state_s1={},
            active_envelope={"venue": "MOCK", "account_scope": "TEST"},
            state_s2={},
        ),
    )


class _FakePersistenceCoordinator:
    def verify_ready(self):
        return None

    def close(self):
        return None


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

