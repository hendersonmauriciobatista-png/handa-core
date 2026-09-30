"""Expected RED controls for signed recovery-capability authority."""

import pytest

from core.persistence.effect_application_ledger import EffectApplicationLedgerError
from tests.integration import test_effect_application_ledger_postgres as _postgres
from tests.integration.test_effect_application_ledger_hardening import _unknown_request


connection = _postgres.connection


def _capability(**overrides):
    return _postgres._recovery_capability(**overrides)


def _evidence():
    return [{"evidence_id": "query", "proof_type": "EXCHANGE_QUERY"}]


def _recover_with_capability(ledger, capability, evidence=None, classification=None):
    evidence = evidence or _evidence()
    classification = classification or capability["allowed_classification"]
    try:
        return ledger.recover_application(
            "request-a",
            recovery_authority_id=capability["issuer_id"],
            recovery_policy_version=capability["recovery_policy_version"],
            classification=classification,
            evidence=evidence,
            application_attempt_id=capability["application_attempt_id"],
            recovery_capability=capability,
            recovery_subject_id=capability["subject_id"],
        )
    except TypeError as error:
        pytest.fail(
            "VALID_RED: recovery API has no signed recovery capability validation: "
            f"{error}",
            pytrace=False,
        )


def test_h02_01_arbitrary_recovery_authority_id_is_not_authority(connection):
    ledger = _unknown_request(connection)
    with pytest.raises(EffectApplicationLedgerError, match="issuer|authority|capability"):
        ledger.recover_application(
            "request-a",
            recovery_authority_id="invented-by-worker",
            recovery_policy_version="v1",
            classification="OUTCOME_UNKNOWN",
            evidence=_evidence(),
        )


def test_h02_02_invalid_signature_is_rejected(connection):
    ledger = _unknown_request(connection)
    with pytest.raises(EffectApplicationLedgerError, match="signature|capability"):
        _recover_with_capability(ledger, _capability(signature="invalid"))


def test_h02_03_unknown_issuer_is_rejected(connection):
    ledger = _unknown_request(connection)
    with pytest.raises(EffectApplicationLedgerError, match="issuer|capability"):
        _recover_with_capability(ledger, _capability(issuer_id="unknown-issuer"))


def test_h02_04_unknown_key_is_rejected(connection):
    ledger = _unknown_request(connection)
    with pytest.raises(EffectApplicationLedgerError, match="key|capability"):
        _recover_with_capability(ledger, _capability(key_id="unknown-key"))


def test_h02_05_revoked_epoch_is_rejected(connection):
    ledger = _unknown_request(connection)
    with pytest.raises(EffectApplicationLedgerError, match="epoch|revoked|capability"):
        _recover_with_capability(ledger, _capability(issuer_epoch=6))


def test_h02_06_cross_request_capability_reuse_is_rejected(connection):
    ledger = _unknown_request(connection)
    with pytest.raises(EffectApplicationLedgerError, match="request|binding|capability"):
        _recover_with_capability(ledger, _capability(effect_request_id="request-b"))


def test_h02_07_cross_attempt_capability_reuse_is_rejected(connection):
    ledger = _unknown_request(connection)
    with pytest.raises(EffectApplicationLedgerError, match="attempt|binding|capability"):
        _recover_with_capability(ledger, _capability(application_attempt_id="attempt-b"))


def test_h02_08_wrong_classification_is_rejected(connection):
    ledger = _unknown_request(connection)
    capability = _capability(allowed_classification="APPLIED")
    with pytest.raises(EffectApplicationLedgerError, match="classification|capability"):
        _recover_with_capability(ledger, capability, classification="OUTCOME_UNKNOWN")


def test_h02_09_wrong_policy_version_is_rejected(connection):
    ledger = _unknown_request(connection)
    with pytest.raises(EffectApplicationLedgerError, match="policy|capability"):
        _recover_with_capability(ledger, _capability(recovery_policy_version="v0"))


def test_h02_10_evidence_digest_substitution_is_rejected(connection):
    ledger = _unknown_request(connection)
    evidence = [{"evidence_id": "substituted", "proof_type": "EXCHANGE_QUERY"}]
    capability = _capability(evidence=_evidence())
    with pytest.raises(EffectApplicationLedgerError, match="evidence|digest|capability"):
        _recover_with_capability(ledger, capability, evidence)


def test_h02_11_not_yet_valid_capability_is_rejected(connection):
    ledger = _unknown_request(connection)
    with pytest.raises(EffectApplicationLedgerError, match="time|valid|capability"):
        _recover_with_capability(ledger, _capability(issued_at="2026-09-30T00:10:00Z"))


def test_h02_12_expired_capability_is_rejected(connection):
    ledger = _unknown_request(connection)
    with pytest.raises(EffectApplicationLedgerError, match="expired|time|capability"):
        _recover_with_capability(ledger, _capability(expires_at="2026-09-28T23:00:00Z"))


def test_h02_13_nonce_replay_is_rejected(connection):
    ledger = _unknown_request(connection)
    capability = _capability()
    _recover_with_capability(ledger, capability)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM handa_live.recovery_capability_consumption "
            "WHERE nonce=%s",
            (capability["nonce"],),
        )
        assert cursor.fetchone() == (1,)
    with pytest.raises(EffectApplicationLedgerError, match="recoverable|nonce|replay|capability"):
        _recover_with_capability(ledger, capability)


def test_h02_14_worker_self_authorization_is_rejected(connection):
    ledger = _unknown_request(connection)
    capability = _capability(subject_id="ordinary-worker", issuer_id="ordinary-worker")
    with pytest.raises(EffectApplicationLedgerError, match="subject|issuer|capability"):
        _recover_with_capability(ledger, capability)


def test_h02_15_recovery_capability_cannot_grant_operational_authority(connection):
    ledger = _unknown_request(connection)
    capability = _capability(allowed_classification="RESUBMIT")
    with pytest.raises(EffectApplicationLedgerError, match="operational|classification|capability"):
        _recover_with_capability(ledger, capability, classification="RESUBMIT")


def test_h02_16_capability_consumption_is_atomic_with_recovery(connection, monkeypatch):
    ledger = _unknown_request(connection)
    capability = _capability()
    original_event = ledger._event

    def fail_after_consumption(*args, **kwargs):
        raise RuntimeError("simulated recovery transition failure")

    monkeypatch.setattr(ledger, "_event", fail_after_consumption)
    with pytest.raises(RuntimeError, match="transition failure"):
        _recover_with_capability(ledger, capability)
    monkeypatch.setattr(ledger, "_event", original_event)
    _recover_with_capability(ledger, capability)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM handa_live.recovery_capability_consumption "
            "WHERE nonce=%s",
            (capability["nonce"],),
        )
        assert cursor.fetchone() == (1,)
