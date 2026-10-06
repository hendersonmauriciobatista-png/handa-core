-- Durable one-time submission authorization boundary.
-- This relation stores authority issued by an external/governed fixture or
-- future issuer; this migration does not create an issuer API.

CREATE TABLE handa_live.submission_authorization (
    submission_authorization_id TEXT PRIMARY KEY,
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
    authority_reference_id TEXT NOT NULL,
    issuer_id TEXT NOT NULL,
    authority_contract_version TEXT NOT NULL,
    authorization_sequence BIGINT NOT NULL CHECK (authorization_sequence > 0),
    submission_fingerprint TEXT NOT NULL,
    authorization_state TEXT NOT NULL
        CHECK (authorization_state IN ('AUTHORIZED', 'CLAIMED')),
    current_version BIGINT NOT NULL DEFAULT 0 CHECK (current_version >= 0),
    claimed_by TEXT,
    claimed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT submission_authorization_attempt_uq
        UNIQUE (submission_attempt_id),
    CONSTRAINT submission_authorization_lineage_fk
        FOREIGN KEY (submission_attempt_id, intent_id)
        REFERENCES handa_live.submission_attempt(attempt_id, intent_id),
    CONSTRAINT submission_authorization_client_namespace_fk
        FOREIGN KEY (venue, account_scope, client_order_id)
        REFERENCES handa_live.order_intent(venue, account_scope, client_order_id),
    CONSTRAINT submission_authorization_sizing_ck CHECK (
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
    CONSTRAINT submission_authorization_state_fields_ck CHECK (
        (authorization_state = 'AUTHORIZED'
            AND current_version = 0
            AND claimed_by IS NULL
            AND claimed_at IS NULL)
        OR
        (authorization_state = 'CLAIMED'
            AND current_version = 1
            AND claimed_by IS NOT NULL
            AND claimed_at IS NOT NULL)
    )
);

CREATE INDEX submission_authorization_intent_idx
    ON handa_live.submission_authorization (intent_id, authorization_sequence);

CREATE OR REPLACE FUNCTION handa_live.guard_submission_authorization_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'submission authorization history is immutable';
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.authorization_state <> 'AUTHORIZED' THEN
            RAISE EXCEPTION 'submission authorization must be inserted AUTHORIZED';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.authorization_state <> 'AUTHORIZED'
       OR NEW.authorization_state <> 'CLAIMED' THEN
        RAISE EXCEPTION 'only AUTHORIZED to CLAIMED is permitted';
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
       OR NEW.authority_reference_id IS DISTINCT FROM OLD.authority_reference_id
       OR NEW.issuer_id IS DISTINCT FROM OLD.issuer_id
       OR NEW.authority_contract_version IS DISTINCT FROM OLD.authority_contract_version
       OR NEW.authorization_sequence IS DISTINCT FROM OLD.authorization_sequence
       OR NEW.submission_fingerprint IS DISTINCT FROM OLD.submission_fingerprint
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'submission authorization binding is immutable';
    END IF;

    IF NEW.current_version <> OLD.current_version + 1
       OR NEW.claimed_by IS NULL THEN
        RAISE EXCEPTION 'invalid submission authorization claim version';
    END IF;

    -- The database, rather than a caller, owns the claim timestamp.
    NEW.claimed_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER submission_authorization_mutation_guard
BEFORE INSERT OR UPDATE OR DELETE
ON handa_live.submission_authorization
FOR EACH ROW
EXECUTE FUNCTION handa_live.guard_submission_authorization_mutation();
