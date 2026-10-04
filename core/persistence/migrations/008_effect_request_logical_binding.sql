ALTER TABLE handa_live.effect_request
    ADD COLUMN logical_effect_id TEXT;

CREATE UNIQUE INDEX effect_request_logical_identity_uq
    ON handa_live.effect_request (intent_id, logical_effect_id)
    WHERE logical_effect_id IS NOT NULL;
