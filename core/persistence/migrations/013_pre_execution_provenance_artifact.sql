-- Durable static-manifest and candidate-provenance records for H&A 2B8B.
-- Runtime access is read-only for manifests and cannot activate authority.

CREATE TABLE handa_live.governance_artifact_manifest (
    artifact_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    CONSTRAINT governance_artifact_manifest_pkey PRIMARY KEY (artifact_id),
    CONSTRAINT governance_artifact_manifest_artifact_type_ck CHECK (
        artifact_type IN ('STRATEGY', 'POLICY', 'RISK', 'CONFIGURATION', 'FRESHNESS')
    ),
    artifact_version TEXT NOT NULL,
    canonical_payload JSONB NOT NULL,
    canonical_payload_digest TEXT NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ NOT NULL,
    producer_component TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    created_by TEXT NOT NULL,
    approved_at TIMESTAMPTZ NOT NULL,
    approved_by TEXT NOT NULL,
    approval_reason TEXT NOT NULL,
    CONSTRAINT governance_artifact_manifest_digest_uq
        UNIQUE (canonical_payload_digest),
    CONSTRAINT governance_artifact_manifest_validity_ck
        CHECK (valid_from < valid_until),
    CONSTRAINT governance_artifact_manifest_text_ck
        CHECK (
            btrim(artifact_id) <> ''
            AND btrim(artifact_version) <> ''
            AND btrim(canonical_payload_digest) <> ''
            AND btrim(producer_component) <> ''
            AND btrim(schema_version) <> ''
            AND btrim(contract_version) <> ''
            AND btrim(created_by) <> ''
            AND btrim(approved_by) <> ''
            AND btrim(approval_reason) <> ''
        )
);

CREATE INDEX governance_artifact_manifest_type_validity_idx
    ON handa_live.governance_artifact_manifest (artifact_type, valid_until);

CREATE OR REPLACE FUNCTION handa_live.guard_governance_artifact_manifest_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'governance artifact manifests are immutable';
END;
$$;

CREATE TRIGGER governance_artifact_manifest_immutability_guard
BEFORE UPDATE OR DELETE
ON handa_live.governance_artifact_manifest
FOR EACH ROW
EXECUTE FUNCTION handa_live.guard_governance_artifact_manifest_immutability();

ALTER TABLE handa_live.authority_envelope
    ADD COLUMN strategy_manifest_id TEXT NULL
        CONSTRAINT authority_envelope_strategy_manifest_id_fkey
        REFERENCES handa_live.governance_artifact_manifest(artifact_id),
    ADD COLUMN policy_manifest_id TEXT NULL
        CONSTRAINT authority_envelope_policy_manifest_id_fkey
        REFERENCES handa_live.governance_artifact_manifest(artifact_id),
    ADD COLUMN risk_manifest_id TEXT NULL
        CONSTRAINT authority_envelope_risk_manifest_id_fkey
        REFERENCES handa_live.governance_artifact_manifest(artifact_id),
    ADD COLUMN configuration_manifest_id TEXT NULL
        CONSTRAINT authority_envelope_configuration_manifest_id_fkey
        REFERENCES handa_live.governance_artifact_manifest(artifact_id),
    ADD COLUMN freshness_manifest_id TEXT NULL
        CONSTRAINT authority_envelope_freshness_manifest_id_fkey
        REFERENCES handa_live.governance_artifact_manifest(artifact_id);

CREATE TABLE handa_live.pre_execution_provenance_artifact (
    provenance_artifact_id TEXT NOT NULL,
    CONSTRAINT pre_execution_provenance_artifact_pkey PRIMARY KEY (provenance_artifact_id),
    candidate_evidence_identity TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    CONSTRAINT pre_execution_provenance_artifact_side_ck CHECK (side = 'BUY'),
    source_group_timestamps JSONB NOT NULL,
    source_group_digests JSONB NOT NULL,
    source_group_intervals JSONB NOT NULL,
    source_group_closure_statuses JSONB NOT NULL,
    source_group_server_times JSONB NOT NULL,
    source_group_constituent_digests JSONB NOT NULL,
    source_group_identities JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_group_constituents JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_group_missing_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_group_trust JSONB NOT NULL DEFAULT '{}'::jsonb,
    ticker_value NUMERIC,
    ticker_application_receipt_at TIMESTAMPTZ,
    decision_produced_at TIMESTAMPTZ,
    requested_quote_amount NUMERIC NOT NULL,
    CONSTRAINT pre_execution_provenance_artifact_requested_quote_amount_ck
        CHECK (requested_quote_amount > 0),
    dynamic_policy_evidence JSONB NOT NULL,
    dynamic_risk_evidence JSONB NOT NULL,
    decision_dynamic_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    static_manifest_identity JSONB NOT NULL DEFAULT '{}'::jsonb,
    strategy_manifest_id TEXT NULL
        CONSTRAINT pre_execution_provenance_artifact_strategy_manifest_id_fkey
        REFERENCES handa_live.governance_artifact_manifest(artifact_id),
    policy_manifest_id TEXT NULL
        CONSTRAINT pre_execution_provenance_artifact_policy_manifest_id_fkey
        REFERENCES handa_live.governance_artifact_manifest(artifact_id),
    risk_manifest_id TEXT NULL
        CONSTRAINT pre_execution_provenance_artifact_risk_manifest_id_fkey
        REFERENCES handa_live.governance_artifact_manifest(artifact_id),
    configuration_manifest_id TEXT NULL
        CONSTRAINT pre_execution_provenance_configuration_manifest_id_fkey
        REFERENCES handa_live.governance_artifact_manifest(artifact_id),
    freshness_manifest_id TEXT NULL
        CONSTRAINT pre_execution_provenance_artifact_freshness_manifest_id_fkey
        REFERENCES handa_live.governance_artifact_manifest(artifact_id),
    binding_status TEXT NOT NULL,
    CONSTRAINT pre_execution_provenance_artifact_binding_status_ck
        CHECK (binding_status IN ('BOUND', 'UNBOUND', 'INCOMPLETE')),
    canonical_semantic_digest TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pre_execution_provenance_digest_uq
        UNIQUE (canonical_semantic_digest),
    CONSTRAINT pre_execution_provenance_text_ck
        CHECK (
            btrim(provenance_artifact_id) <> ''
            AND btrim(candidate_evidence_identity) <> ''
            AND btrim(symbol) <> ''
            AND btrim(canonical_semantic_digest) <> ''
        ),
    CONSTRAINT pre_execution_provenance_binding_ck
        CHECK (
            binding_status <> 'BOUND'
            OR (
                strategy_manifest_id IS NOT NULL
                AND policy_manifest_id IS NOT NULL
                AND risk_manifest_id IS NOT NULL
                AND configuration_manifest_id IS NOT NULL
                AND freshness_manifest_id IS NOT NULL
            )
        )
);

CREATE INDEX pre_execution_provenance_symbol_recorded_idx
    ON handa_live.pre_execution_provenance_artifact (symbol, recorded_at);

CREATE OR REPLACE FUNCTION handa_live.guard_pre_execution_provenance_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'pre-execution provenance artifacts are immutable';
END;
$$;

CREATE TRIGGER pre_execution_provenance_immutability_guard
BEFORE UPDATE OR DELETE
ON handa_live.pre_execution_provenance_artifact
FOR EACH ROW
EXECUTE FUNCTION handa_live.guard_pre_execution_provenance_immutability();
