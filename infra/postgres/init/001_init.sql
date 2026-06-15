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

INSERT INTO dehps_strategies (strategy_key, name, description, config)
VALUES (
  'baseline_v1',
  'Baseline V1',
  'Keep combinations with moderate naturalness and avoid highly anomalous simple patterns.',
  '{"min_score": 0.45, "max_anomaly_penalty": 0.70}'::jsonb
)
ON CONFLICT (strategy_key) DO NOTHING;

