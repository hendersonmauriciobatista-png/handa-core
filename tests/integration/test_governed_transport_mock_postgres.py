"""Integration contracts for the post-claim governed MOCK transport proof."""

from __future__ import annotations

import os
import json
import threading
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

import psycopg2
import pytest

from core.execution.execution_fact import ExecutionFact, ExternalOrderStatus, normalize_external_execution
from core.execution.authority_digest import attempt_semantic_digest, intent_semantic_digest
from core.execution.governed_submission_gateway import (
    GovernedSubmissionGateway,
    TransportDisposition,
)
from core.execution.mock_capability_venue_adapter import MockCapabilityVenueAdapter
from core.execution.submission_authority import submission_fingerprint
from core.persistence.governed_transport_store import (
    EVENT_COLUMNS,
    TRANSPORT_COLUMNS,
    GovernedTransportStore,
    governed_transport_resource_scope,
)
from core.persistence.persistence_coordinator import DatabaseIdentity, PersistenceCoordinator
from core.persistence.submission_authorization_store import SubmissionAuthorizationStore
from tests.integration.test_submission_authority_envelope_and_decision_postgres import (
    _seed_lineage,
)
from tests.integration.test_submission_authorization_postgres import (
    EXPECTED_DATABASE,
    EXPECTED_HOSTS,
    EXPECTED_PORT,
    EXPECTED_URL,
    EXPECTED_USER,
    _bootstrap,
)


ROOT = Path(__file__).parents[2]
IDENTITY = DatabaseIdentity(EXPECTED_HOSTS, EXPECTED_PORT, EXPECTED_DATABASE, EXPECTED_USER)
MIGRATION_012 = ROOT / "core" / "persistence" / "migrations" / "012_governed_transport_submission.sql"


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value != EXPECTED_URL:
        pytest.skip("ENVIRONMENT_BLOCKED: disposable local PostgreSQL is required")
    parsed = urlparse(value)
    if (
        parsed.hostname not in EXPECTED_HOSTS
        or parsed.port != EXPECTED_PORT
        or parsed.path.lstrip("/") != EXPECTED_DATABASE
        or parsed.username != EXPECTED_USER
    ):
        pytest.fail("test database identity is outside the governed disposable database")
    return value


def _execute(url: str, statement: str, parameters=(), *, fetch=False):
    connection = psycopg2.connect(url)
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            rows = cursor.fetchall() if fetch and cursor.description else None
        connection.commit()
        return rows
    finally:
        connection.close()


