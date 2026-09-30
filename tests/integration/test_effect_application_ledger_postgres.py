"""PostgreSQL falsifiers for the Effect Application Ledger foundation."""

import os
import hashlib
import base64
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest
from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

from core.persistence.effect_application_ledger import (
    EffectApplicationLedger,
    EffectApplicationLedgerError,
)


ROOT = Path(__file__).parents[2]
MIGRATIONS = [
    ROOT / "core" / "persistence" / "migrations" / name
    for name in (
        "001_create_handa_live.sql",
        "002_relax_may_have_been_submitted_certainty.sql",
        "003_reconciliation_evidence.sql",
        "004_external_order_observation_contract.sql",
        "005_decision_ledger.sql",
        "006_effect_application_ledger.sql",
    )
]
DB_NAME = "handa_test"
DB_USER = "handa_test"
DB_HOSTS = {"127.0.0.1", "localhost"}
DB_PORT = 55432


def _database_url():
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.fail("TEST_DATABASE_URL is required; refusing database falsifier.")
    parsed = urlparse(value)
    if (
        parsed.hostname not in DB_HOSTS
        or parsed.port != DB_PORT
        or parsed.path.lstrip("/") != DB_NAME
        or parsed.username != DB_USER
    ):
        pytest.fail("TEST_DATABASE_URL is not the authorized local disposable database.")
    return value


def _connect():
    return psycopg2.connect(_database_url())


@pytest.fixture()
def connection():
    connection = _connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
            for migration in MIGRATIONS:
                cursor.execute(migration.read_text(encoding="utf-8"))
        connection.commit()
        yield connection
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("DROP SCHEMA IF EXISTS handa_live CASCADE")
        connection.commit()
        connection.close()


def _intent(connection, intent_id="intent-a"):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.order_intent
            (intent_id, venue, account_scope, client_order_id, slot_id, symbol,
             side, requested_quote_amount, submission_lifecycle_state)
            VALUES (%s, 'BINANCE_SPOT', 'test-account', %s, %s, 'BTCUSDC',
                    'BUY', 10, 'READY_TO_SUBMIT')
            """,
            (intent_id, f"client-{intent_id}", f"slot-{intent_id}"),
        )


def _context(connection, context_id="context-a", intent_id="intent-a", sequence=1):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.reconciliation_context
            (context_id, intent_id, context_sequence, context_state)
            VALUES (%s, %s, %s, 'ACTIVE')
            """,
            (context_id, intent_id, sequence),
        )


