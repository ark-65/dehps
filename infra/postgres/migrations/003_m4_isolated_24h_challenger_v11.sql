BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dehps_m4_isolated_v11') THEN
    CREATE ROLE dehps_m4_isolated_v11 NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
  END IF;
END
$$;

CREATE SCHEMA IF NOT EXISTS m4_isolated_v11;
REVOKE ALL ON SCHEMA m4_isolated_v11 FROM PUBLIC;
GRANT USAGE ON SCHEMA m4_isolated_v11 TO dehps_m4_isolated_v11;

CREATE TABLE IF NOT EXISTS m4_isolated_v11.schema_identity (
  singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
  schema_version TEXT NOT NULL,
  contract_digest TEXT NOT NULL CHECK (contract_digest ~ '^[0-9a-f]{64}$'),
  installed_git_commit TEXT NOT NULL CHECK (installed_git_commit ~ '^[0-9a-f]{40}$'),
  installed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS m4_isolated_v11.multiplicity_head (
  singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
  registration_seq BIGINT NOT NULL CHECK (registration_seq >= -1),
  m_total BIGINT NOT NULL CHECK (m_total BETWEEN 0 AND 1000000),
  head_artifact_digest TEXT CHECK (head_artifact_digest ~ '^[0-9a-f]{64}$'),
  committed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((registration_seq = -1 AND m_total = 0)
      OR (registration_seq >= 0 AND m_total >= 18 AND head_artifact_digest IS NOT NULL))
);

INSERT INTO m4_isolated_v11.multiplicity_head (
  singleton, registration_seq, m_total, head_artifact_digest
) VALUES (TRUE, -1, 0, NULL)
ON CONFLICT (singleton) DO NOTHING;

CREATE TABLE IF NOT EXISTS m4_isolated_v11.registration_batches (
  registration_seq BIGINT PRIMARY KEY CHECK (registration_seq >= 0),
  batch_seq BIGINT NOT NULL UNIQUE CHECK (batch_seq >= 0),
  epoch_date DATE NOT NULL,
  target_issue TEXT NOT NULL CHECK (target_issue ~ '^[0-9]{7}$'),
  batch_plan_digest TEXT NOT NULL UNIQUE CHECK (batch_plan_digest ~ '^[0-9a-f]{64}$'),
  batch_plan_json JSONB NOT NULL,
  registration_execution_id TEXT NOT NULL CHECK (registration_execution_id ~ '^[0-9a-f]{64}$'),
  predecessor_head_digest TEXT,
  registration_delta_digest TEXT NOT NULL UNIQUE CHECK (registration_delta_digest ~ '^[0-9a-f]{64}$'),
  registration_head_digest TEXT NOT NULL UNIQUE CHECK (registration_head_digest ~ '^[0-9a-f]{64}$'),
  m_before BIGINT NOT NULL CHECK (m_before BETWEEN 0 AND 999982),
  m_after BIGINT NOT NULL CHECK (m_after = m_before + 18 AND m_after <= 1000000),
  candidate_count INTEGER NOT NULL CHECK (candidate_count = 18),
  committed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS m4_isolated_v11.candidate_registrations (
  candidate_id TEXT PRIMARY KEY CHECK (candidate_id ~ '^[0-9a-f]{64}$'),
  registration_seq BIGINT NOT NULL REFERENCES m4_isolated_v11.registration_batches(registration_seq),
  slot_ordinal SMALLINT NOT NULL CHECK (slot_ordinal BETWEEN 0 AND 17),
  configuration_id TEXT NOT NULL CHECK (configuration_id ~ '^[0-9a-f]{64}$'),
  cohort_id TEXT NOT NULL CHECK (cohort_id ~ '^[0-9a-f]{64}$'),
  parent_configuration_id TEXT CHECK (parent_configuration_id ~ '^[0-9a-f]{64}$'),
  parent_candidate_id TEXT CHECK (parent_candidate_id ~ '^[0-9a-f]{64}$'),
  family TEXT NOT NULL CHECK (family IN (
    'MARGINAL_STATIC_ALPHA', 'LOGISTIC_L2_LIBLINEAR',
    'BERNOULLI_NAIVE_BAYES', 'SHALLOW_PLATT_TREE',
    'FEATURE_ABI32_LINEAR_RANKER'
  )),
  feature_ids_json JSONB NOT NULL,
  hyperparameters_json JSONB NOT NULL,
  training_window TEXT NOT NULL CHECK (training_window IN ('900', '1500', 'ALL_AVAILABLE')),
  seed_ordinal SMALLINT NOT NULL CHECK (seed_ordinal BETWEEN 0 AND 2),
  seed_hex TEXT NOT NULL CHECK (seed_hex ~ '^[0-9a-f]{32}$'),
  snapshot_digest TEXT NOT NULL CHECK (snapshot_digest ~ '^[0-9a-f]{64}$'),
  source_contract_digest TEXT NOT NULL CHECK (source_contract_digest ~ '^[0-9a-f]{64}$'),
  artifact_digest TEXT NOT NULL UNIQUE CHECK (artifact_digest ~ '^[0-9a-f]{64}$'),
  state TEXT NOT NULL DEFAULT 'REGISTERED' CHECK (state IN ('REGISTERED', 'LEASED', 'TERMINAL')),
  lease_owner TEXT,
  lease_token TEXT CHECK (lease_token ~ '^[0-9a-f]{64}$'),
  retry_cursor SMALLINT CHECK (retry_cursor BETWEEN 0 AND 2),
  lease_acquired_at TIMESTAMPTZ,
  heartbeat_at TIMESTAMPTZ,
  worker_started_at TIMESTAMPTZ,
  registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (registration_seq, slot_ordinal),
  UNIQUE (configuration_id, snapshot_digest, seed_ordinal),
  CHECK ((state = 'REGISTERED' AND lease_owner IS NULL AND lease_token IS NULL
          AND retry_cursor IS NULL AND lease_acquired_at IS NULL
          AND heartbeat_at IS NULL AND worker_started_at IS NULL)
      OR (state IN ('LEASED', 'TERMINAL') AND lease_owner IS NOT NULL
          AND lease_token IS NOT NULL AND retry_cursor IS NOT NULL
          AND lease_acquired_at IS NOT NULL AND heartbeat_at IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS m4_isolated_v11.multiplicity_registration_artifacts (
  artifact_digest TEXT PRIMARY KEY CHECK (artifact_digest ~ '^[0-9a-f]{64}$'),
  registration_seq BIGINT NOT NULL REFERENCES m4_isolated_v11.registration_batches(registration_seq),
  artifact_type TEXT NOT NULL CHECK (artifact_type IN (
    'M4IsolatedCandidateRegistrationV11',
    'M4IsolatedMultiplicityRegistrationDeltaV11',
    'M4IsolatedMultiplicityRegistrationHeadV11'
  )),
  artifact_json JSONB NOT NULL,
  parent_digests_json JSONB NOT NULL,
  registered_at TIMESTAMPTZ NOT NULL,
  CHECK (jsonb_typeof(artifact_json) = 'object'),
  CHECK (jsonb_typeof(parent_digests_json) = 'array')
);

CREATE TABLE IF NOT EXISTS m4_isolated_v11.execution_attempts (
  execution_attempt_id TEXT PRIMARY KEY CHECK (execution_attempt_id ~ '^[0-9a-f]{64}$'),
  candidate_id TEXT NOT NULL REFERENCES m4_isolated_v11.candidate_registrations(candidate_id),
  retry_ordinal SMALLINT NOT NULL CHECK (retry_ordinal BETWEEN 0 AND 2),
  lease_owner TEXT NOT NULL,
  lease_acquired_at TIMESTAMPTZ NOT NULL,
  heartbeat_at TIMESTAMPTZ NOT NULL,
  worker_started_at TIMESTAMPTZ,
  terminal_at TIMESTAMPTZ,
  status TEXT NOT NULL CHECK (status IN ('LEASED', 'SUCCEEDED', 'FAILED')),
  reason TEXT CHECK (reason IN (
    'P3_PREEMPTED', 'WORKER_PROCESS_CRASH', 'WALL_TIMEOUT',
    'DATA_BOUNDARY_VIOLATION', 'SOURCE_IDENTITY_INVALID',
    'INVALID_FEATURES', 'NONFINITE_SCORE', 'MULTIPLICITY_RISK_LIMIT',
    'PARALLEL_EQUIVALENCE_FAILED'
  )),
  attempt_payload_json JSONB,
  artifact_digest TEXT CHECK (artifact_digest ~ '^[0-9a-f]{64}$'),
  artifact_committed BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (candidate_id, retry_ordinal),
  CHECK ((status = 'LEASED' AND terminal_at IS NULL
          AND attempt_payload_json IS NULL AND artifact_digest IS NULL
          AND artifact_committed = FALSE)
      OR (status <> 'LEASED' AND worker_started_at IS NOT NULL
          AND terminal_at IS NOT NULL AND attempt_payload_json IS NOT NULL
          AND ((artifact_committed = FALSE AND artifact_digest IS NULL)
            OR (artifact_committed = TRUE AND artifact_digest IS NOT NULL))))
);

CREATE TABLE IF NOT EXISTS m4_isolated_v11.candidate_results (
  candidate_id TEXT PRIMARY KEY REFERENCES m4_isolated_v11.candidate_registrations(candidate_id),
  status TEXT NOT NULL CHECK (status IN ('SUCCEEDED', 'FAILED')),
  terminal_reason TEXT,
  ordered_attempt_ids_json JSONB NOT NULL,
  fold_values_hex_json JSONB,
  primary_mean_hex TEXT,
  block_means_hex_json JSONB,
  eligible BOOLEAN NOT NULL DEFAULT FALSE,
  artifact_digest TEXT NOT NULL UNIQUE CHECK (artifact_digest ~ '^[0-9a-f]{64}$'),
  completed_at TIMESTAMPTZ NOT NULL,
  CHECK ((status = 'SUCCEEDED' AND fold_values_hex_json IS NOT NULL
          AND primary_mean_hex IS NOT NULL AND block_means_hex_json IS NOT NULL)
      OR (status = 'FAILED' AND terminal_reason IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS m4_isolated_v11.search_checkpoints (
  batch_seq BIGINT PRIMARY KEY CHECK (batch_seq >= -1),
  target_issue TEXT NOT NULL CHECK (target_issue ~ '^[0-9]{7}$'),
  predecessor_replay_digest TEXT,
  batch_digest TEXT,
  batch_replay_digest TEXT,
  multiplicity_delta_digest TEXT,
  checkpoint_digest TEXT NOT NULL UNIQUE CHECK (checkpoint_digest ~ '^[0-9a-f]{64}$'),
  replay_digest TEXT NOT NULL UNIQUE CHECK (replay_digest ~ '^[0-9a-f]{64}$'),
  registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((batch_seq = -1 AND batch_digest IS NULL AND batch_replay_digest IS NULL)
      OR (batch_seq >= 0 AND batch_digest IS NOT NULL AND batch_replay_digest IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS m4_isolated_v11.delivery_ledger (
  delivery_key TEXT PRIMARY KEY CHECK (delivery_key ~ '^[0-9a-f]{64}$'),
  mail_kind TEXT NOT NULL CHECK (mail_kind IN (
    'PREDRAW_TOP100', 'POSTDRAW_SETTLEMENT',
    'DAILY_24H_RESEARCH_SUMMARY', 'IMMEDIATE_FAIL_CLOSED_INCIDENT'
  )),
  target_identity TEXT NOT NULL,
  content_digest TEXT NOT NULL CHECK (content_digest ~ '^[0-9a-f]{64}$'),
  recipient_set_digest TEXT NOT NULL CHECK (recipient_set_digest ~ '^[0-9a-f]{64}$'),
  state TEXT NOT NULL CHECK (state IN ('SENDING', 'SENT', 'UNCERTAIN')),
  attempt_count INTEGER NOT NULL CHECK (attempt_count = 1),
  receipt_artifact_digest TEXT UNIQUE CHECK (receipt_artifact_digest ~ '^[0-9a-f]{64}$'),
  started_at TIMESTAMPTZ NOT NULL,
  terminal_at TIMESTAMPTZ,
  CHECK ((state = 'SENDING' AND terminal_at IS NULL AND receipt_artifact_digest IS NULL)
      OR (state IN ('SENT', 'UNCERTAIN') AND terminal_at IS NOT NULL
          AND receipt_artifact_digest IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS m4_isolated_v11.registered_inputs (
  artifact_digest TEXT PRIMARY KEY CHECK (artifact_digest ~ '^[0-9a-f]{64}$'),
  artifact_type TEXT NOT NULL CHECK (artifact_type IN (
    'm4_isolated_24h_challenger_source_contract_v11',
    'M4IsolatedDatabaseSchemaIdentityV11',
    'M4IsolatedHistorySchemaInputV11',
    'M4IsolatedHistoryContentInputV11',
    'M4IsolatedAuditedDrawInputV11'
  )),
  artifact_json JSONB NOT NULL CHECK (jsonb_typeof(artifact_json) = 'object'),
  parent_digests_json JSONB NOT NULL CHECK (jsonb_typeof(parent_digests_json) = 'array'),
  git_commit TEXT NOT NULL CHECK (git_commit ~ '^[0-9a-f]{40}$'),
  source_path TEXT,
  content_sha256 TEXT NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((artifact_type = 'm4_isolated_24h_challenger_source_contract_v11'
          AND source_path = 'configs/research-os/m4-isolated-24h-challenger-source-v11.json')
      OR (artifact_type <> 'm4_isolated_24h_challenger_source_contract_v11'
          AND source_path IS NULL))
);

CREATE OR REPLACE FUNCTION m4_isolated_v11.reject_append_only_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'm4_isolated_v11 append-only relation cannot be mutated';
END
$$;

DROP TRIGGER IF EXISTS registration_batches_append_only ON m4_isolated_v11.registration_batches;
CREATE TRIGGER registration_batches_append_only
BEFORE UPDATE OR DELETE ON m4_isolated_v11.registration_batches
FOR EACH ROW EXECUTE FUNCTION m4_isolated_v11.reject_append_only_mutation();

DROP TRIGGER IF EXISTS candidate_results_append_only ON m4_isolated_v11.candidate_results;
CREATE TRIGGER candidate_results_append_only
BEFORE UPDATE OR DELETE ON m4_isolated_v11.candidate_results
FOR EACH ROW EXECUTE FUNCTION m4_isolated_v11.reject_append_only_mutation();

DROP TRIGGER IF EXISTS multiplicity_registration_artifacts_append_only
ON m4_isolated_v11.multiplicity_registration_artifacts;
CREATE TRIGGER multiplicity_registration_artifacts_append_only
BEFORE UPDATE OR DELETE ON m4_isolated_v11.multiplicity_registration_artifacts
FOR EACH ROW EXECUTE FUNCTION m4_isolated_v11.reject_append_only_mutation();

DROP TRIGGER IF EXISTS search_checkpoints_append_only ON m4_isolated_v11.search_checkpoints;
CREATE TRIGGER search_checkpoints_append_only
BEFORE UPDATE OR DELETE ON m4_isolated_v11.search_checkpoints
FOR EACH ROW EXECUTE FUNCTION m4_isolated_v11.reject_append_only_mutation();

DROP TRIGGER IF EXISTS delivery_ledger_append_only ON m4_isolated_v11.delivery_ledger;
CREATE TRIGGER delivery_ledger_append_only
BEFORE UPDATE OR DELETE ON m4_isolated_v11.delivery_ledger
FOR EACH ROW EXECUTE FUNCTION m4_isolated_v11.reject_append_only_mutation();

DROP TRIGGER IF EXISTS schema_identity_append_only ON m4_isolated_v11.schema_identity;
CREATE TRIGGER schema_identity_append_only
BEFORE UPDATE OR DELETE ON m4_isolated_v11.schema_identity
FOR EACH ROW EXECUTE FUNCTION m4_isolated_v11.reject_append_only_mutation();

DROP TRIGGER IF EXISTS registered_inputs_append_only ON m4_isolated_v11.registered_inputs;
CREATE TRIGGER registered_inputs_append_only
BEFORE UPDATE OR DELETE ON m4_isolated_v11.registered_inputs
FOR EACH ROW EXECUTE FUNCTION m4_isolated_v11.reject_append_only_mutation();

CREATE OR REPLACE FUNCTION m4_isolated_v11.register_exact_batch(
  p_batch_seq BIGINT,
  p_epoch_date DATE,
  p_target_issue TEXT,
  p_batch_plan_digest TEXT,
  p_batch_plan JSONB,
  p_registration_execution_id TEXT,
  p_predecessor_head_digest TEXT,
  p_registration_delta_digest TEXT,
  p_registration_head_digest TEXT,
  p_candidates JSONB,
  p_registration_artifacts JSONB,
  p_committed_at TIMESTAMPTZ
) RETURNS TABLE(registration_seq BIGINT, m_before BIGINT, m_after BIGINT)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = m4_isolated_v11, pg_temp
AS $$
DECLARE
  v_head m4_isolated_v11.multiplicity_head%ROWTYPE;
  v_registration_seq BIGINT;
BEGIN
  IF jsonb_typeof(p_candidates) <> 'array' OR jsonb_array_length(p_candidates) <> 18 THEN
    RAISE EXCEPTION 'atomic batch must contain exactly 18 candidates';
  END IF;
  IF (SELECT count(DISTINCT value->>'candidate_id') FROM jsonb_array_elements(p_candidates)) <> 18 THEN
    RAISE EXCEPTION 'atomic batch candidate ids must be unique';
  END IF;
  IF jsonb_typeof(p_registration_artifacts) <> 'array'
     OR jsonb_array_length(p_registration_artifacts) <> 20 THEN
    RAISE EXCEPTION 'atomic batch must contain exactly 20 registration artifacts';
  END IF;
  IF (SELECT count(DISTINCT value->>'artifact_digest')
      FROM jsonb_array_elements(p_registration_artifacts)) <> 20 THEN
    RAISE EXCEPTION 'atomic batch registration artifact digests must be unique';
  END IF;
  IF (SELECT count(*) FROM jsonb_array_elements(p_registration_artifacts)
      WHERE value->>'artifact_type' = 'M4IsolatedCandidateRegistrationV11') <> 18
     OR (SELECT count(*) FROM jsonb_array_elements(p_registration_artifacts)
         WHERE value->>'artifact_type' = 'M4IsolatedMultiplicityRegistrationDeltaV11') <> 1
     OR (SELECT count(*) FROM jsonb_array_elements(p_registration_artifacts)
         WHERE value->>'artifact_type' = 'M4IsolatedMultiplicityRegistrationHeadV11') <> 1 THEN
    RAISE EXCEPTION 'atomic batch registration artifact type set changed';
  END IF;
  SELECT * INTO STRICT v_head
  FROM m4_isolated_v11.multiplicity_head
  WHERE singleton = TRUE
  FOR UPDATE;
  IF v_head.m_total + 18 > 1000000 THEN
    RAISE EXCEPTION 'MULTIPLICITY_RISK_LIMIT';
  END IF;
  IF v_head.head_artifact_digest IS DISTINCT FROM p_predecessor_head_digest THEN
    RAISE EXCEPTION 'multiplicity predecessor head mismatch';
  END IF;
  v_registration_seq := v_head.registration_seq + 1;
  INSERT INTO m4_isolated_v11.registration_batches (
    registration_seq, batch_seq, epoch_date, target_issue,
    batch_plan_digest, batch_plan_json, registration_execution_id,
    predecessor_head_digest, registration_delta_digest, registration_head_digest,
    m_before, m_after, candidate_count, committed_at
  ) VALUES (
    v_registration_seq, p_batch_seq, p_epoch_date, p_target_issue,
    p_batch_plan_digest, p_batch_plan, p_registration_execution_id,
    p_predecessor_head_digest, p_registration_delta_digest, p_registration_head_digest,
    v_head.m_total, v_head.m_total + 18, 18, p_committed_at
  );
  INSERT INTO m4_isolated_v11.candidate_registrations (
    candidate_id, registration_seq, slot_ordinal, configuration_id, cohort_id,
    parent_configuration_id, parent_candidate_id, family, feature_ids_json, hyperparameters_json,
    training_window, seed_ordinal, seed_hex, snapshot_digest,
    source_contract_digest, artifact_digest, registered_at
  )
  SELECT
    value->>'candidate_id', v_registration_seq, (value->>'slot_ordinal')::SMALLINT,
    value->>'configuration_id', value->>'cohort_id',
    NULLIF(value->>'parent_configuration_id', ''),
    NULLIF(value->>'parent_candidate_id', ''), value->>'family',
    value->'feature_ids', value->'hyperparameters', value->>'training_window',
    (value->>'seed_ordinal')::SMALLINT, value->>'seed_hex',
    value->>'snapshot_digest', value->>'source_contract_digest',
    value->>'artifact_digest', p_committed_at
  FROM jsonb_array_elements(p_candidates);
  INSERT INTO m4_isolated_v11.multiplicity_registration_artifacts (
    artifact_digest, registration_seq, artifact_type, artifact_json,
    parent_digests_json, registered_at
  )
  SELECT
    value->>'artifact_digest', v_registration_seq, value->>'artifact_type',
    value, value->'parent_digests', p_committed_at
  FROM jsonb_array_elements(p_registration_artifacts);
  UPDATE m4_isolated_v11.multiplicity_head
  SET registration_seq = v_registration_seq,
      m_total = v_head.m_total + 18,
      head_artifact_digest = p_registration_head_digest,
      committed_at = p_committed_at
  WHERE singleton = TRUE;
  RETURN QUERY SELECT v_registration_seq, v_head.m_total, v_head.m_total + 18;
END
$$;

REVOKE ALL ON ALL TABLES IN SCHEMA m4_isolated_v11 FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA m4_isolated_v11 FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA m4_isolated_v11 TO dehps_m4_isolated_v11;
GRANT DELETE ON m4_isolated_v11.execution_attempts TO dehps_m4_isolated_v11;
GRANT EXECUTE ON FUNCTION m4_isolated_v11.register_exact_batch(
  BIGINT, DATE, TEXT, TEXT, JSONB, TEXT, TEXT, TEXT, TEXT, JSONB, JSONB,
  TIMESTAMPTZ
) TO dehps_m4_isolated_v11;

COMMIT;