def _seed_authorized(url: str, prefix: str = "transport"):
    intent_id, attempt_id, client_order_id = _seed_lineage(url, prefix)
    envelope_id = f"{prefix}-envelope"
    decision_id = f"{prefix}-decision"
    authorization_id = f"{prefix}-authorization"
    intent_values = _execute(
        url,
        """
        SELECT intent_id, venue, account_scope, client_order_id, slot_id,
               symbol, side, requested_quote_amount, requested_base_qty,
               policy_context
        FROM handa_live.order_intent
        WHERE intent_id = %s
        """,
        (intent_id,),
        fetch=True,
    )[0]
    intent_row = dict(zip(
        (
            "intent_id", "venue", "account_scope", "client_order_id", "slot_id",
            "symbol", "side", "requested_quote_amount", "requested_base_qty",
            "policy_context",
        ),
        intent_values,
    ))
    attempt_values = _execute(
        url,
        """
        SELECT attempt_id, intent_id, attempt_sequence, venue, account_scope,
               client_order_id, context_id
        FROM handa_live.submission_attempt
        WHERE attempt_id = %s
        """,
        (attempt_id,),
        fetch=True,
    )[0]
    attempt_row = dict(zip(
        (
            "attempt_id", "intent_id", "attempt_sequence", "venue",
            "account_scope", "client_order_id", "context_id",
        ),
        attempt_values,
    ))
    canonical_intent_digest = intent_semantic_digest(intent_row)
    canonical_attempt_digest = attempt_semantic_digest(attempt_row)
    _execute(
        url,
        """
        INSERT INTO handa_live.authority_envelope (
            authority_envelope_id, runtime_mode, venue, account_scope,
            allowed_sides, strategy_version, decision_contract_version,
            policy_version, risk_policy_version, valid_from, valid_until,
            configuration_digest, authority_contract_version, approved_by,
            approval_reason
        ) VALUES (%s, 'OPERATIONAL_ENABLED', 'MOCK', 'TEST', ARRAY['BUY'],
                  'strategy-test-v1', 'decision-contract-v1', 'policy-test-v1',
                  'risk-policy-test-v1', CURRENT_TIMESTAMP - INTERVAL '10 minutes',
                  CURRENT_TIMESTAMP + INTERVAL '10 minutes',
                  'configuration-digest-test-001', 'submission-authority-v1',
                  'fixture-human-only', 'TEST_FIXTURE_AUTHORITY_ONLY')
        """,
        (envelope_id,),
    )
    _execute(
        url,
        """
        UPDATE handa_live.operational_authority_state
        SET operational_mode = 'OPERATIONAL_ENABLED',
            active_authority_envelope_id = %s,
            current_version = 1,
            changed_by = 'fixture-human-only',
            change_reason = 'TEST_FIXTURE_AUTHORITY_ONLY'
        WHERE state_id IS TRUE
        """,
        (envelope_id,),
    )
    _execute(
        url,
        """
        INSERT INTO handa_live.pre_execution_decision (
            pre_execution_decision_id, intent_id, submission_attempt_id,
            evaluation_request_id, evaluation_request_digest,
            authority_envelope_id, decision_sequence, decision_outcome,
            decision_reason, intent_semantic_digest,
            submission_attempt_semantic_digest, decision_contract_version,
            decision_engine_version, policy_version, risk_policy_version,
            strategy_version, input_snapshot_digest, decision_semantics_digest,
            global_safety_epoch, runtime_generation, runtime_mode, venue,
            account_scope, evaluated_at, valid_until
        ) VALUES (%s, %s, %s, %s, %s, %s, 1, 'ALLOW',
                  'TEST_FIXTURE_AUTHORITY_ONLY', %s, %s,
                  'decision-contract-v1', 'buy-signal-evidence-v1',
                  'policy-test-v1', 'risk-policy-test-v1', 'strategy-test-v1',
                  'input-snapshot-test', 'decision-semantics-test', 0, 0,
                  'OPERATIONAL_ENABLED', 'MOCK', 'TEST',
                  CURRENT_TIMESTAMP - INTERVAL '1 minute',
                  CURRENT_TIMESTAMP + INTERVAL '5 minutes')
        """,
        (
            decision_id,
            intent_id,
            attempt_id,
            f"TEST_ONLY_EVALUATION_IDENTITY-{decision_id}",
            f"TEST_ONLY_EVALUATION_DIGEST-{decision_id}",
            envelope_id,
            canonical_intent_digest,
            canonical_attempt_digest,
        ),
    )
    stored_digests = _execute(
        url,
        """
        SELECT intent_semantic_digest, submission_attempt_semantic_digest
        FROM handa_live.pre_execution_decision
        WHERE pre_execution_decision_id = %s
        """,
        (decision_id,),
        fetch=True,
    )[0]
    assert stored_digests == (canonical_intent_digest, canonical_attempt_digest)
    fingerprint = submission_fingerprint(
        intent_id=intent_id,
        submission_attempt_id=attempt_id,
        client_order_id=client_order_id,
        venue="MOCK",
        account_scope="TEST",
        symbol="HYPEUSDC",
        side="BUY",
        requested_quote_amount=Decimal("41.4117522032984"),
        requested_base_qty=None,
    )
    _execute(
        url,
        """
        INSERT INTO handa_live.submission_authorization (
            submission_authorization_id, intent_id, submission_attempt_id,
            client_order_id, venue, account_scope, symbol, side,
            requested_quote_amount, requested_base_qty,
            authority_reference_id, issuer_id, authority_contract_version,
            authorization_sequence, submission_fingerprint, authorization_state
        ) VALUES (%s, %s, %s, %s, 'MOCK', 'TEST', 'HYPEUSDC', 'BUY',
                  %s, NULL, %s, 'handa-submission-authorization-issuer',
                  'submission-authority-v1', 1, %s, 'AUTHORIZED')
        """,
        (
            authorization_id,
            intent_id,
            attempt_id,
            client_order_id,
            Decimal("41.4117522032984"),
            decision_id,
            fingerprint,
        ),
    )
    claim_coordinator = PersistenceCoordinator(
        url, IDENTITY, resource_scope=__import__(
            "core.persistence.submission_claim_store",
            fromlist=["submission_claim_resource_scope"],
        ).submission_claim_resource_scope(),
    )
    try:
        result = SubmissionAuthorizationStore(claim_coordinator).claim_authorization(
            __import__(
                "core.execution.submission_authority",
                fromlist=["SubmissionClaimRequest"],
            ).SubmissionClaimRequest(authorization_id)
        )
    finally:
        claim_coordinator.close()
    assert result.capability is not None
    return result.capability


