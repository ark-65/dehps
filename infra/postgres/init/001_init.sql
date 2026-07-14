CREATE TABLE IF NOT EXISTS ssq_red_combinations (
  id BIGSERIAL PRIMARY KEY,
  numbers SMALLINT[] NOT NULL UNIQUE,
  n1 SMALLINT NOT NULL,
  n2 SMALLINT NOT NULL,
  n3 SMALLINT NOT NULL,
  n4 SMALLINT NOT NULL,
  n5 SMALLINT NOT NULL,
  n6 SMALLINT NOT NULL,
  sum_value SMALLINT NOT NULL,
  span_value SMALLINT NOT NULL,
  odd_count SMALLINT NOT NULL,
  even_count SMALLINT NOT NULL,
  small_count SMALLINT NOT NULL,
  big_count SMALLINT NOT NULL,
  zone_1_count SMALLINT NOT NULL,
  zone_2_count SMALLINT NOT NULL,
  zone_3_count SMALLINT NOT NULL,
  consecutive_pair_count SMALLINT NOT NULL,
  max_consecutive_run SMALLINT NOT NULL,
  min_gap SMALLINT NOT NULL,
  max_gap SMALLINT NOT NULL,
  is_arithmetic_sequence BOOLEAN NOT NULL,
  gua_odd_even TEXT,
  gua_small_big TEXT,
  pattern_complexity_score NUMERIC(8,4),
  anomaly_penalty NUMERIC(8,4),
  structure_naturalness_score NUMERIC(8,4),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ssq_history (
  id BIGSERIAL PRIMARY KEY,
  issue TEXT NOT NULL UNIQUE,
  draw_date DATE,
  red_numbers SMALLINT[] NOT NULL,
  r1 SMALLINT NOT NULL,
  r2 SMALLINT NOT NULL,
  r3 SMALLINT NOT NULL,
  r4 SMALLINT NOT NULL,
  r5 SMALLINT NOT NULL,
  r6 SMALLINT NOT NULL,
  blue_number SMALLINT,
  source TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dehps_strategies (
  id BIGSERIAL PRIMARY KEY,
  strategy_key TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  description TEXT,
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dehps_experiments (
  id BIGSERIAL PRIMARY KEY,
  experiment_key TEXT NOT NULL UNIQUE,
  strategy_key TEXT NOT NULL,
  hypothesis TEXT,
  total_combinations INTEGER NOT NULL,
  kept_combinations INTEGER NOT NULL,
  keep_rate NUMERIC(12,8) NOT NULL,
  history_draws INTEGER NOT NULL,
  covered_draws INTEGER NOT NULL,
  coverage_rate NUMERIC(12,8) NOT NULL,
  lift NUMERIC(12,8) NOT NULL,
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  summary TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dehps_experiment_reports (
  id BIGSERIAL PRIMARY KEY,
  experiment_key TEXT NOT NULL,
  report_markdown TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ssq_sync_runs (
  id BIGSERIAL PRIMARY KEY,
  run_key TEXT NOT NULL UNIQUE,
  source TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  fetched_count INTEGER NOT NULL DEFAULT 0,
  inserted_count INTEGER NOT NULL DEFAULT 0,
  updated_count INTEGER NOT NULL DEFAULT 0,
  skipped_count INTEGER NOT NULL DEFAULT 0,
  conflict_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  raw_meta JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS ssq_data_conflicts (
  id BIGSERIAL PRIMARY KEY,
  issue TEXT NOT NULL,
  existing_red_numbers SMALLINT[],
  incoming_red_numbers SMALLINT[],
  existing_blue_number SMALLINT,
  incoming_blue_number SMALLINT,
  source TEXT,
  conflict_reason TEXT,
  raw_payload JSONB,
  resolution_action TEXT,
  resolution_note TEXT,
  resolved_by TEXT,
  resolved_red_numbers SMALLINT[],
  resolved_blue_number SMALLINT,
  resolved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
  id BIGSERIAL PRIMARY KEY,
  run_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  sync_run_key TEXT,
  experiment_key TEXT,
  git_commit_sha TEXT,
  error_message TEXT,
  summary JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS ssq_draw_sites (
  id BIGSERIAL PRIMARY KEY,
  site_key TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  address TEXT NOT NULL,
  latitude NUMERIC(9,6) NOT NULL,
  longitude NUMERIC(9,6) NOT NULL,
  coordinate_system TEXT NOT NULL DEFAULT 'WGS84',
  accuracy_note TEXT,
  address_source_url TEXT,
  draw_location_source_url TEXT,
  effective_from_issue TEXT,
  effective_to_issue TEXT,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS training_round_results (
  id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL,
  round_index INTEGER NOT NULL,
  phase TEXT NOT NULL,
  step NUMERIC(10,6) NOT NULL,
  train_mode TEXT NOT NULL,
  train_window INTEGER NOT NULL,
  eval_window INTEGER NOT NULL,
  top_n INTEGER NOT NULL,
  as_of_issue TEXT NOT NULL,
  history_fingerprint TEXT NOT NULL,
  objective_policy_version TEXT NOT NULL DEFAULT 'legacy_unversioned',
  objective_policy_hash TEXT NOT NULL DEFAULT '',
  improved BOOLEAN NOT NULL DEFAULT false,
  top_100_hits INTEGER NOT NULL DEFAULT 0,
  top_1000_hits INTEGER NOT NULL DEFAULT 0,
  top_10000_hits INTEGER NOT NULL DEFAULT 0,
  red5_top_100_hits INTEGER NOT NULL DEFAULT 0,
  red5_top_1000_hits INTEGER NOT NULL DEFAULT 0,
  red5_top_10000_hits INTEGER NOT NULL DEFAULT 0,
  median_rank NUMERIC(12,2),
  best_rank INTEGER,
  worst_rank INTEGER,
  objective_score NUMERIC(14,6),
  best_config JSONB NOT NULL DEFAULT '{}'::jsonb,
  best_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  top_results JSONB NOT NULL DEFAULT '[]'::jsonb,
  target_results JSONB NOT NULL DEFAULT '[]'::jsonb,
  prefilter JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (run_id, round_index)
);

CREATE INDEX IF NOT EXISTS idx_training_round_results_created_at
  ON training_round_results (created_at DESC, round_index DESC);

CREATE TABLE IF NOT EXISTS training_target_weight_inversions (
  id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL,
  round_index INTEGER NOT NULL,
  target_issue TEXT NOT NULL,
  red_numbers INTEGER[] NOT NULL,
  current_rank INTEGER NOT NULL,
  hit_top10000 BOOLEAN NOT NULL DEFAULT false,
  score NUMERIC(14,8) NOT NULL,
  rank_margin INTEGER NOT NULL,
  base_config_hash TEXT NOT NULL,
  required_delta_config JSONB NOT NULL DEFAULT '{}'::jsonb,
  adjusted_rank INTEGER,
  adjusted_hit_top10000 BOOLEAN NOT NULL DEFAULT false,
  delta_norm NUMERIC(14,8),
  changed_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
  success BOOLEAN NOT NULL DEFAULT false,
  outlier_reason TEXT,
  aggregate JSONB NOT NULL DEFAULT '{}'::jsonb,
  prefilter JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (run_id, round_index, target_issue, base_config_hash)
);

CREATE INDEX IF NOT EXISTS idx_training_target_weight_inversions_issue
  ON training_target_weight_inversions (target_issue, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_training_target_weight_inversions_success
  ON training_target_weight_inversions (success, target_issue);

CREATE TABLE IF NOT EXISTS training_weight_signals (
  id BIGSERIAL PRIMARY KEY,
  signal_run_id TEXT NOT NULL,
  issue TEXT NOT NULL,
  draw_date DATE,
  weight_name TEXT NOT NULL,
  train_mode TEXT NOT NULL,
  train_window INTEGER NOT NULL,
  eval_window INTEGER NOT NULL,
  top_n INTEGER NOT NULL,
  history_fingerprint TEXT NOT NULL,
  source TEXT NOT NULL,
  base_value NUMERIC(12,6) NOT NULL,
  close_value NUMERIC(12,6) NOT NULL,
  issue_low_value NUMERIC(12,6) NOT NULL,
  issue_high_value NUMERIC(12,6) NOT NULL,
  rolling_low_value NUMERIC(12,6) NOT NULL,
  rolling_high_value NUMERIC(12,6) NOT NULL,
  rsv NUMERIC(12,6) NOT NULL,
  k_value NUMERIC(12,6) NOT NULL,
  d_value NUMERIC(12,6) NOT NULL,
  j_value NUMERIC(12,6) NOT NULL,
  recommended_offset NUMERIC(12,6) NOT NULL,
  best_objective_score NUMERIC(14,6) NOT NULL,
  objective_delta NUMERIC(14,6) NOT NULL,
  sample_count INTEGER NOT NULL,
  probe_results JSONB NOT NULL DEFAULT '[]'::jsonb,
  advisor_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (signal_run_id, issue, weight_name)
);

CREATE INDEX IF NOT EXISTS idx_training_weight_signals_weight_issue
  ON training_weight_signals (weight_name, issue);

CREATE INDEX IF NOT EXISTS idx_training_weight_signals_run_issue
  ON training_weight_signals (signal_run_id, issue);

CREATE INDEX IF NOT EXISTS idx_training_weight_signals_run_weight_issue
  ON training_weight_signals (signal_run_id, weight_name, issue);

CREATE TABLE IF NOT EXISTS training_next_candidates_current (
  id BIGSERIAL PRIMARY KEY,
  line_key TEXT NOT NULL DEFAULT 'static_100',
  line_label TEXT NOT NULL DEFAULT '100-period static training',
  line_kind TEXT NOT NULL DEFAULT 'static',
  snapshot_key TEXT NOT NULL,
  run_id TEXT NOT NULL,
  source_round_index INTEGER,
  as_of_issue TEXT NOT NULL,
  next_issue TEXT NOT NULL,
  next_draw_date DATE,
  train_mode TEXT NOT NULL,
  train_window INTEGER NOT NULL,
  eval_window INTEGER NOT NULL,
  top_n INTEGER NOT NULL,
  history_fingerprint TEXT NOT NULL,
  config_hash TEXT NOT NULL,
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  prediction_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  rank INTEGER NOT NULL,
  red_numbers SMALLINT[] NOT NULL,
  score NUMERIC(14,8) NOT NULL,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_training_next_candidates_current_line_rank
  ON training_next_candidates_current (line_key, rank);

CREATE INDEX IF NOT EXISTS idx_training_next_candidates_current_generated
  ON training_next_candidates_current (generated_at DESC);

CREATE INDEX IF NOT EXISTS idx_training_next_candidates_current_line_issue
  ON training_next_candidates_current (line_key, next_issue, generated_at DESC);

CREATE TABLE IF NOT EXISTS training_prediction_evaluations (
  id BIGSERIAL PRIMARY KEY,
  evaluation_key TEXT NOT NULL UNIQUE,
  line_key TEXT NOT NULL,
  line_label TEXT NOT NULL,
  line_kind TEXT NOT NULL,
  snapshot_key TEXT,
  run_id TEXT,
  source_round_index INTEGER,
  as_of_issue TEXT,
  predicted_issue TEXT NOT NULL,
  actual_draw_date DATE,
  actual_red_numbers SMALLINT[],
  actual_blue_number SMALLINT,
  exact_rank INTEGER,
  exact_score NUMERIC(14,8),
  hit_top_100 BOOLEAN NOT NULL DEFAULT false,
  hit_top_1000 BOOLEAN NOT NULL DEFAULT false,
  hit_top_10000 BOOLEAN NOT NULL DEFAULT false,
  red5_rank INTEGER,
  red5_score NUMERIC(14,8),
  red5_numbers SMALLINT[],
  hit_red5_top_100 BOOLEAN NOT NULL DEFAULT false,
  hit_red5_top_1000 BOOLEAN NOT NULL DEFAULT false,
  hit_red5_top_10000 BOOLEAN NOT NULL DEFAULT false,
  candidate_count INTEGER NOT NULL DEFAULT 0,
  snapshot_generated_at TIMESTAMPTZ,
  status TEXT NOT NULL,
  summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  prediction_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  json_path TEXT,
  report_path TEXT,
  guardrail TEXT NOT NULL DEFAULT '',
  evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_training_prediction_evaluations_line_issue
  ON training_prediction_evaluations (line_key, predicted_issue, evaluated_at DESC);

CREATE TABLE IF NOT EXISTS research_hypothesis_families (
  id BIGSERIAL PRIMARY KEY,
  family_key TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  mechanism TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'partially_rejected', 'rejected', 'exhausted', 'reopened')),
  rejection_scope TEXT NOT NULL DEFAULT 'none'
    CHECK (rejection_scope IN ('none', 'parameter_region', 'mechanism_family')),
  rejection_reason TEXT,
  reopen_condition TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(metadata_json) = 'object')
);

CREATE TABLE IF NOT EXISTS research_hypotheses (
  id BIGSERIAL PRIMARY KEY,
  hypothesis_key TEXT NOT NULL UNIQUE,
  family_id BIGINT NOT NULL REFERENCES research_hypothesis_families(id) ON DELETE RESTRICT,
  parent_hypothesis_id BIGINT REFERENCES research_hypotheses(id) ON DELETE RESTRICT,
  title TEXT NOT NULL,
  statement TEXT NOT NULL DEFAULT '',
  mechanism TEXT NOT NULL,
  null_hypothesis TEXT NOT NULL DEFAULT '',
  minimal_non_null TEXT NOT NULL DEFAULT '',
  invariants_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  baseline_definition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  metric_definition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  failure_condition_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  self_deception_risk_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  status TEXT NOT NULL DEFAULT 'proposed'
    CHECK (status IN ('proposed', 'preregistered', 'running', 'accepted_for_followup', 'rejected', 'inconclusive', 'invalidated')),
  rejection_scope TEXT NOT NULL DEFAULT 'none'
    CHECK (rejection_scope IN ('none', 'parameter_region', 'mechanism_family')),
  rejection_reason TEXT,
  reopen_condition TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  preregistered_at TIMESTAMPTZ,
  started_at TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(metadata_json) = 'object'),
  CHECK (parent_hypothesis_id IS NULL OR parent_hypothesis_id <> id)
);

CREATE TABLE IF NOT EXISTS research_hypothesis_experiments (
  id BIGSERIAL PRIMARY KEY,
  hypothesis_id BIGINT NOT NULL REFERENCES research_hypotheses(id) ON DELETE RESTRICT,
  experiment_key TEXT NOT NULL UNIQUE,
  experiment_type TEXT NOT NULL,
  external_run_id TEXT,
  training_run_id TEXT,
  training_round_index INTEGER,
  report_path TEXT,
  artifact_paths_json JSONB NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(artifact_paths_json) = 'array'),
  config_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(config_snapshot_json) = 'object'),
  status TEXT NOT NULL DEFAULT 'planned'
    CHECK (status IN ('planned', 'running', 'completed', 'failed', 'invalidated', 'cancelled')),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(metadata_json) = 'object'),
  CHECK (training_round_index IS NULL OR training_round_index > 0),
  CHECK (training_round_index IS NULL OR training_run_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS research_hypothesis_evidence (
  id BIGSERIAL PRIMARY KEY,
  hypothesis_id BIGINT NOT NULL REFERENCES research_hypotheses(id) ON DELETE RESTRICT,
  experiment_id BIGINT REFERENCES research_hypothesis_experiments(id) ON DELETE RESTRICT,
  evidence_type TEXT NOT NULL,
  direction TEXT NOT NULL
    CHECK (direction IN ('supporting', 'contradicting', 'neutral', 'invalidating')),
  summary TEXT NOT NULL,
  metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(metrics_json) = 'object'),
  artifact_path TEXT,
  content_hash TEXT,
  observed_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(metadata_json) = 'object')
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_research_hypothesis_evidence_content
  ON research_hypothesis_evidence (hypothesis_id, evidence_type, content_hash)
  WHERE content_hash IS NOT NULL;

CREATE TABLE IF NOT EXISTS research_hypothesis_decisions (
  id BIGSERIAL PRIMARY KEY,
  hypothesis_id BIGINT REFERENCES research_hypotheses(id) ON DELETE RESTRICT,
  family_id BIGINT REFERENCES research_hypothesis_families(id) ON DELETE RESTRICT,
  previous_status TEXT NOT NULL,
  new_status TEXT NOT NULL,
  decision_code TEXT NOT NULL,
  summary TEXT NOT NULL,
  reason_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(reason_json) = 'object'),
  evidence_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(evidence_ids_json) = 'array'),
  decided_by TEXT NOT NULL,
  decided_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((hypothesis_id IS NOT NULL)::integer + (family_id IS NOT NULL)::integer = 1)
);

CREATE INDEX IF NOT EXISTS idx_research_hypotheses_family_status
  ON research_hypotheses (family_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_research_hypothesis_experiments_hypothesis
  ON research_hypothesis_experiments (hypothesis_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_research_hypothesis_evidence_hypothesis
  ON research_hypothesis_evidence (hypothesis_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_research_hypothesis_decisions_hypothesis
  ON research_hypothesis_decisions (hypothesis_id, decided_at, id);

CREATE OR REPLACE FUNCTION reject_research_decision_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'research hypothesis decisions are immutable';
END;
$$;

DROP TRIGGER IF EXISTS research_hypothesis_decisions_immutable
  ON research_hypothesis_decisions;
CREATE TRIGGER research_hypothesis_decisions_immutable
BEFORE UPDATE OR DELETE ON research_hypothesis_decisions
FOR EACH ROW EXECUTE FUNCTION reject_research_decision_mutation();

CREATE OR REPLACE FUNCTION guard_research_status_transition()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status IS DISTINCT FROM OLD.status
     AND current_setting('dehps.registry_status_transition', true) IS DISTINCT FROM 'allowed' THEN
    RAISE EXCEPTION 'research status changes must use the hypothesis registry repository';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS research_hypotheses_status_guard ON research_hypotheses;
CREATE TRIGGER research_hypotheses_status_guard
BEFORE UPDATE OF status ON research_hypotheses
FOR EACH ROW EXECUTE FUNCTION guard_research_status_transition();

DROP TRIGGER IF EXISTS research_hypothesis_families_status_guard
  ON research_hypothesis_families;
CREATE TRIGGER research_hypothesis_families_status_guard
BEFORE UPDATE OF status ON research_hypothesis_families
FOR EACH ROW EXECUTE FUNCTION guard_research_status_transition();

CREATE TABLE IF NOT EXISTS agent_requests (
  id BIGSERIAL PRIMARY KEY,
  request_key TEXT NOT NULL UNIQUE,
  request_type TEXT NOT NULL CHECK (request_type IN (
    'research_hypothesis_proposal', 'research_preregistration',
    'research_experiment_plan', 'research_evidence_submission',
    'research_decision_submission', 'research_scheduler_request',
    'engineering_implementation',
    'engineering_bug_fix', 'engineering_test_addition',
    'engineering_runtime_fix', 'engineering_experiment_tool',
    'operator_isolated_run', 'operator_database_migration',
    'operator_supervisor_restart', 'operator_release'
  )),
  requested_by_role TEXT NOT NULL
    CHECK (requested_by_role IN ('research', 'engineering', 'reviewer', 'operator')),
  requested_by TEXT NOT NULL,
  hypothesis_id BIGINT REFERENCES research_hypotheses(id) ON DELETE RESTRICT,
  experiment_id BIGINT REFERENCES research_hypothesis_experiments(id) ON DELETE RESTRICT,
  parent_request_id BIGINT REFERENCES agent_requests(id) ON DELETE RESTRICT,
  title TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(payload_json) = 'object'),
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
    'draft', 'submitted', 'under_review', 'approved', 'rejected',
    'cancelled', 'executing', 'completed', 'failed', 'invalidated'
  )),
  risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
  requires_review BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  submitted_at TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(metadata_json) = 'object'),
  CHECK (parent_request_id IS NULL OR parent_request_id <> id)
);

CREATE TABLE IF NOT EXISTS agent_request_decisions (
  id BIGSERIAL PRIMARY KEY,
  request_id BIGINT NOT NULL REFERENCES agent_requests(id) ON DELETE RESTRICT,
  previous_status TEXT NOT NULL,
  new_status TEXT NOT NULL,
  decision_code TEXT NOT NULL,
  summary TEXT NOT NULL,
  reason_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(reason_json) = 'object'),
  decided_by_role TEXT NOT NULL
    CHECK (decided_by_role IN ('research', 'engineering', 'reviewer', 'operator')),
  decided_by TEXT NOT NULL,
  decided_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_request_executions (
  id BIGSERIAL PRIMARY KEY,
  request_id BIGINT NOT NULL REFERENCES agent_requests(id) ON DELETE RESTRICT,
  executor_role TEXT NOT NULL
    CHECK (executor_role IN ('research', 'engineering', 'reviewer', 'operator')),
  executor_id TEXT NOT NULL,
  execution_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'running'
    CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
  environment TEXT NOT NULL DEFAULT 'isolated'
    CHECK (environment IN ('isolated', 'development', 'production')),
  run_id TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  result_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(result_json) = 'object'),
  artifact_paths_json JSONB NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(artifact_paths_json) = 'array'),
  error_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(error_json) = 'object'),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_requests_status_type
  ON agent_requests (status, request_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_requests_role_risk
  ON agent_requests (requested_by_role, risk_level, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_request_decisions_request
  ON agent_request_decisions (request_id, decided_at, id);
CREATE INDEX IF NOT EXISTS idx_agent_request_executions_request
  ON agent_request_executions (request_id, started_at, id);

CREATE OR REPLACE FUNCTION reject_agent_request_decision_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'agent request decisions are immutable';
END;
$$;

DROP TRIGGER IF EXISTS agent_request_decisions_immutable ON agent_request_decisions;
CREATE TRIGGER agent_request_decisions_immutable
BEFORE UPDATE OR DELETE ON agent_request_decisions
FOR EACH ROW EXECUTE FUNCTION reject_agent_request_decision_mutation();

CREATE OR REPLACE FUNCTION guard_agent_request_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.submitted_at IS NOT NULL THEN
      RAISE EXCEPTION 'submitted agent requests cannot be deleted';
    END IF;
    RETURN OLD;
  END IF;
  IF NEW.status IS DISTINCT FROM OLD.status
     AND current_setting('dehps.agent_request_status_transition', true) IS DISTINCT FROM 'allowed' THEN
    RAISE EXCEPTION 'agent request status changes must use the Agent Request repository';
  END IF;
  IF NEW.payload_json IS DISTINCT FROM OLD.payload_json
     AND (
       OLD.status IN ('approved', 'executing', 'completed', 'failed')
       OR EXISTS (
         SELECT 1 FROM agent_request_decisions d
         WHERE d.request_id = OLD.id AND d.new_status = 'approved'
       )
     ) THEN
    RAISE EXCEPTION 'approved agent request payload is frozen';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS agent_requests_mutation_guard ON agent_requests;
CREATE TRIGGER agent_requests_mutation_guard
BEFORE UPDATE OR DELETE ON agent_requests
FOR EACH ROW EXECUTE FUNCTION guard_agent_request_mutation();

ALTER TABLE IF EXISTS agent_requests
  DROP CONSTRAINT IF EXISTS agent_requests_request_type_check;
ALTER TABLE IF EXISTS agent_requests
  ADD CONSTRAINT agent_requests_request_type_check
  CHECK (request_type IN (
    'research_hypothesis_proposal', 'research_preregistration',
    'research_experiment_plan', 'research_evidence_submission',
    'research_decision_submission', 'research_scheduler_request',
    'engineering_implementation', 'engineering_bug_fix',
    'engineering_test_addition', 'engineering_runtime_fix',
    'engineering_experiment_tool', 'operator_isolated_run',
    'operator_database_migration', 'operator_supervisor_restart',
    'operator_release'
  ));

CREATE TABLE IF NOT EXISTS research_scheduler_queue (
  id BIGSERIAL PRIMARY KEY,
  queue_key TEXT NOT NULL UNIQUE,
  queue_status TEXT NOT NULL CHECK (queue_status IN (
    'proposal', 'planning', 'engineering', 'operator',
    'waiting_forward', 'review', 'completed', 'blocked'
  )),
  action TEXT NOT NULL CHECK (action IN (
    'create_proposal_request', 'create_planning_request',
    'create_engineering_request', 'create_operator_request',
    'create_review_request', 'wait_forward', 'block', 'stop',
    'continue_existing', 'discover_patterns', 'screen_patterns',
    'synthesize_features', 'synthesize_strategies',
    'submit_pattern_hypothesis', 'wait_forward_pattern'
  )),
  priority_score NUMERIC(10,6) NOT NULL DEFAULT 0,
  target_hypothesis_key TEXT,
  target_family_key TEXT,
  target_experiment_key TEXT,
  request_key TEXT REFERENCES agent_requests(request_key) ON DELETE RESTRICT,
  context_fingerprint TEXT NOT NULL,
  reason_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(reason_json) = 'object'),
  budget_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(budget_json) = 'object'),
  policy_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(policy_json) = 'object'),
  created_by TEXT NOT NULL DEFAULT 'research:scheduler',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(metadata_json) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_research_scheduler_queue_status
  ON research_scheduler_queue (queue_status, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_research_scheduler_queue_request
  ON research_scheduler_queue (request_key)
  WHERE request_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_research_scheduler_open_action
  ON research_scheduler_queue (
    action,
    COALESCE(target_hypothesis_key, ''),
    COALESCE(target_family_key, ''),
    COALESCE(target_experiment_key, '')
  )
  WHERE queue_status NOT IN ('completed', 'blocked');

CREATE TABLE IF NOT EXISTS discovered_patterns (
  id BIGSERIAL PRIMARY KEY,
  pattern_key TEXT NOT NULL UNIQUE,
  pattern_family TEXT NOT NULL,
  pattern_type TEXT NOT NULL,
  formula_hash TEXT NOT NULL UNIQUE,
  lifecycle_status TEXT NOT NULL CHECK (lifecycle_status IN (
    'discovered', 'screened', 'frozen_pending', 'frozen_supported',
    'frozen_rejected', 'forward_pending', 'forward_supported',
    'forward_rejected', 'inconclusive', 'invalidated'
  )),
  history_fingerprint TEXT NOT NULL,
  legal_universe_fingerprint TEXT NOT NULL,
  search_issue_range_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(search_issue_range_json) = 'object'),
  formula_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(formula_json) = 'object'),
  parameters_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(parameters_json) = 'object'),
  pattern_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(pattern_json) = 'object'),
  parent_pattern_key TEXT REFERENCES discovered_patterns(pattern_key) ON DELETE RESTRICT,
  multiplicity_family TEXT,
  generator_version TEXT NOT NULL,
  code_commit TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(metadata_json) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_discovered_patterns_family_status
  ON discovered_patterns (pattern_family, lifecycle_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_discovered_patterns_formula_hash
  ON discovered_patterns (formula_hash);

CREATE TABLE IF NOT EXISTS pattern_observations (
  id BIGSERIAL PRIMARY KEY,
  observation_key TEXT NOT NULL UNIQUE,
  pattern_key TEXT NOT NULL REFERENCES discovered_patterns(pattern_key) ON DELETE RESTRICT,
  issue TEXT,
  observed_support NUMERIC(16,8) NOT NULL,
  expected_support NUMERIC(16,8) NOT NULL,
  observation_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(observation_json) = 'object'),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pattern_observations_pattern
  ON pattern_observations (pattern_key, created_at DESC);

CREATE TABLE IF NOT EXISTS pattern_validations (
  id BIGSERIAL PRIMARY KEY,
  validation_key TEXT NOT NULL UNIQUE,
  pattern_key TEXT NOT NULL REFERENCES discovered_patterns(pattern_key) ON DELETE RESTRICT,
  window_type TEXT NOT NULL CHECK (window_type IN ('search', 'frozen', 'forward')),
  decision TEXT NOT NULL CHECK (decision IN ('supported', 'rejected', 'inconclusive', 'invalidated')),
  issue_range_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(issue_range_json) = 'object'),
  frozen_threshold_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(frozen_threshold_json) = 'object'),
  significance_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(significance_json) = 'object'),
  immutable BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pattern_validations_pattern_window
  ON pattern_validations (pattern_key, window_type, created_at DESC);

