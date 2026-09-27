-- H&A LIVE reconciliation evidence lineage, schema version 003.
-- This migration adds only durable evidence association structure.

ALTER TABLE handa_live.reconciliation
    ADD CONSTRAINT reconciliation_id_intent_uq
    UNIQUE (reconciliation_id, intent_id);

ALTER TABLE handa_live.normalized_evidence
    ADD CONSTRAINT normalized_revision_id_intent_uq
    UNIQUE (normalized_revision_id, intent_id);

CREATE TABLE handa_live.reconciliation_evidence (
    reconciliation_id TEXT NOT NULL,
    intent_id TEXT NOT NULL,
    normalized_revision_id TEXT NOT NULL,
    PRIMARY KEY (reconciliation_id, intent_id, normalized_revision_id),
    FOREIGN KEY (reconciliation_id, intent_id)
        REFERENCES handa_live.reconciliation(reconciliation_id, intent_id),
    FOREIGN KEY (normalized_revision_id, intent_id)
        REFERENCES handa_live.normalized_evidence(
            normalized_revision_id, intent_id
        )
);
