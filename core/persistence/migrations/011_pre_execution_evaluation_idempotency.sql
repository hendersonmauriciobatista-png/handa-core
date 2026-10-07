-- Fail-closed replay identity for immutable pre-execution decisions.
-- Historical decisions have no legitimate request identity and must not be
-- backfilled or reinterpreted.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM handa_live.pre_execution_decision
    ) THEN
        RAISE EXCEPTION
            'migration 011 requires an empty pre_execution_decision table';
    END IF;
END
$$;

ALTER TABLE handa_live.pre_execution_decision
    ADD COLUMN evaluation_request_id TEXT NOT NULL,
    ADD COLUMN evaluation_request_digest TEXT NOT NULL;

ALTER TABLE handa_live.pre_execution_decision
    DROP CONSTRAINT pre_execution_decision_validity_ck,
    ADD CONSTRAINT pre_execution_decision_request_identity_ck
        CHECK (
            btrim(evaluation_request_id) <> ''
            AND btrim(evaluation_request_digest) <> ''
        ),
    ADD CONSTRAINT pre_execution_decision_validity_ck
        CHECK (
            (
                decision_outcome = 'ALLOW'
                AND valid_until > evaluated_at
            )
            OR
            (
                decision_outcome = 'BLOCK'
                AND valid_until = evaluated_at
            )
        ),
    ADD CONSTRAINT pre_execution_decision_request_id_uq
        UNIQUE (evaluation_request_id);