CREATE TABLE IF NOT EXISTS synthesized_features (
  id BIGSERIAL PRIMARY KEY,
  feature_key TEXT NOT NULL UNIQUE,
  pattern_key TEXT NOT NULL REFERENCES discovered_patterns(pattern_key) ON DELETE RESTRICT,
  formula_hash TEXT NOT NULL,
  feature_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(feature_json) = 'object'),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_synthesized_features_pattern
  ON synthesized_features (pattern_key, created_at DESC);

CREATE TABLE IF NOT EXISTS synthesized_strategies (
  id BIGSERIAL PRIMARY KEY,
  strategy_key TEXT NOT NULL UNIQUE,
  feature_key TEXT NOT NULL REFERENCES synthesized_features(feature_key) ON DELETE RESTRICT,
  strategy_type TEXT NOT NULL,
  strategy_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(strategy_json) = 'object'),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_synthesized_strategies_feature
  ON synthesized_strategies (feature_key, created_at DESC);

CREATE TABLE IF NOT EXISTS pattern_search_cycles (
  id BIGSERIAL PRIMARY KEY,
  cycle_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  search_issue_range_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(search_issue_range_json) = 'object'),
  budget_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(budget_json) = 'object'),
  discovered_count INTEGER NOT NULL DEFAULT 0,
  accepted_count INTEGER NOT NULL DEFAULT 0,
  result_json JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(result_json) = 'object'),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO dehps_strategies (strategy_key, name, description, config)
