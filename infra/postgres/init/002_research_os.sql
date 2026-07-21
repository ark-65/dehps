CREATE TABLE IF NOT EXISTS research_os_goal_definitions (
  goal_digest TEXT PRIMARY KEY CHECK (goal_digest ~ '^[0-9a-f]{64}$'),
  goal_key TEXT NOT NULL,
  semantic_version TEXT NOT NULL,
  objective_class TEXT NOT NULL CHECK (objective_class IN (
    'prediction_quality', 'runtime_capability', 'knowledge_quality', 'maintenance_integrity'
  )),
  owner_lane TEXT NOT NULL CHECK (owner_lane IN ('production', 'research', 'maintenance')),
  definition_json JSONB NOT NULL CHECK (jsonb_typeof(definition_json) = 'object'),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (goal_key, goal_digest)
);

CREATE INDEX IF NOT EXISTS idx_research_os_goal_definitions_key
  ON research_os_goal_definitions (goal_key, created_at, goal_digest);

CREATE TABLE IF NOT EXISTS research_os_task_definitions (
  task_digest TEXT PRIMARY KEY CHECK (task_digest ~ '^[0-9a-f]{64}$'),
  task_key TEXT NOT NULL,
  goal_digest TEXT NOT NULL REFERENCES research_os_goal_definitions(goal_digest) ON DELETE RESTRICT,
  task_type TEXT NOT NULL,
  lane TEXT NOT NULL CHECK (lane IN ('production', 'research', 'maintenance')),
  priority INTEGER NOT NULL DEFAULT 0,
  definition_json JSONB NOT NULL CHECK (jsonb_typeof(definition_json) = 'object'),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (task_key, task_digest)
);

CREATE INDEX IF NOT EXISTS idx_research_os_task_definitions_key
  ON research_os_task_definitions (task_key, created_at, task_digest);
CREATE INDEX IF NOT EXISTS idx_research_os_task_definitions_goal
  ON research_os_task_definitions (goal_digest, task_key);

CREATE TABLE IF NOT EXISTS research_os_manifests (
  manifest_digest TEXT PRIMARY KEY CHECK (manifest_digest ~ '^[0-9a-f]{64}$'),
  schema_version TEXT NOT NULL,
  manifest_json JSONB NOT NULL CHECK (jsonb_typeof(manifest_json) = 'object'),
  source TEXT NOT NULL DEFAULT 'native',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS research_os_manifest_goals (
  manifest_digest TEXT NOT NULL REFERENCES research_os_manifests(manifest_digest) ON DELETE RESTRICT,
  goal_digest TEXT NOT NULL REFERENCES research_os_goal_definitions(goal_digest) ON DELETE RESTRICT,
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  PRIMARY KEY (manifest_digest, goal_digest),
  UNIQUE (manifest_digest, ordinal)
);

CREATE TABLE IF NOT EXISTS research_os_manifest_tasks (
  manifest_digest TEXT NOT NULL REFERENCES research_os_manifests(manifest_digest) ON DELETE RESTRICT,
  task_digest TEXT NOT NULL REFERENCES research_os_task_definitions(task_digest) ON DELETE RESTRICT,
  ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
  PRIMARY KEY (manifest_digest, task_digest),
  UNIQUE (manifest_digest, ordinal)
);

CREATE TABLE IF NOT EXISTS research_os_control_planes (
  control_plane_key TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL,
  current_manifest_digest TEXT NOT NULL REFERENCES research_os_manifests(manifest_digest) ON DELETE RESTRICT,
  source TEXT NOT NULL DEFAULT 'native',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS research_os_goal_states (
  control_plane_key TEXT NOT NULL REFERENCES research_os_control_planes(control_plane_key) ON DELETE RESTRICT,
  goal_digest TEXT NOT NULL REFERENCES research_os_goal_definitions(goal_digest) ON DELETE RESTRICT,
  status TEXT NOT NULL CHECK (status IN (
    'draft', 'approved', 'active', 'suspended', 'completed', 'retired'
  )),
  retired_at TIMESTAMPTZ,
  superseded_by_goal_digest TEXT REFERENCES research_os_goal_definitions(goal_digest) ON DELETE RESTRICT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (control_plane_key, goal_digest)
);

CREATE TABLE IF NOT EXISTS research_os_task_states (
  control_plane_key TEXT NOT NULL REFERENCES research_os_control_planes(control_plane_key) ON DELETE RESTRICT,
  task_digest TEXT NOT NULL REFERENCES research_os_task_definitions(task_digest) ON DELETE RESTRICT,
  declared_status TEXT NOT NULL CHECK (declared_status IN ('draft', 'completed', 'failed', 'superseded')),
  resolved_status TEXT NOT NULL CHECK (resolved_status IN (
    'draft', 'ready', 'dependency_wait', 'external_wait', 'approval_wait',
    'completed', 'failed', 'superseded'
  )),
  reason_code TEXT NOT NULL,
  dependency_state_json JSONB NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(dependency_state_json) = 'array'),
  superseded_by_task_digest TEXT REFERENCES research_os_task_definitions(task_digest) ON DELETE RESTRICT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (control_plane_key, task_digest)
);

CREATE INDEX IF NOT EXISTS idx_research_os_task_states_status
  ON research_os_task_states (control_plane_key, resolved_status, task_digest);

CREATE TABLE IF NOT EXISTS research_os_dependency_facts (
  control_plane_key TEXT NOT NULL REFERENCES research_os_control_planes(control_plane_key) ON DELETE RESTRICT,
  fact_type TEXT NOT NULL CHECK (fact_type IN ('artifact', 'evidence', 'external_event', 'authority')),
  fact_key TEXT NOT NULL,
  fact_status TEXT NOT NULL DEFAULT 'available' CHECK (fact_status = 'available'),
  fact_json JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(fact_json) = 'object'),
  observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (control_plane_key, fact_type, fact_key)
);

