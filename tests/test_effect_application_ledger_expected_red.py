"""Evolved ER controls backed by the PostgreSQL falsifiers."""

from tests.integration import test_effect_application_ledger_postgres as _postgres


connection = _postgres.connection


def test_er001_duplicate_effect_request_cannot_create_second_application(connection):
    _postgres.test_dbe001_effect_request_identity_is_unique(connection)


def test_er002_one_applied_effect_per_request(connection):
    _postgres.test_dbe002_only_one_applied_effect_per_request(connection)


def test_er003_concurrent_claim_has_one_effective_owner(connection):
    _postgres.test_dbe003_concurrent_claims_have_one_effective_owner(connection)


def test_er004_stale_semantic_decision_cannot_claim(connection):
    _postgres.test_dbe004_stale_decision_cannot_claim(connection)


def test_er005_newer_decision_invalidates_older_authority(connection):
    _postgres.test_dbe005_newer_decision_invalidates_older_authority(connection)


def test_er006_later_contradiction_blocks_application(connection):
    _postgres.test_dbe006_later_contradiction_blocks_claim(connection)


def test_er007_applied_history_is_immutable(connection):
    _postgres.test_dbe007_applied_history_is_immutable(connection)


def test_er008_lifecycle_history_is_immutable(connection):
    _postgres.test_dbe008_lifecycle_history_is_immutable(connection)


def test_er009_recovery_history_is_immutable(connection):
    _postgres.test_dbe009_recovery_history_is_immutable(connection)


def test_er010_recovery_requires_authority(connection):
    _postgres.test_dbe010_recovery_requires_authority_and_evidence(connection)


def test_er011_failed_without_effect_requires_positive_proof(connection):
    _postgres.test_dbe011_failed_without_effect_requires_positive_proof(connection)


def test_er012_unknown_outcome_cannot_replay(connection):
    _postgres.test_dbe012_outcome_unknown_cannot_replay_without_recovery(connection)


def test_er013_recovery_applied_requires_receipt(connection):
    _postgres.test_dbe013_recovery_applied_requires_receipt(connection)


def test_er014_recovery_failed_requires_nonmutation_proof(connection):
    _postgres.test_dbe014_recovery_failed_requires_nonmutation_proof(connection)


def test_er015_recovery_unknown_is_audited(connection):
    _postgres.test_dbe015_recovery_unknown_is_durable_and_audited(connection)


def test_er016_rollback_leaves_no_false_applied_history(connection):
    _postgres.test_dbe016_rollback_leaves_no_false_applied_history(connection)


def test_er017_duplicate_applied_call_is_rejected(connection):
    _postgres.test_dbe017_duplicate_applied_call_cannot_mutate_again(connection)


def test_er018_receipt_is_opaque_and_hash_bound(connection):
    _postgres.test_dbe018_applied_receipt_is_opaque_and_hash_bound(connection)


def test_er019_legacy_submission_attempt_is_not_reinterpreted(connection):
    _postgres.test_dbe019_legacy_submission_attempt_is_not_reinterpreted(connection)


def test_er020_mismatched_identity_cannot_bind_request(connection):
    _postgres.test_dbe020_effect_request_requires_composite_context_identity(connection)
