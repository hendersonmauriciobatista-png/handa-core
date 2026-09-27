-- H&A LIVE order/evidence boundary, schema version 001.
-- This migration contains no operational submission authority.

CREATE SCHEMA IF NOT EXISTS handa_live;

CREATE TABLE handa_live.order_intent (
    intent_id TEXT PRIMARY KEY,
    venue TEXT NOT NULL,
    account_scope TEXT NOT NULL,
    client_order_id TEXT NOT NULL,
    slot_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    requested_quote_amount NUMERIC,
    requested_base_qty NUMERIC,
    policy_context TEXT NOT NULL DEFAULT '',
    submission_lifecycle_state TEXT NOT NULL
        CHECK (submission_lifecycle_state IN (
            'READY_TO_SUBMIT', 'SUBMISSION_ATTEMPTED', 'MAY_HAVE_BEEN_SUBMITTED'
        )),
    execution_certainty TEXT
        CHECK (execution_certainty IS NULL OR execution_certainty IN (
            'UNKNOWN', 'NO_EFFECT_CONFIRMED', 'EXECUTION_CONFIRMED'
        )),
    reconciliation_state TEXT
        CHECK (reconciliation_state IS NULL OR reconciliation_state IN (
            'NOT_REQUIRED', 'PENDING', 'RESOLVED', 'BLOCKED'
        )),
    exchange_order_id TEXT,
    current_version BIGINT NOT NULL DEFAULT 0 CHECK (current_version >= 0),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT order_intent_client_order_namespace_uq
        UNIQUE (venue, account_scope, client_order_id),
    CONSTRAINT order_intent_sizing_by_side_ck CHECK (
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
    CONSTRAINT order_intent_state_boundary_ck CHECK (
        (submission_lifecycle_state = 'READY_TO_SUBMIT'
            AND execution_certainty IS NULL)
        OR submission_lifecycle_state <> 'READY_TO_SUBMIT'
    ),
    CONSTRAINT order_intent_may_have_been_unknown_ck CHECK (
        submission_lifecycle_state <> 'MAY_HAVE_BEEN_SUBMITTED'
        OR (execution_certainty IS NOT NULL AND execution_certainty = 'UNKNOWN')
    ),
    CONSTRAINT order_intent_unknown_reconciliation_ck CHECK (
        execution_certainty IS NULL
        OR execution_certainty <> 'UNKNOWN'
        OR (
            reconciliation_state IS NOT NULL
            AND reconciliation_state IN ('PENDING', 'BLOCKED')
        )
    ),
    CONSTRAINT order_intent_no_effect_resolved_ck CHECK (
        execution_certainty IS NULL
        OR execution_certainty <> 'NO_EFFECT_CONFIRMED'
        OR (
            reconciliation_state IS NOT NULL
            AND reconciliation_state = 'RESOLVED'
        )
    ),
    CONSTRAINT order_intent_non_negative_amounts_ck CHECK (
        (requested_quote_amount IS NULL OR requested_quote_amount > 0)
        AND (requested_base_qty IS NULL OR requested_base_qty > 0)
    )
);

CREATE TABLE handa_live.submission_attempt (
    attempt_id TEXT PRIMARY KEY,
    intent_id TEXT NOT NULL REFERENCES handa_live.order_intent(intent_id),
    attempt_sequence BIGINT NOT NULL CHECK (attempt_sequence > 0),
    venue TEXT NOT NULL,
    account_scope TEXT NOT NULL,
    client_order_id TEXT NOT NULL,
    submission_lifecycle_state TEXT NOT NULL
        CHECK (submission_lifecycle_state IN (
            'SUBMISSION_ATTEMPTED', 'MAY_HAVE_BEEN_SUBMITTED'
        )),
    exchange_order_id TEXT,
    transport_status TEXT,
    transport_error JSONB,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    observed_at TIMESTAMPTZ,
    exchange_event_time TIMESTAMPTZ,
    UNIQUE (intent_id, attempt_sequence),
    FOREIGN KEY (venue, account_scope, client_order_id)
        REFERENCES handa_live.order_intent(venue, account_scope, client_order_id)
);

ALTER TABLE handa_live.submission_attempt
    ADD CONSTRAINT submission_attempt_lineage_uq
    UNIQUE (attempt_id, intent_id);

CREATE TABLE handa_live.exchange_evidence (
    evidence_id TEXT PRIMARY KEY,
    intent_id TEXT NOT NULL REFERENCES handa_live.order_intent(intent_id),
    attempt_id TEXT REFERENCES handa_live.submission_attempt(attempt_id),
    evidence_sequence BIGINT NOT NULL CHECK (evidence_sequence > 0),
    symbol TEXT NOT NULL,
    exchange_order_id TEXT,
    exchange_status TEXT CHECK (exchange_status IS NULL OR exchange_status IN (
        'NEW', 'PARTIALLY_FILLED', 'FILLED', 'CANCELED', 'EXPIRED', 'EXPIRED_IN_MATCH'
    )),
    raw_snapshot JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    observed_at TIMESTAMPTZ NOT NULL,
    exchange_event_time TIMESTAMPTZ,
    UNIQUE (intent_id, evidence_sequence),
    UNIQUE (evidence_id, intent_id),
    UNIQUE (evidence_id, intent_id, symbol, exchange_order_id),
    FOREIGN KEY (attempt_id, intent_id)
        REFERENCES handa_live.submission_attempt(attempt_id, intent_id)
);

CREATE TABLE handa_live.trade_effect (
    symbol TEXT NOT NULL,
    exchange_order_id TEXT NOT NULL,
    exchange_trade_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    intent_id TEXT NOT NULL,
    price NUMERIC NOT NULL CHECK (price > 0),
    gross_base_qty NUMERIC NOT NULL CHECK (gross_base_qty > 0),
    quote_qty NUMERIC NOT NULL CHECK (quote_qty >= 0),
    commission_amount NUMERIC NOT NULL CHECK (commission_amount >= 0),
    commission_asset TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    exchange_event_time TIMESTAMPTZ,
    PRIMARY KEY (symbol, exchange_order_id, exchange_trade_id),
    FOREIGN KEY (evidence_id, intent_id)
        REFERENCES handa_live.exchange_evidence(evidence_id, intent_id),
    FOREIGN KEY (evidence_id, intent_id, symbol, exchange_order_id)
        REFERENCES handa_live.exchange_evidence(
            evidence_id, intent_id, symbol, exchange_order_id
        )
);

CREATE TABLE handa_live.normalized_evidence (
    normalized_revision_id TEXT PRIMARY KEY,
    evidence_id TEXT NOT NULL,
    intent_id TEXT NOT NULL,
    revision_sequence BIGINT NOT NULL CHECK (revision_sequence > 0),
    exchange_status TEXT CHECK (exchange_status IS NULL OR exchange_status IN (
        'NEW', 'PARTIALLY_FILLED', 'FILLED', 'CANCELED', 'EXPIRED', 'EXPIRED_IN_MATCH'
    )),
    normalized_status TEXT NOT NULL CHECK (normalized_status IN (
        'SUBMISSION_REJECTED', 'UNKNOWN', 'NO_EFFECT_CONFIRMED',
        'PARTIALLY_FILLED', 'FILLED', 'CANCELED'
    )),
    provenance JSONB NOT NULL,
    normalized_payload JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (evidence_id, revision_sequence),
    FOREIGN KEY (evidence_id, intent_id)
        REFERENCES handa_live.exchange_evidence(evidence_id, intent_id)
);

CREATE TABLE handa_live.reconciliation (
    reconciliation_id TEXT PRIMARY KEY,
    intent_id TEXT NOT NULL REFERENCES handa_live.order_intent(intent_id),
    decision_sequence BIGINT NOT NULL CHECK (decision_sequence > 0),
    reconciliation_state TEXT NOT NULL
        CHECK (reconciliation_state IN (
            'NOT_REQUIRED', 'PENDING', 'RESOLVED', 'BLOCKED'
        )),
    execution_certainty TEXT NOT NULL
        CHECK (execution_certainty IN (
            'UNKNOWN', 'NO_EFFECT_CONFIRMED', 'EXECUTION_CONFIRMED'
        )),
    decision_reason TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ,
    UNIQUE (intent_id, decision_sequence),
    CONSTRAINT reconciliation_unknown_state_ck CHECK (
        execution_certainty <> 'UNKNOWN'
        OR reconciliation_state IN ('PENDING', 'BLOCKED')
    ),
    CONSTRAINT reconciliation_no_effect_resolved_ck CHECK (
        execution_certainty <> 'NO_EFFECT_CONFIRMED'
        OR reconciliation_state = 'RESOLVED'
    )
);

CREATE INDEX order_intent_unresolved_symbol_idx
    ON handa_live.order_intent (symbol, intent_id)
    WHERE execution_certainty = 'UNKNOWN'
       OR submission_lifecycle_state = 'MAY_HAVE_BEEN_SUBMITTED';

CREATE INDEX order_intent_client_namespace_idx
    ON handa_live.order_intent (venue, account_scope, client_order_id);

CREATE INDEX exchange_evidence_lineage_idx
    ON handa_live.exchange_evidence (intent_id, evidence_sequence);

CREATE INDEX reconciliation_pending_idx
    ON handa_live.reconciliation (intent_id, decision_sequence)
    WHERE reconciliation_state IN ('PENDING', 'BLOCKED');
