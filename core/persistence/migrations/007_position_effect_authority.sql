CREATE TABLE handa_live.position (
    position_id TEXT PRIMARY KEY,
    intent_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK (lifecycle_state IN ('ACTIVE', 'CLOSED')),
    current_quantity NUMERIC NOT NULL CHECK (current_quantity >= 0),
    open_effect_request_id TEXT NOT NULL
        REFERENCES handa_live.effect_request(effect_request_id),
    position_lifecycle_version BIGINT NOT NULL CHECK (position_lifecycle_version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((lifecycle_state = 'ACTIVE' AND current_quantity > 0)
        OR (lifecycle_state = 'CLOSED' AND current_quantity = 0)),
    UNIQUE (position_id, intent_id),
    FOREIGN KEY (open_effect_request_id, intent_id)
        REFERENCES handa_live.effect_request(effect_request_id, intent_id)
);

CREATE TABLE handa_live.position_receipt (
    receipt_id TEXT PRIMARY KEY,
    external_order_identity TEXT NOT NULL,
    execution_extent_identity TEXT NOT NULL UNIQUE,
    executed_base_quantity NUMERIC NOT NULL CHECK (executed_base_quantity > 0),
    executed_quote_quantity NUMERIC,
    weighted_price NUMERIC,
    external_status TEXT NOT NULL,
    receipt_payload JSONB NOT NULL,
    receipt_digest TEXT NOT NULL UNIQUE,
    normalization_version TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE handa_live.position_effect_event (
    position_effect_event_id BIGSERIAL PRIMARY KEY,
    position_id TEXT NOT NULL REFERENCES handa_live.position(position_id),
    intent_id TEXT NOT NULL,
    effect_type TEXT NOT NULL CHECK (effect_type IN ('OPEN', 'REDUCE', 'CLOSE')),
    effect_request_id TEXT NOT NULL UNIQUE
        REFERENCES handa_live.effect_request(effect_request_id),
    application_attempt_id TEXT NOT NULL,
    external_order_identity TEXT NOT NULL,
    execution_extent_identity TEXT NOT NULL UNIQUE,
    receipt_id TEXT NOT NULL REFERENCES handa_live.position_receipt(receipt_id),
    previous_quantity NUMERIC NOT NULL CHECK (previous_quantity >= 0),
    applied_quantity NUMERIC NOT NULL CHECK (applied_quantity > 0),
    resulting_quantity NUMERIC NOT NULL CHECK (resulting_quantity >= 0),
    event_sequence BIGINT NOT NULL CHECK (event_sequence > 0),
    reconciliation_context_id TEXT NOT NULL,
    semantic_decision_id TEXT NOT NULL,
    decision_sequence BIGINT NOT NULL CHECK (decision_sequence > 0),
    authority_contract_version TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (position_id, event_sequence),
    UNIQUE (position_id, intent_id, position_effect_event_id),
    FOREIGN KEY (position_id, intent_id)
        REFERENCES handa_live.position(position_id, intent_id),
    FOREIGN KEY (effect_request_id, intent_id)
        REFERENCES handa_live.effect_request(effect_request_id, intent_id),
    CHECK ((effect_type = 'OPEN' AND previous_quantity = 0 AND resulting_quantity = applied_quantity)
        OR (effect_type = 'REDUCE' AND applied_quantity < previous_quantity
            AND resulting_quantity = previous_quantity - applied_quantity
            AND resulting_quantity > 0)
        OR (effect_type = 'CLOSE' AND applied_quantity = previous_quantity
            AND resulting_quantity = 0))
);

CREATE OR REPLACE FUNCTION handa_live.reject_position_history_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'position effect history is immutable';
END;
$$;

CREATE TRIGGER position_receipt_immutable
BEFORE UPDATE OR DELETE ON handa_live.position_receipt
FOR EACH ROW EXECUTE FUNCTION handa_live.reject_position_history_mutation();

CREATE TRIGGER position_effect_event_immutable
BEFORE UPDATE OR DELETE ON handa_live.position_effect_event
FOR EACH ROW EXECUTE FUNCTION handa_live.reject_position_history_mutation();

CREATE OR REPLACE FUNCTION handa_live.validate_position_effect_event()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    current_qty NUMERIC;
    current_state TEXT;
    expected_sequence BIGINT;
BEGIN
    SELECT current_quantity, lifecycle_state
      INTO current_qty, current_state
      FROM handa_live.position
     WHERE position_id = NEW.position_id AND intent_id = NEW.intent_id
     FOR UPDATE;
    IF current_qty IS NULL THEN
        RAISE EXCEPTION 'position identity does not exist';
    END IF;
    SELECT COALESCE(MAX(event_sequence), 0) + 1 INTO expected_sequence
      FROM handa_live.position_effect_event
     WHERE position_id = NEW.position_id;
    IF NEW.event_sequence <> expected_sequence THEN
        RAISE EXCEPTION 'position effect event sequence violation';
    END IF;
    IF NEW.effect_type = 'OPEN' AND expected_sequence <> 1 THEN
        RAISE EXCEPTION 'position can have only one OPEN';
    END IF;
    IF NEW.effect_type IN ('REDUCE', 'CLOSE') AND current_state <> 'ACTIVE' THEN
        RAISE EXCEPTION 'closed position cannot receive effect';
    END IF;
    IF NEW.effect_type = 'OPEN' THEN
        IF NEW.previous_quantity <> 0 OR current_qty <> NEW.resulting_quantity THEN
            RAISE EXCEPTION 'position OPEN quantity transition mismatch';
        END IF;
    ELSIF NEW.previous_quantity <> current_qty THEN
        RAISE EXCEPTION 'position quantity transition mismatch';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER position_effect_event_defense
BEFORE INSERT ON handa_live.position_effect_event
FOR EACH ROW EXECUTE FUNCTION handa_live.validate_position_effect_event();
