-- H&A LIVE external order-observation contract, schema version 004.
-- This migration adds structured observation facts without deriving decisions.

ALTER TABLE handa_live.exchange_evidence
    ADD COLUMN client_order_id_observed TEXT,
    ADD COLUMN order_type TEXT,
    ADD COLUMN time_in_force TEXT,
    ADD COLUMN orig_qty NUMERIC,
    ADD COLUMN orig_quote_order_qty NUMERIC,
    ADD COLUMN executed_qty NUMERIC,
    ADD COLUMN cumulative_quote_qty NUMERIC,
    ADD COLUMN observation_class TEXT,
    ADD COLUMN observation_source TEXT;

ALTER TABLE handa_live.exchange_evidence
    ADD CONSTRAINT exchange_evidence_orig_qty_non_negative_ck
        CHECK (orig_qty IS NULL OR orig_qty >= 0),
    ADD CONSTRAINT exchange_evidence_orig_quote_qty_non_negative_ck
        CHECK (orig_quote_order_qty IS NULL OR orig_quote_order_qty >= 0),
    ADD CONSTRAINT exchange_evidence_executed_qty_non_negative_ck
        CHECK (executed_qty IS NULL OR executed_qty >= 0),
    ADD CONSTRAINT exchange_evidence_observation_class_ck
        CHECK (
            observation_class IS NULL
            OR observation_class IN (
                'ORDER_STATE', 'EXECUTION_EVENT', 'TRADE_RECORD'
            )
        ),
    ADD CONSTRAINT exchange_evidence_observation_source_ck
        CHECK (
            observation_source IS NULL
            OR observation_source IN (
                'BINANCE_SPOT_ORDER_RESPONSE',
                'BINANCE_SPOT_ORDER_QUERY',
                'BINANCE_SPOT_EXECUTION_REPORT',
                'BINANCE_SPOT_TRADE_QUERY'
            )
        );