class DurableFakeAdapter:
    def __init__(self, *, order=None, fail_submit=None, fail_recovery=None):
        self.order = order
        self.fail_submit = fail_submit
        self.fail_recovery = fail_recovery
        self.submit_count = 0
        self.recovery_count = 0

    @staticmethod
    def _fact(client_order_id: str) -> ExecutionFact:
        return normalize_external_execution({
            "symbol": "HYPEUSDC", "side": "BUY", "status": "FILLED",
            "orderId": "mock-order-test", "clientOrderId": client_order_id,
            "executedQty": "0.414117522032984",
            "cummulativeQuoteQty": "41.4117522032984",
            "fills": [{"tradeId": "mock-fill-test", "price": "100", "qty": "0.414117522032984", "quoteQty": "41.4117522032984"}],
            "singleFill": True, "fullExtentProven": True,
        })

    def submit_buy(self, *, symbol, requested_quote_amount, client_order_id):
        self.submit_count += 1
        if self.fail_submit is not None:
            raise self.fail_submit
        self.order = self._fact(client_order_id)
        return self.order

    def recover_by_client_order_id(self, client_order_id):
        self.recovery_count += 1
        if self.fail_recovery is not None:
            raise self.fail_recovery
        return self.order


class SimulatedProcessCrash(BaseException):
    """Test-only crash boundary after the durable MOCK effect."""


class CrashAfterDurableEffectAdapter:
    def __init__(self, adapter):
        self._adapter = adapter
        self.submit_count = 0

    def submit_buy(self, **kwargs):
        fact = self._adapter.submit_buy(**kwargs)
        self.submit_count += 1
        raise SimulatedProcessCrash("simulated process loss after durable MOCK effect")

    def recover_by_client_order_id(self, client_order_id):
        return self._adapter.recover_by_client_order_id(client_order_id)