VALUES (
  'baseline_v1',
  'Baseline V1',
  'Keep combinations with moderate naturalness and avoid highly anomalous simple patterns.',
  '{"min_score": 0.45, "max_anomaly_penalty": 0.70}'::jsonb
)
ON CONFLICT (strategy_key) DO NOTHING;

INSERT INTO ssq_draw_sites (
  site_key, name, address, latitude, longitude, coordinate_system, accuracy_note,
  address_source_url, draw_location_source_url, effective_from_issue, effective_to_issue, is_active
)
VALUES (
  'cwl_beijing_n4ring_v0',
  'China Welfare Lottery Issuance Management Center',
  'Beijing, Chaoyang District, North 4th Ring East Road 73',
  39.990000,
  116.430000,
  'WGS84',
  'Approximate site coordinate for external physics experiments; the address is sourced, while coordinates are rounded and should not be treated as survey-grade.',
  'https://www.cwl.gov.cn/c/2020-02-01/463075.shtml',
  'https://www.thepaper.cn/newsDetail_forward_11540335',
  NULL,
  NULL,
  true
)
ON CONFLICT (site_key) DO UPDATE
SET name = EXCLUDED.name,
    address = EXCLUDED.address,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    coordinate_system = EXCLUDED.coordinate_system,
    accuracy_note = EXCLUDED.accuracy_note,
    address_source_url = EXCLUDED.address_source_url,
    draw_location_source_url = EXCLUDED.draw_location_source_url,
    effective_from_issue = EXCLUDED.effective_from_issue,
    effective_to_issue = EXCLUDED.effective_to_issue,
    is_active = EXCLUDED.is_active,
    updated_at = now();
