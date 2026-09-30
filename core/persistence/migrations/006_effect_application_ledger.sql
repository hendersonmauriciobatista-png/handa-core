CREATE TABLE handa_live.effect_request (
    effect_request_id TEXT PRIMARY KEY,
    effect_type TEXT NOT NULL,
    intent_id TEXT NOT NULL,
    reconciliation_context_id TEXT NOT NULL,
    current_state TEXT NOT NULL CHECK (
        current_state IN (
            'AUTHORIZED', 'APPLYING', 'APPLIED',
            'FAILED_WITHOUT_EFFECT', 'OUTCOME_UNKNOWN'
        )
    ),
    current_attempt_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (effect_request_id, intent_id),
    FOREIGN KEY (intent_id) REFERENCES handa_live.order_intent(intent_id),
    FOREIGN KEY (reconciliation_context_id, intent_id)
        REFERENCES handa_live.reconciliation_context(context_id, intent_id)
);

CREATE TABLE handa_live.authority_binding (
    effect_request_id TEXT PRIMARY KEY
        REFERENCES handa_live.effect_request(effect_request_id),
    authority_decision_id TEXT NOT NULL,
    intent_id TEXT NOT NULL,
    reconciliation_context_id TEXT NOT NULL,
    decision_sequence BIGINT NOT NULL CHECK (decision_sequence > 0),
    authority_contract_version TEXT NOT NULL,
    bound_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (authority_decision_id, intent_id)
        REFERENCES handa_live.semantic_decision(decision_id, intent_id),
    FOREIGN KEY (reconciliation_context_id, intent_id)
        REFERENCES handa_live.reconciliation_context(context_id, intent_id),
    FOREIGN KEY (effect_request_id, intent_id)
        REFERENCES handa_live.effect_request(effect_request_id, intent_id),
    UNIQUE (effect_request_id, authority_decision_id, intent_id)
);

CREATE TABLE handa_live.application_attempt (
    application_attempt_id TEXT PRIMARY KEY,
    effect_request_id TEXT NOT NULL
        REFERENCES handa_live.effect_request(effect_request_id),
    attempt_state TEXT NOT NULL CHECK (
        attempt_state IN (
            'APPLYING', 'APPLIED', 'FAILED_WITHOUT_EFFECT', 'OUTCOME_UNKNOWN'
        )
    ),
    claimant_id TEXT NOT NULL,
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    UNIQUE (application_attempt_id, effect_request_id)
);

CREATE UNIQUE INDEX effect_application_one_active_attempt
    ON handa_live.application_attempt (effect_request_id)
    WHERE attempt_state = 'APPLYING';

ALTER TABLE handa_live.effect_request
    ADD CONSTRAINT effect_request_current_attempt_fk
    FOREIGN KEY (current_attempt_id)
    REFERENCES handa_live.application_attempt(application_attempt_id);

CREATE TABLE handa_live.applied_effect (
    applied_effect_id TEXT PRIMARY KEY,
    effect_request_id TEXT NOT NULL UNIQUE
        REFERENCES handa_live.effect_request(effect_request_id),
    application_attempt_id TEXT NOT NULL
        REFERENCES handa_live.application_attempt(application_attempt_id),
    receipt_id TEXT NOT NULL,
    receipt_schema_version TEXT NOT NULL,
    producer_id TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    receipt_payload JSONB NOT NULL,
    evidence_ids TEXT[] NOT NULL DEFAULT '{}',
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (receipt_id),
    UNIQUE (applied_effect_id, effect_request_id)
);

CREATE TABLE handa_live.lifecycle_event (
    lifecycle_event_id BIGSERIAL PRIMARY KEY,
    effect_request_id TEXT NOT NULL
        REFERENCES handa_live.effect_request(effect_request_id),
    event_sequence BIGINT NOT NULL,
    previous_state TEXT,
    next_state TEXT NOT NULL CHECK (
        next_state IN (
            'AUTHORIZED', 'APPLYING', 'APPLIED',
            'FAILED_WITHOUT_EFFECT', 'OUTCOME_UNKNOWN'
        )
    ),
    event_kind TEXT NOT NULL,
    reason TEXT NOT NULL,
    application_attempt_id TEXT,
    recovery_authority_id TEXT,
    recovery_policy_version TEXT,
    evidence_ids TEXT[] NOT NULL DEFAULT '{}',
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (effect_request_id, event_sequence)
);