CREATE TABLE IF NOT EXISTS research_os_external_executor_observations (
  observation_digest TEXT PRIMARY KEY CHECK (observation_digest ~ '^[0-9a-f]{64}$'),
  control_plane_key TEXT NOT NULL REFERENCES research_os_control_planes(control_plane_key) ON DELETE RESTRICT,
  capability TEXT NOT NULL,
  owner TEXT NOT NULL,
  status TEXT NOT NULL,
  pid INTEGER,
  observed_at TIMESTAMPTZ NOT NULL,
  observation_json JSONB NOT NULL CHECK (jsonb_typeof(observation_json) = 'object'),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_research_os_external_executor_observations_owner
  ON research_os_external_executor_observations (control_plane_key, owner, observed_at DESC);

CREATE OR REPLACE FUNCTION dehps_research_os_reject_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'Research OS immutable artifact rows cannot be updated or deleted';
END;
$$;

DROP TRIGGER IF EXISTS research_os_goal_definitions_immutable ON research_os_goal_definitions;
CREATE TRIGGER research_os_goal_definitions_immutable
BEFORE UPDATE OR DELETE ON research_os_goal_definitions
FOR EACH ROW EXECUTE FUNCTION dehps_research_os_reject_immutable_mutation();

DROP TRIGGER IF EXISTS research_os_task_definitions_immutable ON research_os_task_definitions;
CREATE TRIGGER research_os_task_definitions_immutable
BEFORE UPDATE OR DELETE ON research_os_task_definitions
FOR EACH ROW EXECUTE FUNCTION dehps_research_os_reject_immutable_mutation();

DROP TRIGGER IF EXISTS research_os_manifests_immutable ON research_os_manifests;
CREATE TRIGGER research_os_manifests_immutable
BEFORE UPDATE OR DELETE ON research_os_manifests
FOR EACH ROW EXECUTE FUNCTION dehps_research_os_reject_immutable_mutation();

DROP TRIGGER IF EXISTS research_os_manifest_goals_immutable ON research_os_manifest_goals;
CREATE TRIGGER research_os_manifest_goals_immutable
BEFORE UPDATE OR DELETE ON research_os_manifest_goals
FOR EACH ROW EXECUTE FUNCTION dehps_research_os_reject_immutable_mutation();

DROP TRIGGER IF EXISTS research_os_manifest_tasks_immutable ON research_os_manifest_tasks;
CREATE TRIGGER research_os_manifest_tasks_immutable
BEFORE UPDATE OR DELETE ON research_os_manifest_tasks
FOR EACH ROW EXECUTE FUNCTION dehps_research_os_reject_immutable_mutation();

DROP TRIGGER IF EXISTS research_os_external_executor_observations_immutable
  ON research_os_external_executor_observations;
CREATE TRIGGER research_os_external_executor_observations_immutable
BEFORE UPDATE OR DELETE ON research_os_external_executor_observations
FOR EACH ROW EXECUTE FUNCTION dehps_research_os_reject_immutable_mutation();
