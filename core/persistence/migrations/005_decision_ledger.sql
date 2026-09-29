-- Additive semantic decision ledger.
-- Existing reconciliation and reconciliation_evidence remain compatibility history.

ALTER TABLE handa_live.submission_attempt
    ADD COLUMN context_id TEXT;

ALTER TABLE handa_live.exchange_evidence
    ADD CONSTRAINT exchange_evidence_id_intent_key
    UNIQUE (evidence_id, intent_id);

ALTER TABLE handa_live.normalized_evidence
    ADD CONSTRAINT normalized_evidence_id_intent_key
    UNIQUE (normalized_revision_id, intent_id);

ALTER TABLE handa_live.trade_effect
    ADD CONSTRAINT trade_effect_identity_intent_key
    UNIQUE (symbol, exchange_order_id, exchange_trade_id, intent_id);

CREATE TABLE handa_live.reconciliation_context (
    context_id TEXT PRIMARY KEY,
    intent_id TEXT NOT NULL REFERENCES handa_live.order_intent(intent_id),
    context_sequence BIGINT NOT NULL CHECK (context_sequence > 0),
    context_state TEXT NOT NULL CHECK (context_state IN ('ACTIVE', 'CLOSED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMPTZ,
    closure_reason TEXT,
    predecessor_context_id TEXT REFERENCES handa_live.reconciliation_context(context_id),
    predecessor_intent_id TEXT,
    UNIQUE (context_id, intent_id),
    UNIQUE (intent_id, context_sequence),
    FOREIGN KEY (predecessor_context_id, predecessor_intent_id)
        REFERENCES handa_live.reconciliation_context(context_id, intent_id),
    CHECK (
        (context_state = 'ACTIVE' AND closed_at IS NULL)
        OR (context_state = 'CLOSED' AND closed_at IS NOT NULL)
    ),
    CHECK (
        (predecessor_context_id IS NULL AND predecessor_intent_id IS NULL)
        OR (predecessor_context_id IS NOT NULL AND predecessor_intent_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX reconciliation_context_one_active_per_intent
    ON handa_live.reconciliation_context (intent_id)
    WHERE context_state = 'ACTIVE';

ALTER TABLE handa_live.submission_attempt
    ADD CONSTRAINT submission_attempt_context_fk
    FOREIGN KEY (context_id, intent_id)
    REFERENCES handa_live.reconciliation_context(context_id, intent_id);

ALTER TABLE handa_live.order_intent
    ADD COLUMN current_context_id TEXT,
    ADD COLUMN current_decision_id TEXT;

CREATE TABLE handa_live.semantic_decision (
    decision_id TEXT PRIMARY KEY,
    context_id TEXT NOT NULL,
    intent_id TEXT NOT NULL,
    reconciliation_id TEXT REFERENCES handa_live.reconciliation(reconciliation_id),
    decision_sequence BIGINT NOT NULL CHECK (decision_sequence > 0),
    evaluation_time TIMESTAMPTZ NOT NULL,
    decision_scope TEXT NOT NULL CHECK (decision_scope IN ('ORDER_OUTCOME', 'QUANTITY_DEPENDENT')),
    authority_state TEXT NOT NULL CHECK (authority_state IN ('RESOLVED', 'PENDING', 'BLOCKED')),
    execution_occurred JSONB NOT NULL,
    order_outcome_terminal JSONB NOT NULL,
    execution_extent JSONB NOT NULL,
    final_partial_outcome JSONB NOT NULL,
    unknown_reason JSONB,
    contradiction_result JSONB,
    decision_reason TEXT,
    evaluated_input_snapshot JSONB NOT NULL,
    authority_contract_version TEXT NOT NULL,
    decision_schema_version TEXT NOT NULL,
    evidence_normalization_version TEXT NOT NULL,
    lineage_completeness_status TEXT NOT NULL CHECK (
        lineage_completeness_status IN ('LINEAGE_COMPLETE', 'LINEAGE_INCOMPLETE')
    ),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (decision_id, intent_id),
    UNIQUE (context_id, decision_sequence),
    FOREIGN KEY (context_id, intent_id)
        REFERENCES handa_live.reconciliation_context(context_id, intent_id)
);

ALTER TABLE handa_live.order_intent
    ADD CONSTRAINT order_intent_current_context_fk
    FOREIGN KEY (current_context_id, intent_id)
    REFERENCES handa_live.reconciliation_context(context_id, intent_id),
    ADD CONSTRAINT order_intent_current_decision_fk
    FOREIGN KEY (current_decision_id, intent_id)
    REFERENCES handa_live.semantic_decision(decision_id, intent_id);

CREATE TABLE handa_live.decision_evidence_reference (
    reference_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL REFERENCES handa_live.semantic_decision(decision_id),
    intent_id TEXT NOT NULL,
    evidence_kind TEXT NOT NULL CHECK (
        evidence_kind IN (
            'EXCHANGE_OBSERVATION',
            'NORMALIZED_REVISION',
            'TRADE_FILL',
            'CONTRADICTION_BASIS'
        )
    ),
    semantic_role TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (reference_id, decision_id, intent_id),
    UNIQUE (reference_id, intent_id),
    FOREIGN KEY (decision_id, intent_id)
        REFERENCES handa_live.semantic_decision(decision_id, intent_id)
);

CREATE TABLE handa_live.decision_exchange_observation_ref (
    reference_id TEXT PRIMARY KEY REFERENCES handa_live.decision_evidence_reference(reference_id),
    evidence_id TEXT NOT NULL REFERENCES handa_live.exchange_evidence(evidence_id),
    intent_id TEXT NOT NULL,
    UNIQUE (reference_id, evidence_id, intent_id),
    FOREIGN KEY (reference_id) REFERENCES handa_live.decision_evidence_reference(reference_id),
    FOREIGN KEY (reference_id, intent_id)
        REFERENCES handa_live.decision_evidence_reference(reference_id, intent_id),
    FOREIGN KEY (evidence_id, intent_id)
        REFERENCES handa_live.exchange_evidence(evidence_id, intent_id)
);

CREATE TABLE handa_live.decision_normalized_revision_ref (
    reference_id TEXT PRIMARY KEY REFERENCES handa_live.decision_evidence_reference(reference_id),
    normalized_revision_id TEXT NOT NULL REFERENCES handa_live.normalized_evidence(normalized_revision_id),
    intent_id TEXT NOT NULL,
    UNIQUE (reference_id, normalized_revision_id, intent_id),
    FOREIGN KEY (reference_id) REFERENCES handa_live.decision_evidence_reference(reference_id),
    FOREIGN KEY (reference_id, intent_id)
        REFERENCES handa_live.decision_evidence_reference(reference_id, intent_id),
    FOREIGN KEY (normalized_revision_id, intent_id)
        REFERENCES handa_live.normalized_evidence(normalized_revision_id, intent_id)
);

CREATE TABLE handa_live.decision_trade_fill_ref (
    reference_id TEXT PRIMARY KEY REFERENCES handa_live.decision_evidence_reference(reference_id),
    symbol TEXT NOT NULL,
    exchange_order_id TEXT NOT NULL,
    exchange_trade_id TEXT NOT NULL,
    intent_id TEXT NOT NULL,
    UNIQUE (reference_id, symbol, exchange_order_id, exchange_trade_id, intent_id),
    FOREIGN KEY (symbol, exchange_order_id, exchange_trade_id, intent_id)
        REFERENCES handa_live.trade_effect(symbol, exchange_order_id, exchange_trade_id, intent_id),
    FOREIGN KEY (reference_id) REFERENCES handa_live.decision_evidence_reference(reference_id),
    FOREIGN KEY (reference_id, intent_id)
        REFERENCES handa_live.decision_evidence_reference(reference_id, intent_id)
);

CREATE TABLE handa_live.decision_contradiction_basis_ref (
    reference_id TEXT PRIMARY KEY REFERENCES handa_live.decision_evidence_reference(reference_id),
    basis_reference_id TEXT NOT NULL REFERENCES handa_live.decision_evidence_reference(reference_id),
    intent_id TEXT NOT NULL,
    UNIQUE (reference_id, basis_reference_id, intent_id),
    CHECK (reference_id <> basis_reference_id),
    FOREIGN KEY (reference_id) REFERENCES handa_live.decision_evidence_reference(reference_id),
    FOREIGN KEY (reference_id, intent_id)
        REFERENCES handa_live.decision_evidence_reference(reference_id, intent_id),
    FOREIGN KEY (basis_reference_id, intent_id)
        REFERENCES handa_live.decision_evidence_reference(reference_id, intent_id)
);

CREATE OR REPLACE FUNCTION handa_live.reject_semantic_decision_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'semantic decision ledger rows are immutable';
END;
$$;

CREATE TRIGGER semantic_decision_immutable
BEFORE UPDATE OR DELETE ON handa_live.semantic_decision
FOR EACH ROW EXECUTE FUNCTION handa_live.reject_semantic_decision_mutation();

CREATE TRIGGER decision_evidence_reference_immutable
BEFORE UPDATE OR DELETE ON handa_live.decision_evidence_reference
FOR EACH ROW EXECUTE FUNCTION handa_live.reject_semantic_decision_mutation();

CREATE TRIGGER decision_exchange_observation_ref_immutable
BEFORE UPDATE OR DELETE ON handa_live.decision_exchange_observation_ref
FOR EACH ROW EXECUTE FUNCTION handa_live.reject_semantic_decision_mutation();

CREATE TRIGGER decision_normalized_revision_ref_immutable
BEFORE UPDATE OR DELETE ON handa_live.decision_normalized_revision_ref
FOR EACH ROW EXECUTE FUNCTION handa_live.reject_semantic_decision_mutation();

CREATE TRIGGER decision_trade_fill_ref_immutable
BEFORE UPDATE OR DELETE ON handa_live.decision_trade_fill_ref
FOR EACH ROW EXECUTE FUNCTION handa_live.reject_semantic_decision_mutation();

CREATE TRIGGER decision_contradiction_basis_ref_immutable
BEFORE UPDATE OR DELETE ON handa_live.decision_contradiction_basis_ref
FOR EACH ROW EXECUTE FUNCTION handa_live.reject_semantic_decision_mutation();

CREATE OR REPLACE FUNCTION handa_live.reject_contributing_attempt_context_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.context_id IS DISTINCT FROM NEW.context_id
       AND EXISTS (
           SELECT 1
           FROM handa_live.semantic_decision
           WHERE context_id = OLD.context_id
              OR context_id = NEW.context_id
       ) THEN
        RAISE EXCEPTION 'attempt context association is immutable after contribution';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER submission_attempt_context_immutable_after_decision
BEFORE UPDATE OF context_id ON handa_live.submission_attempt
FOR EACH ROW EXECUTE FUNCTION handa_live.reject_contributing_attempt_context_mutation();