def _decision(
    connection,
    decision_id="decision-a",
    context_id="context-a",
    intent_id="intent-a",
    sequence=1,
    authority_state="RESOLVED",
    contradiction=None,
):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO handa_live.semantic_decision
            (decision_id, context_id, intent_id, decision_sequence, evaluation_time,
             decision_scope, authority_state, execution_occurred,
             order_outcome_terminal, execution_extent, final_partial_outcome,
             evaluated_input_snapshot, authority_contract_version,
             decision_schema_version, evidence_normalization_version,
             lineage_completeness_status, contradiction_result)
            VALUES (%s, %s, %s, %s, %s, 'ORDER_OUTCOME', %s,
                    '{"value":"UNKNOWN"}', '{"value":"UNKNOWN"}',
                    '{"value":"UNKNOWN"}', '{"value":"UNKNOWN"}',
                    '{"source":"dbe"}', 'v1', 'v1', 'v1',
                    'LINEAGE_INCOMPLETE', %s::jsonb)
            """,
            (
                decision_id,
                context_id,
                intent_id,
                sequence,
                datetime.now(timezone.utc),
                authority_state,
                contradiction,
            ),
        )


def _base(connection, **decision_options):
    _intent(connection)
    _context(connection)
    _decision(connection, **decision_options)
    connection.commit()


def _ledger(connection):
    return EffectApplicationLedger(connection, trusted_issuers=TEST_TRUSTED_ISSUERS)


TEST_PRIVATE_KEY = ECC.import_key(
    "-----BEGIN PRIVATE KEY-----\n"
    "MC4CAQAwBQYDK2VwBCIEIKdW5mXgZ2QfQmT8x5dB4mJjz0Kq1oP6j6qGv4sV7w8A\n"
    "-----END PRIVATE KEY-----"
)
TEST_PUBLIC_KEY = TEST_PRIVATE_KEY.public_key()
TEST_TRUSTED_ISSUERS = {
    "recovery-issuer": {
        "key_id": "recovery-key-1",
        "public_key": base64.b64encode(TEST_PUBLIC_KEY.export_key(format="DER")).decode("ascii"),
        "issuer_epoch": 7,
        "revoked_epochs": set(),
        "subjects": {"recovery-worker"},
        "policy_versions": {"v1"},
    }
}


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _recovery_capability(
    effect_request_id="request-a",
    application_attempt_id="attempt-a",
    allowed_classification="OUTCOME_UNKNOWN",
    evidence=None,
    **overrides,
):
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    evidence = evidence or [{"evidence_id": "query", "proof_type": "EXCHANGE_QUERY"}]
    capability = {
        "issuer_id": "recovery-issuer",
        "key_id": "recovery-key-1",
        "issuer_epoch": 7,
        "subject_id": "recovery-worker",
        "effect_request_id": effect_request_id,
        "application_attempt_id": application_attempt_id,
        "allowed_classification": allowed_classification,
        "recovery_policy_version": "v1",
        "evidence_digest": hashlib.sha256(_canonical_json(evidence)).hexdigest(),
        "issued_at": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "nonce": f"nonce-{effect_request_id}-{application_attempt_id}-{allowed_classification}",
    }
    capability.update(overrides)
    payload = {key: capability[key] for key in sorted(capability)}
    capability["signature"] = base64.b64encode(
        eddsa.new(TEST_PRIVATE_KEY, "rfc8032").sign(_canonical_json(payload))
    ).decode("ascii")
    return capability


def _request(ledger, request_id="request-a", decision_id="decision-a", sequence=1):
    return ledger.create_effect_request(
        effect_request_id=request_id,
        effect_type="TEST_EFFECT",
        intent_id="intent-a",
        reconciliation_context_id="context-a",
        authority_decision_id=decision_id,
        decision_sequence=sequence,
        authority_contract_version="v1",
    )


def _receipt(receipt_id="receipt-a"):
    return {
        "receipt_id": receipt_id,
        "schema_version": "opaque-v1",
        "producer_id": "test-producer",
        "payload": {"opaque": True, "receipt_id": receipt_id},
    }


def _expect_db_error(connection, statement, params=(), needle=None):
    with pytest.raises(psycopg2.Error) as error:
        with connection.cursor() as cursor:
            cursor.execute(statement, params)
    message = str(error.value)
    connection.rollback()
    if needle:
        assert needle in message, message
    return message


def test_dbe001_effect_request_identity_is_unique(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    with pytest.raises(EffectApplicationLedgerError):
        _request(ledger)


def test_dbe002_only_one_applied_effect_per_request(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    ledger.mark_applied("request-a", application_attempt_id="attempt-a", receipt=_receipt())
    _expect_db_error(
        connection,
        "INSERT INTO handa_live.applied_effect "
        "(applied_effect_id,effect_request_id,application_attempt_id,receipt_id,"
        "receipt_schema_version,producer_id,payload_hash,receipt_payload) "
        "VALUES ('applied-b','request-a','attempt-a','receipt-b','v1','p','h','{}')",
        needle="effect_request_id",
    )


def test_dbe003_concurrent_claims_have_one_effective_owner(connection):
    _base(connection)
    _request(_ledger(connection))

    def claim(attempt_id):
        conn = _connect()
        try:
            return _ledger(conn).claim_application(
                "request-a", application_attempt_id=attempt_id
            )
        except Exception as exc:  # each result is classified below
            return exc
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ("attempt-a", "attempt-b")))
    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, Exception) for result in results) == 1


def test_dbe004_stale_decision_cannot_claim(connection):
    _base(connection)
    _decision(connection, "decision-b", sequence=2)
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE handa_live.order_intent SET current_decision_id='decision-b' "
            "WHERE intent_id='intent-a'"
        )
    connection.commit()
    ledger = _ledger(connection)
    _request(ledger)
    with pytest.raises(EffectApplicationLedgerError, match="stale authority"):
        ledger.claim_application("request-a", application_attempt_id="attempt-a")


def test_dbe005_newer_decision_invalidates_older_authority(connection):
    _base(connection)
    _decision(connection, "decision-b", sequence=2)
    connection.commit()
    ledger = _ledger(connection)
    _request(ledger)
    with pytest.raises(EffectApplicationLedgerError, match="newer semantic decision"):
        ledger.claim_application("request-a", application_attempt_id="attempt-a")


def test_dbe006_later_contradiction_blocks_claim(connection):
    _base(connection)
    _decision(connection, "decision-b", sequence=2, authority_state="BLOCKED")
    connection.commit()
    ledger = _ledger(connection)
    _request(ledger)
    with pytest.raises(EffectApplicationLedgerError, match="later contradiction"):
        ledger.claim_application("request-a", application_attempt_id="attempt-a")


def test_dbe007_applied_history_is_immutable(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    ledger.mark_applied("request-a", application_attempt_id="attempt-a", receipt=_receipt())
    _expect_db_error(
        connection,
        "UPDATE handa_live.applied_effect SET producer_id='changed' "
        "WHERE effect_request_id='request-a'",
        needle="history is immutable",
    )


def test_dbe008_lifecycle_history_is_immutable(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    _expect_db_error(
        connection,
        "DELETE FROM handa_live.lifecycle_event WHERE effect_request_id='request-a'",
        needle="history is immutable",
    )


def test_dbe009_recovery_history_is_immutable(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    ledger.mark_outcome_unknown(
        "request-a", application_attempt_id="attempt-a", reason="lost response"
    )
    evidence = [{"evidence_id": "ev-unknown", "proof_type": "EXCHANGE_QUERY"}]
    ledger.recover_application(
        "request-a",
        recovery_authority_id="recovery-a",
        recovery_policy_version="v1",
        classification="OUTCOME_UNKNOWN",
        evidence=evidence,
        recovery_capability=_recovery_capability(evidence=evidence),
        recovery_subject_id="recovery-worker",
    )
    _expect_db_error(
        connection,
        "DELETE FROM handa_live.recovery_event "
        "WHERE effect_request_id='request-a'",
        needle="history is immutable",
    )


def test_dbe010_recovery_requires_authority_and_evidence(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    ledger.mark_outcome_unknown(
        "request-a", application_attempt_id="attempt-a", reason="lost response"
    )
    with pytest.raises(EffectApplicationLedgerError, match="recovery authority"):
        ledger.recover_application(
            "request-a", recovery_authority_id="", recovery_policy_version="v1",
            classification="OUTCOME_UNKNOWN", evidence=[{"evidence_id": "e"}],
        )


def test_dbe011_failed_without_effect_requires_positive_proof(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    with pytest.raises(EffectApplicationLedgerError, match="positive non-mutation"):
        ledger.mark_failed_without_effect(
            "request-a", application_attempt_id="attempt-a", evidence=[]
        )


def test_dbe012_outcome_unknown_cannot_replay_without_recovery(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    ledger.mark_outcome_unknown(
        "request-a", application_attempt_id="attempt-a", reason="lost response"
    )
    with pytest.raises(EffectApplicationLedgerError, match="not claimable"):
        ledger.claim_application("request-a", application_attempt_id="attempt-b")


def test_dbe013_recovery_applied_requires_receipt(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    ledger.mark_outcome_unknown(
        "request-a", application_attempt_id="attempt-a", reason="lost response"
    )
    with pytest.raises(EffectApplicationLedgerError, match="requires receipt"):
        ledger.recover_application(
            "request-a", recovery_authority_id="recovery-a",
            recovery_policy_version="v1", classification="APPLIED",
            evidence=[{"evidence_id": "receipt-proof"}],
        )


def test_dbe014_recovery_failed_requires_nonmutation_proof(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    ledger.mark_outcome_unknown(
        "request-a", application_attempt_id="attempt-a", reason="lost response"
    )
    with pytest.raises(EffectApplicationLedgerError, match="positive non-mutation"):
        ledger.recover_application(
            "request-a", recovery_authority_id="recovery-a",
            recovery_policy_version="v1", classification="FAILED_WITHOUT_EFFECT",
            evidence=[{"evidence_id": "weak", "proof_type": "ABSENCE"}],
        )


def test_dbe015_recovery_unknown_is_durable_and_audited(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    ledger.mark_outcome_unknown(
        "request-a", application_attempt_id="attempt-a", reason="lost response"
    )
    evidence = [{"evidence_id": "still-unknown", "proof_type": "EXCHANGE_QUERY"}]
    state = ledger.recover_application(
        "request-a", recovery_authority_id="recovery-a",
        recovery_policy_version="v1", classification="OUTCOME_UNKNOWN",
        evidence=evidence,
        recovery_capability=_recovery_capability(evidence=evidence),
        recovery_subject_id="recovery-worker",
    )
    assert state.state == "OUTCOME_UNKNOWN"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM handa_live.recovery_event "
            "WHERE effect_request_id='request-a'"
        )
        assert cursor.fetchone() == (1,)


def test_dbe016_rollback_leaves_no_false_applied_history(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    with pytest.raises(psycopg2.Error):
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO handa_live.applied_effect "
                "(applied_effect_id,effect_request_id,application_attempt_id,receipt_id,"
                "receipt_schema_version,producer_id,payload_hash,receipt_payload) "
                "VALUES ('bad','missing','attempt-a','bad','v1','p','h','{}')"
            )
    connection.rollback()
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM handa_live.applied_effect")
        assert cursor.fetchone() == (0,)


def test_dbe017_duplicate_applied_call_cannot_mutate_again(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    ledger.mark_applied("request-a", application_attempt_id="attempt-a", receipt=_receipt())
    with pytest.raises(EffectApplicationLedgerError, match="not current"):
        ledger.mark_applied("request-a", application_attempt_id="attempt-a", receipt=_receipt("b"))


def test_dbe018_applied_receipt_is_opaque_and_hash_bound(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    ledger.mark_applied("request-a", application_attempt_id="attempt-a", receipt=_receipt())
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT receipt_id, payload_hash, receipt_payload->>'opaque' "
            "FROM handa_live.applied_effect WHERE effect_request_id='request-a'"
        )
        assert cursor.fetchone() == ("receipt-a", hashlib.sha256(
            b'{"opaque":true,"receipt_id":"receipt-a"}'
        ).hexdigest(), "true")


def test_dbe019_legacy_submission_attempt_is_not_reinterpreted(connection):
    _base(connection)
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO handa_live.submission_attempt "
            "(attempt_id,intent_id,attempt_sequence,venue,account_scope,"
            "client_order_id,submission_lifecycle_state) "
            "VALUES ('legacy-attempt','intent-a',1,'BINANCE_SPOT',"
            "'test-account','client-intent-a','MAY_HAVE_BEEN_SUBMITTED')"
        )
    connection.commit()
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM handa_live.application_attempt")
        assert cursor.fetchone() == (0,)


def test_dbe020_effect_request_requires_composite_context_identity(connection):
    _base(connection)
    with pytest.raises(EffectApplicationLedgerError):
        _ledger(connection).create_effect_request(
            effect_request_id="request-a", effect_type="TEST_EFFECT",
            intent_id="intent-a", reconciliation_context_id="context-missing",
            authority_decision_id="decision-a", decision_sequence=1,
            authority_contract_version="v1",
        )


def test_dbe021_authority_binding_is_append_only(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    _expect_db_error(
        connection,
        "UPDATE handa_live.authority_binding SET decision_sequence=2 "
        "WHERE effect_request_id='request-a'",
        needle="history is immutable",
    )


def test_dbe022_current_attempt_fk_rejects_unknown_attempt(connection):
    _base(connection)
    _request(_ledger(connection))
    _expect_db_error(
        connection,
        "UPDATE handa_live.effect_request SET current_attempt_id='missing' "
        "WHERE effect_request_id='request-a'",
        needle="ownership mismatch",
    )


def test_dbe023_recovery_does_not_create_synthetic_semantic_history(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    ledger.mark_outcome_unknown(
        "request-a", application_attempt_id="attempt-a", reason="lost response"
    )
    evidence = [{"evidence_id": "unknown", "proof_type": "EXCHANGE_QUERY"}]
    ledger.recover_application(
        "request-a", recovery_authority_id="recovery-a",
        recovery_policy_version="v1", classification="OUTCOME_UNKNOWN",
        evidence=evidence,
        recovery_capability=_recovery_capability(evidence=evidence),
        recovery_subject_id="recovery-worker",
    )
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM handa_live.semantic_decision")
        assert cursor.fetchone() == (1,)


def test_dbe024_failed_state_is_replay_safe(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    state = ledger.mark_failed_without_effect(
        "request-a", application_attempt_id="attempt-a",
        evidence=[{"evidence_id": "rollback", "proof_type": "TRANSACTION_ROLLBACK"}],
    )
    assert state.state == "FAILED_WITHOUT_EFFECT"
    with pytest.raises(EffectApplicationLedgerError, match="not claimable"):
        ledger.claim_application("request-a", application_attempt_id="attempt-b")


def test_dbe025_recovery_applied_is_durable_once(connection):
    _base(connection)
    ledger = _ledger(connection)
    _request(ledger)
    ledger.claim_application("request-a", application_attempt_id="attempt-a")
    ledger.mark_outcome_unknown(
        "request-a", application_attempt_id="attempt-a", reason="lost response"
    )
    evidence = [{"evidence_id": "receipt-proof", "proof_type": "RECEIPT"}]
    first = ledger.recover_application(
        "request-a", recovery_authority_id="recovery-a",
        recovery_policy_version="v1", classification="APPLIED",
        evidence=evidence,
        recovery_capability=_recovery_capability(
            allowed_classification="APPLIED", evidence=evidence,
        ),
        recovery_subject_id="recovery-worker",
        receipt=_receipt(),
    )
    assert first.state == "APPLIED"
    with pytest.raises(EffectApplicationLedgerError, match="not recoverable"):
        ledger.recover_application(
            "request-a", recovery_authority_id="recovery-a",
            recovery_policy_version="v1", classification="APPLIED",
            evidence=[{"evidence_id": "receipt-proof", "proof_type": "RECEIPT"}],
            receipt=_receipt(),
            recovery_capability=_recovery_capability(
                allowed_classification="APPLIED", evidence=evidence,
            ),
            recovery_subject_id="recovery-worker",
        )