class ThreadSafeFakeAdapter(DurableFakeAdapter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._counter_lock = threading.Lock()

    def submit_buy(self, **kwargs):
        with self._counter_lock:
            self.submit_count += 1
            if self.fail_submit is not None:
                raise self.fail_submit
            self.order = self._fact(kwargs["client_order_id"])
            return self.order

    def recover_by_client_order_id(self, client_order_id):
        with self._counter_lock:
            self.recovery_count += 1
            if self.fail_recovery is not None:
                raise self.fail_recovery
            return self.order


class BlockingFirstSendAdapter(ThreadSafeFakeAdapter):
    def __init__(self):
        super().__init__()
        self.submit_started = threading.Event()
        self.release_submit = threading.Event()
        self.recovery_started = threading.Event()

    def submit_buy(self, **kwargs):
        with self._counter_lock:
            self.submit_count += 1
        self.submit_started.set()
        if not self.release_submit.wait(timeout=10):
            raise AssertionError("first-send test did not release the venue call")
        self.order = self._fact(kwargs["client_order_id"])
        return self.order

    def recover_by_client_order_id(self, client_order_id):
        with self._counter_lock:
            self.recovery_count += 1
        self.recovery_started.set()
        return self.order


def _pausing_store_class(paused, release):
    class PausingTransportStore(GovernedTransportStore):
        armed = True

        @staticmethod
        def get_projection(context, authorization_id, *, for_update=False):
            if for_update and PausingTransportStore.armed:
                PausingTransportStore.armed = False
                paused.set()
                if not release.wait(timeout=10):
                    raise AssertionError("recovery-wins test did not release the first worker")
            return GovernedTransportStore.get_projection(
                context, authorization_id, for_update=for_update
            )

    return PausingTransportStore


def _notifying_store_class(lock_attempted):
    class NotifyingTransportStore(GovernedTransportStore):
        @staticmethod
        def get_projection(context, authorization_id, *, for_update=False):
            if for_update:
                lock_attempted.set()
            return GovernedTransportStore.get_projection(
                context, authorization_id, for_update=for_update
            )

    return NotifyingTransportStore


@pytest.fixture()
def prepared():
    url = _database_url()
    _bootstrap(url)
    with psycopg2.connect(url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(MIGRATION_012.read_text(encoding="utf-8"))
        connection.commit()
    try:
        yield url
    finally:
        _execute(url, "DROP SCHEMA IF EXISTS handa_live CASCADE")


def _gateway(url, adapter):
    coordinator = PersistenceCoordinator(
        url, IDENTITY, resource_scope=governed_transport_resource_scope()
    )
    store = GovernedTransportStore(coordinator)
    return coordinator, store, GovernedSubmissionGateway(store, adapter)


def _gateway_with_store_class(url, adapter, store_class):
    coordinator = PersistenceCoordinator(
        url, IDENTITY, resource_scope=governed_transport_resource_scope()
    )
    store = store_class(coordinator)
    return coordinator, store, GovernedSubmissionGateway(store, adapter)


def _event_types(url, authorization_id):
    rows = _execute(
        url,
        """
        SELECT event_type
        FROM handa_live.transport_event
        WHERE submission_authorization_id = %s
        ORDER BY event_sequence
        """,
        (authorization_id,),
        fetch=True,
    )
    return [row[0] for row in rows]


def _projection_state(url, authorization_id):
    return _execute(
        url,
        """
        SELECT transport_state, external_order_id
        FROM handa_live.transport_submission
        WHERE submission_authorization_id = %s
        """,
        (authorization_id,),
        fetch=True,
    )[0]


def test_migration_creates_projection_and_ledger(prepared):
    rows = _execute(
        prepared,
        """SELECT table_name FROM information_schema.tables
           WHERE table_schema = 'handa_live'
             AND table_name IN ('transport_submission', 'transport_event')
           ORDER BY table_name""",
        fetch=True,
    )
    assert rows == [("transport_event",), ("transport_submission",)]


def test_valid_claim_commits_handoff_before_one_mock_send(prepared):
    capability = _seed_authorized(prepared, "handoff")
    adapter = DurableFakeAdapter()
    coordinator, store, gateway = _gateway(prepared, adapter)
    try:
        result = gateway.submit(capability)
        assert result.disposition is TransportDisposition.SUBMISSION_ACCEPTED
        assert adapter.submit_count == 1
        with coordinator.transaction() as context:
            row = store.get_projection(context, capability.submission_authorization_id)
            assert row is not None
    finally:
        coordinator.close()


def test_lost_response_recovery_does_not_send_again(prepared):
    capability = _seed_authorized(prepared, "lost")
    adapter = DurableFakeAdapter()
    coordinator, store, gateway = _gateway(prepared, adapter)
    try:
        first = gateway.submit(capability)
        assert first.disposition is TransportDisposition.SUBMISSION_ACCEPTED
        second = gateway.submit(capability)
        assert second.disposition is TransportDisposition.TERMINAL_REPLAY
        assert adapter.submit_count == 1
    finally:
        coordinator.close()


def test_lost_response_after_durable_mock_effect_recovers_without_second_send(
    prepared, monkeypatch, tmp_path
):
    from tests.test_fw2_governed_mock_lost_response_expected_red import _fresh_executor

    capability = _seed_authorized(prepared, "crash-recovery")
    executor, state_path = _fresh_executor(monkeypatch, tmp_path)
    first_adapter = CrashAfterDurableEffectAdapter(MockCapabilityVenueAdapter(executor))
    first_coordinator, _, first_gateway = _gateway(prepared, first_adapter)
    try:
        with pytest.raises(SimulatedProcessCrash):
            first_gateway.submit(capability)
    finally:
        first_coordinator.close()

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert len(state["orders"]) == 1
    assert first_adapter.submit_count == 1
    assert _event_types(prepared, capability.submission_authorization_id) == [
        "HANDOFF_COMMITTED"
    ]

    restarted_executor, _ = _fresh_executor(monkeypatch, tmp_path, state=state)
    original_execute_authorized_buy = restarted_executor.execute_authorized_buy

    def forbidden_second_send(**kwargs):
        raise AssertionError("recovery attempted a second MOCK send")

    restarted_executor.execute_authorized_buy = forbidden_second_send
    second_coordinator, _, second_gateway = _gateway(
        prepared, MockCapabilityVenueAdapter(restarted_executor)
    )
    try:
        recovered = second_gateway.submit(capability)
        assert recovered.disposition is TransportDisposition.RECOVERY_ACCEPTED
        assert recovered.execution_fact is not None
        assert recovered.execution_fact.external_order_id == next(iter(state["orders"].values()))[
            "external_order_id"
        ]
        assert _projection_state(prepared, capability.submission_authorization_id)[0] == (
            "OBSERVED_ACCEPTED"
        )
        assert _event_types(prepared, capability.submission_authorization_id) == [
            "HANDOFF_COMMITTED",
            "RECOVERY_ACCEPTED",
        ]
        replay = second_gateway.submit(capability)
        assert replay.disposition is TransportDisposition.TERMINAL_REPLAY
        assert first_adapter.submit_count == 1
    finally:
        second_coordinator.close()
        restarted_executor.execute_authorized_buy = original_execute_authorized_buy


def test_concurrent_equivalent_capability_replay_has_one_or_zero_mock_sends(prepared):
    capability = _seed_authorized(prepared, "concurrent-replay")
    replay_capability = object.__new__(type(capability))
    for name in type(capability).__slots__:
        value = getattr(capability, name)
        object.__setattr__(replay_capability, name, value)
    adapter = ThreadSafeFakeAdapter()
    barrier = threading.Barrier(2)
    results = []
    errors = []

    def worker(worker_capability):
        coordinator, _, gateway = _gateway(prepared, adapter)
        try:
            barrier.wait(timeout=10)
            results.append(gateway.submit(worker_capability))
        except BaseException as exc:
            errors.append(exc)
        finally:
            coordinator.close()

    threads = [
        threading.Thread(target=worker, args=(capability,)),
        threading.Thread(target=worker, args=(replay_capability,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert not any(thread.is_alive() for thread in threads)
    assert not errors
    assert len(results) == 2
    assert adapter.submit_count <= 1
    assert adapter.submit_count + adapter.recovery_count >= 1
    assert _projection_state(prepared, capability.submission_authorization_id)[0] in {
        "OBSERVED_ACCEPTED",
        "NO_EFFECT_CONFIRMED",
    }
    counts = _execute(
        prepared,
        """
        SELECT
            (SELECT COUNT(*) FROM handa_live.transport_submission
             WHERE submission_authorization_id = %s),
            (SELECT COUNT(*) FROM handa_live.transport_event
             WHERE submission_authorization_id = %s
               AND event_type = 'HANDOFF_COMMITTED')
        """,
        (capability.submission_authorization_id, capability.submission_authorization_id),
        fetch=True,
    )[0]
    assert counts == (1, 1)


def test_recovery_wins_first_send_race_without_venue_send(prepared):
    capability = _seed_authorized(prepared, "recovery-wins")
    adapter = DurableFakeAdapter()
    paused = threading.Event()
    release = threading.Event()
    store_class = _pausing_store_class(paused, release)
    a_coordinator, _, a_gateway = _gateway_with_store_class(
        prepared, adapter, store_class
    )
    b_coordinator, _, b_gateway = _gateway(prepared, adapter)
    a_results = []
    b_results = []
    errors = []

    def worker_a():
        try:
            a_results.append(a_gateway.submit(capability))
        except BaseException as exc:
            errors.append(exc)

    def worker_b():
        try:
            b_results.append(b_gateway.submit(capability))
        except BaseException as exc:
            errors.append(exc)

    thread_a = threading.Thread(target=worker_a)
    thread_a.start()
    assert paused.wait(timeout=10)
    thread_b = threading.Thread(target=worker_b)
    thread_b.start()
    thread_b.join(timeout=15)
    assert not thread_b.is_alive()
    assert len(b_results) == 1
    assert b_results[0].disposition is TransportDisposition.RECOVERY_NO_EFFECT_CONFIRMED
    release.set()
    thread_a.join(timeout=15)
    assert not thread_a.is_alive()
    assert not errors
    assert len(a_results) == 1
    assert a_results[0].disposition is TransportDisposition.TERMINAL_REPLAY
    assert adapter.submit_count == 0
    assert _event_types(prepared, capability.submission_authorization_id) == [
        "HANDOFF_COMMITTED",
        "RECOVERY_NO_EFFECT_CONFIRMED",
    ]
    a_coordinator.close()
    b_coordinator.close()


def test_first_send_wins_recovery_race_under_shared_projection_lock(prepared):
    capability = _seed_authorized(prepared, "first-send-wins")
    adapter = BlockingFirstSendAdapter()
    lock_attempted = threading.Event()
    b_store_class = _notifying_store_class(lock_attempted)
    a_coordinator, _, a_gateway = _gateway(prepared, adapter)
    b_coordinator, _, b_gateway = _gateway_with_store_class(
        prepared, adapter, b_store_class
    )
    a_results = []
    b_results = []
    errors = []

    def worker_a():
        try:
            a_results.append(a_gateway.submit(capability))
        except BaseException as exc:
            errors.append(exc)

    def worker_b():
        try:
            b_results.append(b_gateway.submit(capability))
        except BaseException as exc:
            errors.append(exc)

    thread_a = threading.Thread(target=worker_a)
    thread_a.start()
    assert adapter.submit_started.wait(timeout=10)
    thread_b = threading.Thread(target=worker_b)
    thread_b.start()
    assert lock_attempted.wait(timeout=10)
    assert not adapter.recovery_started.is_set()
    assert adapter.submit_count == 1
    adapter.release_submit.set()
    thread_a.join(timeout=15)
    thread_b.join(timeout=15)
    assert not thread_a.is_alive()
    assert not thread_b.is_alive()
    assert not errors
    assert len(a_results) == 1
    assert len(b_results) == 1
    assert a_results[0].disposition is TransportDisposition.SUBMISSION_ACCEPTED
    assert b_results[0].disposition is TransportDisposition.TERMINAL_REPLAY
    assert adapter.submit_count == 1
    assert adapter.recovery_count == 1
    assert _event_types(prepared, capability.submission_authorization_id) == [
        "HANDOFF_COMMITTED",
        "SUBMISSION_ACCEPTED",
    ]
    a_coordinator.close()
    b_coordinator.close()


def test_no_effect_recovery_is_terminal_and_cannot_resubmit(prepared):
    capability = _seed_authorized(prepared, "no-effect")
    adapter = DurableFakeAdapter()
    coordinator, store, gateway = _gateway(prepared, adapter)
    try:
        with coordinator.transaction() as context:
            preparation = store.prepare_handoff(context, capability)
            assert preparation.created
        result = gateway.submit(capability)
        assert result.disposition is TransportDisposition.RECOVERY_NO_EFFECT_CONFIRMED
        assert adapter.submit_count == 0
        replay = gateway.submit(capability)
        assert replay.disposition is TransportDisposition.TERMINAL_REPLAY
        assert adapter.submit_count == 0
    finally:
        coordinator.close()


def test_ambiguous_failure_enters_unknown_without_retry(prepared):
    capability = _seed_authorized(prepared, "unknown")
    adapter = DurableFakeAdapter(fail_submit=RuntimeError("lost response"))
    coordinator, store, gateway = _gateway(prepared, adapter)
    try:
        result = gateway.submit(capability)
        assert result.disposition is TransportDisposition.SUBMISSION_OUTCOME_UNKNOWN
        assert adapter.submit_count == 1
        recovered = gateway.submit(capability)
        assert recovered.disposition is TransportDisposition.RECOVERY_NO_EFFECT_CONFIRMED
        assert adapter.submit_count == 1
    finally:
        coordinator.close()


def test_event_history_is_immutable_and_terminal_cannot_reopen(prepared):
    capability = _seed_authorized(prepared, "immutable")
    adapter = DurableFakeAdapter()
    coordinator, store, gateway = _gateway(prepared, adapter)
    try:
        gateway.submit(capability)
        with pytest.raises(psycopg2.Error):
            _execute(
                prepared,
                "DELETE FROM handa_live.transport_event WHERE submission_authorization_id = %s",
                (capability.submission_authorization_id,),
            )
        with pytest.raises(psycopg2.Error):
            _execute(
                prepared,
                "UPDATE handa_live.transport_submission SET transport_state = 'HANDOFF_COMMITTED' WHERE submission_authorization_id = %s",
                (capability.submission_authorization_id,),
            )
    finally:
        coordinator.close()


def test_sell_and_forged_capability_fail_closed(prepared):
    capability = _seed_authorized(prepared, "reject")
    coordinator, store, gateway = _gateway(prepared, DurableFakeAdapter())
    try:
        invalid = gateway.submit(object())
        assert invalid.disposition is TransportDisposition.INVALID_CAPABILITY
        assert gateway.submit(SimpleNamespace(side="SELL")) .disposition is TransportDisposition.INVALID_CAPABILITY
    finally:
        coordinator.close()


def test_new_executor_primitive_requires_decimal_and_preserves_quote(monkeypatch, tmp_path):
    from tests.test_fw2_governed_mock_lost_response_expected_red import _fresh_executor

    executor, _ = _fresh_executor(monkeypatch, tmp_path)
    with pytest.raises(TypeError):
        executor.execute_authorized_buy(
            symbol="HYPEUSDC", requested_quote_amount=41.0, client_order_id="client-1"
        )
    fact = executor.execute_authorized_buy(
        symbol="HYPEUSDC", requested_quote_amount=Decimal("41.4117522032984"), client_order_id="client-1"
    )
    assert fact.executed_quote_qty == Decimal("41.4117522032984")


def test_adapter_is_capability_neutral():
    source = (ROOT / "core" / "execution" / "mock_capability_venue_adapter.py").read_text(encoding="utf-8")
    assert "ClaimedSubmissionCapability" not in source
    assert "BuySignal" not in source
