"""Control-first falsifiers for the 3B4 closure hardening controls."""

import psycopg2
import pytest

from core.persistence.effect_application_ledger import (
    EffectApplicationLedger,
    EffectApplicationLedgerError,
)
from tests.integration import test_effect_application_ledger_postgres as _postgres


connection = _postgres.connection
_base = _postgres._base
_ledger = _postgres._ledger
_request = _postgres._request


def _unknown_request(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    ledger.mark_outcome_unknown(
        "request-a", application_attempt_id="attempt-a", reason="fault injection"
    )
    return ledger


def _expect_rejected(connection, statement, params=(), needle=None):
    with pytest.raises(psycopg2.Error) as error:
        with connection.cursor() as cursor:
            cursor.execute(statement, params)
    message = str(error.value)
    connection.rollback()
    if needle:
        assert needle in message, message
    return message


def test_h01_c3_ordinary_exception_never_proves_failed_without_effect(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    with pytest.raises(EffectApplicationLedgerError, match="positive non-mutation"):
        ledger.mark_failed_without_effect(
            "request-a",
            application_attempt_id="attempt-a",
            evidence=[{"evidence_id": "exception", "proof_type": "ORDINARY_EXCEPTION"}],
        )
    assert ledger.get_application_state("request-a").state == "APPLYING"


def test_h01_c4_crash_after_application_boundary_preserves_unknown(connection, monkeypatch):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")

    def crash_before_projection(*args, **kwargs):
        raise RuntimeError("simulated crash after application evidence")

    monkeypatch.setattr(ledger, "_finish", crash_before_projection)
    with pytest.raises(EffectApplicationLedgerError, match="unknown"):
        ledger.mark_applied(
            "request-a", application_attempt_id="attempt-a",
            receipt=_postgres._receipt(),
        )
    assert ledger.get_application_state("request-a").state == "OUTCOME_UNKNOWN"


def test_h02_arbitrary_recovery_authority_id_is_rejected(connection):
    ledger = _unknown_request(connection)
    with pytest.raises(EffectApplicationLedgerError, match="recovery capability"):
        ledger.recover_application(
            "request-a",
            recovery_authority_id="invented-by-ordinary-worker",
            recovery_policy_version="v1",
            classification="OUTCOME_UNKNOWN",
            evidence=[{"evidence_id": "query", "proof_type": "EXCHANGE_QUERY"}],
        )


def test_h03_direct_invalid_projection_state_update_is_rejected(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    _expect_rejected(
        connection,
        "UPDATE handa_live.effect_request SET current_state='APPLIED' "
        "WHERE effect_request_id='request-a'",
        needle="transition",
    )


def test_h03_direct_cross_request_current_attempt_is_rejected(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger, request_id="request-a")
    _request(ledger, request_id="request-b")
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    ledger.claim_application("request-b", application_attempt_id="attempt-b")
    _expect_rejected(
        connection,
        "UPDATE handa_live.effect_request SET current_attempt_id='attempt-b' "
        "WHERE effect_request_id='request-a'",
        needle="ownership",
    )


def test_h04_lifecycle_gap_is_rejected(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    _expect_rejected(
        connection,
        "INSERT INTO handa_live.lifecycle_event "
        "(effect_request_id,event_sequence,previous_state,next_state,event_kind,reason) "
        "VALUES ('request-a',3,'AUTHORIZED','APPLYING','INJECTED','gap')",
        needle="sequence",
    )


def test_h04_lifecycle_previous_state_must_match_projection(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    _expect_rejected(
        connection,
        "INSERT INTO handa_live.lifecycle_event "
        "(effect_request_id,event_sequence,previous_state,next_state,event_kind,reason) "
        "VALUES ('request-a',2,'APPLIED','APPLYING','INJECTED','wrong predecessor')",
        needle="previous state",
    )


def test_h01_c1_fault_before_claim_commit_establishes_no_owner(connection, monkeypatch):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)

    def fail_before_claim_commit(*args, **kwargs):
        raise RuntimeError("fault before claim commit")

    monkeypatch.setattr(ledger, "_event", fail_before_claim_commit)
    with pytest.raises(RuntimeError, match="before claim commit"):
        ledger.claim_application("request-a", application_attempt_id="attempt-a")

    assert ledger.get_application_state("request-a").state == "AUTHORIZED"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM handa_live.application_attempt "
            "WHERE effect_request_id='request-a'"
        )
        assert cursor.fetchone() == (0,)
        cursor.execute(
            "SELECT count(*) FROM handa_live.applied_effect "
            "WHERE effect_request_id='request-a'"
        )
        assert cursor.fetchone() == (0,)

    # The same request remains claimable after the injected pre-commit failure.
    monkeypatch.setattr(ledger, "_event", _postgres.EffectApplicationLedger._event)
    assert ledger.claim_application(
        "request-a", application_attempt_id="attempt-a"
    ).state == "APPLYING"


def test_h01_c2_durable_claim_requires_positive_no_call_proof(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    assert ledger.claim_application(
        "request-a", application_attempt_id="attempt-a"
    ).state == "APPLYING"

    with pytest.raises(EffectApplicationLedgerError, match="positive non-mutation"):
        ledger.mark_failed_without_effect(
            "request-a",
            application_attempt_id="attempt-a",
            evidence=[{"evidence_id": "worker-gone", "proof_type": "PROCESS_DISAPPEARED"}],
        )

    state = ledger.mark_failed_without_effect(
        "request-a",
        application_attempt_id="attempt-a",
        evidence=[{"evidence_id": "no-call", "proof_type": "NO_CALL_STARTED"}],
    )
    assert state.state == "FAILED_WITHOUT_EFFECT"


def test_h01_c5_lost_acknowledgement_discovers_existing_applied_result(connection):
    _base(connection)
    first_ledger = _ledger(connection)
    _request(first_ledger)
    first_ledger.claim_application("request-a", application_attempt_id="attempt-a")
    first_ledger.mark_applied(
        "request-a", application_attempt_id="attempt-a", receipt=_postgres._receipt()
    )

    # The caller acknowledgement is intentionally discarded. A new caller
    # must discover the durable result rather than apply again.
    second_ledger = _ledger(connection)
    state = second_ledger.get_application_state("request-a")
    assert state.state == "APPLIED"
    assert state.applied_effect_id is not None
    with pytest.raises(EffectApplicationLedgerError, match="not claimable"):
        second_ledger.claim_application("request-a", application_attempt_id="attempt-b")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM handa_live.applied_effect "
            "WHERE effect_request_id='request-a'"
        )
        assert cursor.fetchone() == (1,)
