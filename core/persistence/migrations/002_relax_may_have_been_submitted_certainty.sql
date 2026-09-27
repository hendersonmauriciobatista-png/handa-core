-- H&A LIVE order/evidence boundary, schema version 002.
-- Preserve the handoff fact while allowing terminal reconciliation projections.

ALTER TABLE handa_live.order_intent
    DROP CONSTRAINT IF EXISTS order_intent_may_have_been_unknown_ck;

ALTER TABLE handa_live.order_intent
    ADD CONSTRAINT order_intent_may_have_been_certainty_ck CHECK (
        submission_lifecycle_state <> 'MAY_HAVE_BEEN_SUBMITTED'
        OR execution_certainty IS NOT NULL
    );

ALTER TABLE handa_live.order_intent
    ADD CONSTRAINT order_intent_terminal_reconciliation_ck CHECK (
        execution_certainty IS NULL
        OR execution_certainty NOT IN (
            'NO_EFFECT_CONFIRMED', 'EXECUTION_CONFIRMED'
        )
        OR (
            reconciliation_state IS NOT NULL
            AND reconciliation_state = 'RESOLVED'
        )
    );