CREATE TABLE handa_live.recovery_event (
    recovery_event_id BIGSERIAL PRIMARY KEY,
    effect_request_id TEXT NOT NULL
        REFERENCES handa_live.effect_request(effect_request_id),
    application_attempt_id TEXT,
    previous_state TEXT NOT NULL,
    resulting_state TEXT NOT NULL CHECK (
        resulting_state IN ('APPLIED', 'FAILED_WITHOUT_EFFECT', 'OUTCOME_UNKNOWN')
    ),
    recovery_authority_id TEXT NOT NULL,
    recovery_policy_version TEXT NOT NULL,
    evidence_ids TEXT[] NOT NULL DEFAULT '{}',
    reason TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE handa_live.recovery_capability_consumption (
    issuer_id TEXT NOT NULL,
    key_id TEXT NOT NULL,
    issuer_epoch BIGINT NOT NULL CHECK (issuer_epoch > 0),
    nonce TEXT NOT NULL,
    effect_request_id TEXT NOT NULL
        REFERENCES handa_live.effect_request(effect_request_id),
    application_attempt_id TEXT NOT NULL,
    consumed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (issuer_id, key_id, issuer_epoch, nonce),
    FOREIGN KEY (application_attempt_id, effect_request_id)
        REFERENCES handa_live.application_attempt(application_attempt_id, effect_request_id)
);

CREATE OR REPLACE FUNCTION handa_live.reject_effect_ledger_history_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'effect application ledger history is immutable';
END;
$$;

CREATE TRIGGER authority_binding_immutable
BEFORE UPDATE OR DELETE ON handa_live.authority_binding
FOR EACH ROW EXECUTE FUNCTION handa_live.reject_effect_ledger_history_mutation();

CREATE TRIGGER applied_effect_immutable
BEFORE UPDATE OR DELETE ON handa_live.applied_effect
FOR EACH ROW EXECUTE FUNCTION handa_live.reject_effect_ledger_history_mutation();

CREATE TRIGGER lifecycle_event_immutable
BEFORE UPDATE OR DELETE ON handa_live.lifecycle_event
FOR EACH ROW EXECUTE FUNCTION handa_live.reject_effect_ledger_history_mutation();

CREATE TRIGGER recovery_event_immutable
BEFORE UPDATE OR DELETE ON handa_live.recovery_event
FOR EACH ROW EXECUTE FUNCTION handa_live.reject_effect_ledger_history_mutation();

CREATE TRIGGER recovery_capability_consumption_immutable
BEFORE UPDATE OR DELETE ON handa_live.recovery_capability_consumption
FOR EACH ROW EXECUTE FUNCTION handa_live.reject_effect_ledger_history_mutation();

CREATE TRIGGER application_attempt_identity_immutable
BEFORE UPDATE OF application_attempt_id, effect_request_id, claimant_id, claimed_at
ON handa_live.application_attempt
FOR EACH ROW EXECUTE FUNCTION handa_live.reject_effect_ledger_history_mutation();

ALTER TABLE handa_live.lifecycle_event
    ADD CONSTRAINT lifecycle_event_attempt_request_fk
    FOREIGN KEY (application_attempt_id, effect_request_id)
    REFERENCES handa_live.application_attempt(application_attempt_id, effect_request_id);

ALTER TABLE handa_live.recovery_event
    ADD CONSTRAINT recovery_event_attempt_request_fk
    FOREIGN KEY (application_attempt_id, effect_request_id)
    REFERENCES handa_live.application_attempt(application_attempt_id, effect_request_id);

CREATE OR REPLACE FUNCTION handa_live.validate_application_attempt_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.attempt_state IS DISTINCT FROM OLD.attempt_state THEN
        IF NOT (
            (OLD.attempt_state = 'APPLYING' AND NEW.attempt_state IN ('APPLIED', 'FAILED_WITHOUT_EFFECT', 'OUTCOME_UNKNOWN'))
            OR (OLD.attempt_state = 'OUTCOME_UNKNOWN' AND NEW.attempt_state IN ('APPLIED', 'FAILED_WITHOUT_EFFECT', 'OUTCOME_UNKNOWN'))
        ) THEN
            RAISE EXCEPTION 'invalid application attempt transition';
        END IF;
        IF NEW.attempt_state = 'APPLIED' AND NOT EXISTS (
            SELECT 1 FROM handa_live.applied_effect
            WHERE application_attempt_id = NEW.application_attempt_id
              AND effect_request_id = NEW.effect_request_id
        ) THEN
            RAISE EXCEPTION 'APPLIED attempt requires applied effect';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER application_attempt_transition_defense
BEFORE UPDATE OF attempt_state ON handa_live.application_attempt
FOR EACH ROW EXECUTE FUNCTION handa_live.validate_application_attempt_transition();

CREATE OR REPLACE FUNCTION handa_live.validate_effect_request_projection()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    attempt_request_id TEXT;
    applied_exists BOOLEAN;
BEGIN
    IF NEW.current_attempt_id IS NOT NULL THEN
        SELECT effect_request_id INTO attempt_request_id
        FROM handa_live.application_attempt
        WHERE application_attempt_id = NEW.current_attempt_id;
        IF attempt_request_id IS DISTINCT FROM NEW.effect_request_id THEN
            RAISE EXCEPTION 'current application attempt ownership mismatch';
        END IF;
    END IF;

    IF NEW.current_state = 'AUTHORIZED' AND NEW.current_attempt_id IS NOT NULL THEN
        RAISE EXCEPTION 'AUTHORIZED request cannot have current application attempt';
    END IF;

    IF OLD.current_state IS DISTINCT FROM NEW.current_state THEN
        IF NOT (
            (OLD.current_state = 'AUTHORIZED' AND NEW.current_state = 'APPLYING')
            OR (OLD.current_state = 'APPLYING' AND NEW.current_state IN ('APPLIED', 'FAILED_WITHOUT_EFFECT', 'OUTCOME_UNKNOWN'))
            OR (OLD.current_state = 'OUTCOME_UNKNOWN' AND NEW.current_state IN ('APPLIED', 'FAILED_WITHOUT_EFFECT', 'OUTCOME_UNKNOWN'))
        ) THEN
            RAISE EXCEPTION 'invalid effect request projection transition';
        END IF;
    END IF;

    IF NEW.current_state = 'APPLIED' THEN
        SELECT EXISTS (
            SELECT 1 FROM handa_live.applied_effect
            WHERE effect_request_id = NEW.effect_request_id
        ) INTO applied_exists;
        IF NOT applied_exists THEN
            RAISE EXCEPTION 'APPLIED projection requires applied effect';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER effect_request_projection_defense
BEFORE UPDATE OF current_state, current_attempt_id ON handa_live.effect_request
FOR EACH ROW EXECUTE FUNCTION handa_live.validate_effect_request_projection();

CREATE OR REPLACE FUNCTION handa_live.validate_lifecycle_chain_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    projected_state TEXT;
    expected_sequence BIGINT;
BEGIN
    SELECT current_state INTO projected_state
    FROM handa_live.effect_request
    WHERE effect_request_id = NEW.effect_request_id
    FOR UPDATE;
    IF projected_state IS NULL THEN
        RAISE EXCEPTION 'lifecycle event request does not exist';
    END IF;

    SELECT COALESCE(MAX(event_sequence), 0) + 1 INTO expected_sequence
    FROM handa_live.lifecycle_event
    WHERE effect_request_id = NEW.effect_request_id;
    IF NEW.event_sequence <> expected_sequence THEN
        RAISE EXCEPTION 'lifecycle event sequence progression violation';
    END IF;

    IF expected_sequence = 1 THEN
        IF NEW.previous_state IS NOT NULL OR NEW.next_state <> 'AUTHORIZED' THEN
            RAISE EXCEPTION 'invalid initial lifecycle transition';
        END IF;
    ELSE
        IF NEW.previous_state IS DISTINCT FROM projected_state THEN
            RAISE EXCEPTION 'lifecycle previous state does not match projection';
        END IF;
        IF NOT (
            (projected_state = 'AUTHORIZED' AND NEW.next_state = 'APPLYING')
            OR (projected_state = 'APPLYING' AND NEW.next_state IN ('APPLIED', 'FAILED_WITHOUT_EFFECT', 'OUTCOME_UNKNOWN'))
            OR (projected_state = 'OUTCOME_UNKNOWN' AND NEW.next_state IN ('APPLIED', 'FAILED_WITHOUT_EFFECT', 'OUTCOME_UNKNOWN'))
        ) THEN
            RAISE EXCEPTION 'invalid lifecycle transition';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER lifecycle_chain_defense
BEFORE INSERT ON handa_live.lifecycle_event
FOR EACH ROW EXECUTE FUNCTION handa_live.validate_lifecycle_chain_insert();
