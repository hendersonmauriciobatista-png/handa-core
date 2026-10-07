-- Durable post-claim MOCK transport projection and immutable history.

CREATE TABLE handa_live.transport_submission (
    submission_authorization_id TEXT PRIMARY KEY
        REFERENCES handa_live.submission_authorization(submission_authorization_id),
    intent_id TEXT NOT NULL
        REFERENCES handa_live.order_intent(intent_id),
    submission_attempt_id TEXT NOT NULL,
    client_order_id TEXT NOT NULL,
    venue TEXT NOT NULL,
    account_scope TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    requested_quote_amount NUMERIC,
    requested_base_qty NUMERIC,
    submission_fingerprint TEXT NOT NULL,
    transport_state TEXT NOT NULL CHECK (
        transport_state IN (
            'HANDOFF_COMMITTED', 'OUTCOME_UNKNOWN',
            'OBSERVED_ACCEPTED', 'OBSERVED_REJECTED',
            'NO_EFFECT_CONFIRMED'
        )
    ),
    current_version BIGINT NOT NULL DEFAULT 0 CHECK (current_version >= 0),
    handoff_committed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_event_sequence BIGINT NOT NULL CHECK (last_event_sequence > 0),
    external_order_id TEXT,
    last_error JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT transport_submission_attempt_uq UNIQUE (submission_attempt_id),
    CONSTRAINT transport_submission_lineage_fk
        FOREIGN KEY (submission_attempt_id, intent_id)
        REFERENCES handa_live.submission_attempt(attempt_id, intent_id),
    CONSTRAINT transport_submission_client_namespace_fk
        FOREIGN KEY (venue, account_scope, client_order_id)
        REFERENCES handa_live.order_intent(venue, account_scope, client_order_id),
    CONSTRAINT transport_submission_sizing_ck CHECK (
        (side = 'BUY'
            AND requested_quote_amount IS NOT NULL
            AND requested_quote_amount > 0
            AND requested_base_qty IS NULL)
        OR
        (side = 'SELL'
            AND requested_base_qty IS NOT NULL
            AND requested_base_qty > 0
            AND requested_quote_amount IS NULL)
    ),
    CONSTRAINT transport_submission_sequence_ck CHECK (
        current_version >= 0 AND last_event_sequence > 0
    )
);

CREATE INDEX transport_submission_attempt_idx
    ON handa_live.transport_submission (submission_attempt_id);

CREATE OR REPLACE FUNCTION handa_live.touch_transport_submission_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION handa_live.guard_transport_submission_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'transport submission history is immutable';
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.current_version <> 0
           OR NEW.last_event_sequence <> 1
           OR NEW.external_order_id IS NOT NULL
           OR NEW.transport_state <> 'HANDOFF_COMMITTED' THEN
            RAISE EXCEPTION 'transport submission must begin at committed handoff';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.submission_authorization_id IS DISTINCT FROM OLD.submission_authorization_id
       OR NEW.intent_id IS DISTINCT FROM OLD.intent_id
       OR NEW.submission_attempt_id IS DISTINCT FROM OLD.submission_attempt_id
       OR NEW.client_order_id IS DISTINCT FROM OLD.client_order_id
       OR NEW.venue IS DISTINCT FROM OLD.venue
       OR NEW.account_scope IS DISTINCT FROM OLD.account_scope
       OR NEW.symbol IS DISTINCT FROM OLD.symbol
       OR NEW.side IS DISTINCT FROM OLD.side
       OR NEW.requested_quote_amount IS DISTINCT FROM OLD.requested_quote_amount
       OR NEW.requested_base_qty IS DISTINCT FROM OLD.requested_base_qty
       OR NEW.submission_fingerprint IS DISTINCT FROM OLD.submission_fingerprint
       OR NEW.handoff_committed_at IS DISTINCT FROM OLD.handoff_committed_at THEN
        RAISE EXCEPTION 'transport submission binding is immutable';
    END IF;

    IF NEW.current_version <> OLD.current_version + 1
       OR NEW.last_event_sequence <> OLD.last_event_sequence + 1 THEN
        RAISE EXCEPTION 'transport submission version sequence is invalid';
    END IF;

    IF OLD.transport_state IN ('OBSERVED_ACCEPTED', 'OBSERVED_REJECTED', 'NO_EFFECT_CONFIRMED') THEN
        RAISE EXCEPTION 'terminal transport submission cannot transition';
    END IF;

    IF NOT (
        (OLD.transport_state = 'HANDOFF_COMMITTED' AND NEW.transport_state IN (
            'OUTCOME_UNKNOWN', 'OBSERVED_ACCEPTED', 'OBSERVED_REJECTED', 'NO_EFFECT_CONFIRMED'
        ))
        OR
        (OLD.transport_state = 'OUTCOME_UNKNOWN' AND NEW.transport_state IN (
            'OUTCOME_UNKNOWN', 'OBSERVED_ACCEPTED', 'OBSERVED_REJECTED', 'NO_EFFECT_CONFIRMED'
        ))
    ) THEN
        RAISE EXCEPTION 'invalid transport submission state transition';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER transport_submission_mutation_guard
