-- Durable structural contracts for the future submission-authority issuer.
-- This migration creates persistence only.  It does not expose approval,
-- activation, evaluation, issuance, or claim APIs.

CREATE SEQUENCE handa_live.authority_envelope_version_seq
    AS BIGINT
    START WITH 1
    INCREMENT BY 1
    MINVALUE 1;

CREATE TABLE handa_live.authority_envelope (
    authority_envelope_id TEXT PRIMARY KEY,
    envelope_version BIGINT NOT NULL
        DEFAULT nextval('handa_live.authority_envelope_version_seq'),
    runtime_mode TEXT NOT NULL,
    venue TEXT NOT NULL,
    account_scope TEXT NOT NULL,
    allowed_sides TEXT[] NOT NULL,
    strategy_version TEXT NOT NULL,
    decision_contract_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    risk_policy_version TEXT NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ NOT NULL,
    configuration_digest TEXT NOT NULL,
    authority_contract_version TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approval_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT authority_envelope_version_uq
        UNIQUE (envelope_version),
    CONSTRAINT authority_envelope_version_ck
        CHECK (envelope_version > 0),
    CONSTRAINT authority_envelope_validity_ck
        CHECK (valid_from < valid_until),
    CONSTRAINT authority_envelope_sides_ck
        CHECK (
            cardinality(allowed_sides) BETWEEN 1 AND 2
            AND array_position(allowed_sides, NULL) IS NULL
            AND allowed_sides <@ ARRAY['BUY', 'SELL']::TEXT[]
            AND (
                cardinality(allowed_sides) = 1
                OR allowed_sides[1] <> allowed_sides[2]
            )
        ),
    CONSTRAINT authority_envelope_text_ck
        CHECK (
            btrim(authority_envelope_id) <> ''
            AND btrim(runtime_mode) <> ''
            AND btrim(venue) <> ''
            AND btrim(account_scope) <> ''
            AND btrim(strategy_version) <> ''
            AND btrim(decision_contract_version) <> ''
            AND btrim(policy_version) <> ''
            AND btrim(risk_policy_version) <> ''
            AND btrim(configuration_digest) <> ''
            AND btrim(authority_contract_version) <> ''
            AND btrim(approved_by) <> ''
            AND btrim(approval_reason) <> ''
        )
);

CREATE INDEX authority_envelope_scope_idx
    ON handa_live.authority_envelope (venue, account_scope, valid_until);

CREATE OR REPLACE FUNCTION handa_live.guard_authority_envelope_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'authority envelope definitions are immutable';
END;
$$;

CREATE TRIGGER authority_envelope_immutability_guard
BEFORE UPDATE OR DELETE
ON handa_live.authority_envelope
FOR EACH ROW
EXECUTE FUNCTION handa_live.guard_authority_envelope_immutability();

CREATE TABLE handa_live.authority_envelope_event (
    event_id TEXT PRIMARY KEY,
    authority_envelope_id TEXT NOT NULL
        REFERENCES handa_live.authority_envelope(authority_envelope_id),
    event_sequence BIGINT NOT NULL CHECK (event_sequence > 0),
    event_type TEXT NOT NULL
        CHECK (event_type IN ('ACTIVATED', 'REVOKED', 'SUPERSEDED')),
    actor_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    safety_epoch_after BIGINT NOT NULL CHECK (safety_epoch_after >= 0),
    runtime_generation_after BIGINT NOT NULL CHECK (runtime_generation_after >= 0),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT authority_envelope_event_sequence_uq
        UNIQUE (authority_envelope_id, event_sequence),
    CONSTRAINT authority_envelope_event_text_ck
        CHECK (
            btrim(event_id) <> ''
            AND btrim(actor_id) <> ''
            AND btrim(reason) <> ''
        )
);

CREATE INDEX authority_envelope_event_history_idx
    ON handa_live.authority_envelope_event
       (authority_envelope_id, event_sequence);

CREATE OR REPLACE FUNCTION handa_live.guard_authority_envelope_event_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'authority envelope event history is immutable';
END;
$$;

CREATE TRIGGER authority_envelope_event_immutability_guard
BEFORE UPDATE OR DELETE
ON handa_live.authority_envelope_event
FOR EACH ROW
EXECUTE FUNCTION handa_live.guard_authority_envelope_event_immutability();

