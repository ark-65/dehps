from pathlib import Path

from dehps.storage.postgres_store import ensure_research_os_schema


class RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.marker_exists = False
        self.digest = None
        self.row = None

    def cursor(self, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql: str, params=()):
        self.statements.append(sql)
        if sql.startswith("SELECT to_regclass"):
            self.row = ("dehps_schema_applications" if self.marker_exists else None,)
        elif sql.startswith("SELECT schema_digest"):
            self.row = (self.digest,) if self.digest else None
        elif sql.startswith("CREATE TABLE IF NOT EXISTS dehps_schema_applications"):
            self.marker_exists = True
        elif sql.startswith("INSERT INTO dehps_schema_applications"):
            self.digest = params[1]
        return self

    def fetchone(self):
        return self.row


def test_research_os_migration_is_additive_idempotent_and_immutable() -> None:
    sql = (Path(__file__).resolve().parents[3] / "infra/postgres/init/002_research_os.sql").read_text()

    for table in (
        "research_os_goal_definitions",
        "research_os_task_definitions",
        "research_os_manifests",
        "research_os_manifest_goals",
        "research_os_manifest_tasks",
        "research_os_control_planes",
        "research_os_goal_states",
        "research_os_task_states",
        "research_os_dependency_facts",
        "research_os_external_executor_observations",
        "research_os_mainline_execution_events",
        "research_os_mainline_artifacts",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
    assert "Research OS immutable artifact rows cannot be updated or deleted" in sql
    assert "ON DELETE RESTRICT" in sql
    assert "research_scheduler_queue" not in sql
    assert "training_round_results" not in sql
    assert "UPDATE research_" not in sql
    expected_objective_classes = (
        "prediction_quality",
        "structural_decision_utility",
        "runtime_capability",
        "knowledge_quality",
        "maintenance_integrity",
    )
    create_constraint = sql.split(
        "ALTER TABLE research_os_goal_definitions", 1
    )[0]
    replay_constraint = sql.split(
        "ALTER TABLE research_os_goal_definitions", 1
    )[1].split("CREATE INDEX", 1)[0]
    for objective_class in expected_objective_classes:
        assert f"'{objective_class}'" in create_constraint
        assert f"'{objective_class}'" in replay_constraint
    assert (
        "DROP CONSTRAINT IF EXISTS "
        "research_os_goal_definitions_objective_class_check"
    ) in replay_constraint
    assert (
        "ADD CONSTRAINT research_os_goal_definitions_objective_class_check"
    ) in replay_constraint


def test_research_os_schema_loader_skips_ddl_after_committed_digest() -> None:
    connection = RecordingConnection()

    ensure_research_os_schema(connection)  # type: ignore[arg-type]
    first_count = len(connection.statements)
    ensure_research_os_schema(connection)  # type: ignore[arg-type]

    assert len(connection.statements) == first_count + 2
    assert all(s.startswith("SELECT") for s in connection.statements[first_count:])
    assert sum(s.startswith("CREATE TABLE IF NOT EXISTS research_os_goal_definitions")
               for s in connection.statements) == 1


def test_changed_schema_digest_requires_reapplication() -> None:
    connection = RecordingConnection()
    ensure_research_os_schema(connection)
    connection.digest = "old"
    ensure_research_os_schema(connection)
    assert sum(s.startswith("CREATE TABLE IF NOT EXISTS research_os_goal_definitions")
               for s in connection.statements) == 2