BEFORE INSERT OR UPDATE OR DELETE
ON handa_live.transport_submission
FOR EACH ROW
EXECUTE FUNCTION handa_live.guard_transport_submission_mutation();

CREATE TRIGGER transport_submission_updated_at
BEFORE UPDATE
ON handa_live.transport_submission
FOR EACH ROW
EXECUTE FUNCTION handa_live.touch_transport_submission_updated_at();

CREATE TABLE handa_live.transport_event (
    event_id TEXT PRIMARY KEY,
    submission_authorization_id TEXT NOT NULL
        REFERENCES handa_live.transport_submission(submission_authorization_id),
    event_sequence BIGINT NOT NULL CHECK (event_sequence > 0),
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'HANDOFF_COMMITTED',
            'SUBMISSION_ACCEPTED', 'SUBMISSION_REJECTED',
            'SUBMISSION_OUTCOME_UNKNOWN',
            'RECOVERY_ACCEPTED', 'RECOVERY_REJECTED',
            'RECOVERY_NO_EFFECT_CONFIRMED', 'RECOVERY_INCONCLUSIVE'
        )
    ),
    transport_state_after TEXT NOT NULL CHECK (
        transport_state_after IN (
            'HANDOFF_COMMITTED', 'OUTCOME_UNKNOWN',
            'OBSERVED_ACCEPTED', 'OBSERVED_REJECTED',
            'NO_EFFECT_CONFIRMED'
        )
    ),
    actor_id TEXT NOT NULL,
    external_order_id TEXT,
    observation_identity TEXT,
    event_detail JSONB NOT NULL DEFAULT '{}'::JSONB,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT transport_event_sequence_uq
        UNIQUE (submission_authorization_id, event_sequence),
    CONSTRAINT transport_event_actor_ck CHECK (btrim(actor_id) <> '')
);

CREATE INDEX transport_event_history_idx
    ON handa_live.transport_event (submission_authorization_id, event_sequence);

CREATE OR REPLACE FUNCTION handa_live.guard_transport_event_semantics()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'transport event history is immutable';
    END IF;

    IF (NEW.event_type = 'HANDOFF_COMMITTED' AND NEW.transport_state_after <> 'HANDOFF_COMMITTED')
       OR (NEW.event_type IN ('SUBMISSION_OUTCOME_UNKNOWN', 'RECOVERY_INCONCLUSIVE')
           AND NEW.transport_state_after <> 'OUTCOME_UNKNOWN')
       OR (NEW.event_type IN ('SUBMISSION_ACCEPTED', 'RECOVERY_ACCEPTED')
           AND NEW.transport_state_after <> 'OBSERVED_ACCEPTED')
       OR (NEW.event_type IN ('SUBMISSION_REJECTED', 'RECOVERY_REJECTED')
           AND NEW.transport_state_after <> 'OBSERVED_REJECTED')
       OR (NEW.event_type = 'RECOVERY_NO_EFFECT_CONFIRMED'
           AND NEW.transport_state_after <> 'NO_EFFECT_CONFIRMED') THEN
        RAISE EXCEPTION 'transport event and state are incompatible';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER transport_event_immutability_guard
BEFORE INSERT OR UPDATE OR DELETE
ON handa_live.transport_event
FOR EACH ROW
EXECUTE FUNCTION handa_live.guard_transport_event_semantics();