CREATE TABLE handa_live.operational_authority_state (
    state_id BOOLEAN PRIMARY KEY,
    operational_mode TEXT NOT NULL,
    active_authority_envelope_id TEXT NULL
        REFERENCES handa_live.authority_envelope(authority_envelope_id),
    global_safety_epoch BIGINT NOT NULL CHECK (global_safety_epoch >= 0),
    runtime_generation BIGINT NOT NULL CHECK (runtime_generation >= 0),
    current_version BIGINT NOT NULL CHECK (current_version >= 0),
    last_event_id TEXT NULL
        REFERENCES handa_live.authority_envelope_event(event_id),
    changed_by TEXT NOT NULL,
    change_reason TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT operational_authority_state_singleton_ck
        CHECK (state_id IS TRUE),
    CONSTRAINT operational_authority_state_text_ck
        CHECK (
            btrim(operational_mode) <> ''
            AND btrim(changed_by) <> ''
            AND btrim(change_reason) <> ''
        )
);

INSERT INTO handa_live.operational_authority_state (
    state_id,
    operational_mode,
    active_authority_envelope_id,
    global_safety_epoch,
    runtime_generation,
    current_version,
    last_event_id,
    changed_by,
    change_reason
) VALUES (
    TRUE,
    'OBSERVE_ONLY',
    NULL,
    0,
    0,
    0,
    NULL,
    'migration-010',
    'fail-safe authority state initialization'
);

CREATE TABLE handa_live.pre_execution_decision (
    pre_execution_decision_id TEXT PRIMARY KEY,
    intent_id TEXT NOT NULL
        REFERENCES handa_live.order_intent(intent_id),
    submission_attempt_id TEXT NOT NULL,
    authority_envelope_id TEXT NOT NULL
        REFERENCES handa_live.authority_envelope(authority_envelope_id),
    decision_sequence BIGINT NOT NULL CHECK (decision_sequence > 0),
    decision_outcome TEXT NOT NULL
        CHECK (decision_outcome IN ('ALLOW', 'BLOCK')),
    decision_reason TEXT NOT NULL,
    intent_semantic_digest TEXT NOT NULL,
    submission_attempt_semantic_digest TEXT NOT NULL,
    decision_contract_version TEXT NOT NULL,
    decision_engine_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    risk_policy_version TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    input_snapshot_digest TEXT NOT NULL,
    decision_semantics_digest TEXT NOT NULL,
    global_safety_epoch BIGINT NOT NULL CHECK (global_safety_epoch >= 0),
    runtime_generation BIGINT NOT NULL CHECK (runtime_generation >= 0),
    runtime_mode TEXT NOT NULL,
    venue TEXT NOT NULL,
    account_scope TEXT NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pre_execution_decision_attempt_lineage_fk
        FOREIGN KEY (submission_attempt_id, intent_id)
        REFERENCES handa_live.submission_attempt(attempt_id, intent_id),
    CONSTRAINT pre_execution_decision_sequence_uq
        UNIQUE (submission_attempt_id, decision_sequence),
    CONSTRAINT pre_execution_decision_composite_identity_uq
        UNIQUE (
            pre_execution_decision_id,
            intent_id,
            submission_attempt_id
        ),
    CONSTRAINT pre_execution_decision_validity_ck
        CHECK (valid_until > evaluated_at),
    CONSTRAINT pre_execution_decision_text_ck
        CHECK (
            btrim(pre_execution_decision_id) <> ''
            AND btrim(decision_reason) <> ''
            AND btrim(intent_semantic_digest) <> ''
            AND btrim(submission_attempt_semantic_digest) <> ''
            AND btrim(decision_contract_version) <> ''
            AND btrim(decision_engine_version) <> ''
            AND btrim(policy_version) <> ''
            AND btrim(risk_policy_version) <> ''
            AND btrim(strategy_version) <> ''
            AND btrim(input_snapshot_digest) <> ''
            AND btrim(decision_semantics_digest) <> ''
            AND btrim(runtime_mode) <> ''
            AND btrim(venue) <> ''
            AND btrim(account_scope) <> ''
        )
);

CREATE INDEX pre_execution_decision_currentness_idx
    ON handa_live.pre_execution_decision
       (submission_attempt_id, decision_sequence DESC);

CREATE OR REPLACE FUNCTION handa_live.guard_pre_execution_decision_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'pre-execution decisions are immutable';
END;
$$;

CREATE TRIGGER pre_execution_decision_immutability_guard
BEFORE UPDATE OR DELETE
ON handa_live.pre_execution_decision
FOR EACH ROW
EXECUTE FUNCTION handa_live.guard_pre_execution_decision_immutability();

ALTER TABLE handa_live.submission_authorization
    ADD CONSTRAINT submission_authorization_decision_lineage_fk
    FOREIGN KEY (
        authority_reference_id,
        intent_id,
        submission_attempt_id
    )
    REFERENCES handa_live.pre_execution_decision (
        pre_execution_decision_id,
        intent_id,
        submission_attempt_id
    );
