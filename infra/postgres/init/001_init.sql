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
