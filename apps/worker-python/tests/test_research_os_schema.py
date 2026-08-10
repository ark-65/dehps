from pathlib import Path

from dehps.storage.postgres_store import ensure_research_os_schema


class RecordingConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, sql: str) -> None:
        self.statements.append(sql)


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


def test_research_os_schema_loader_replays_the_same_idempotent_migration() -> None:
    connection = RecordingConnection()

    ensure_research_os_schema(connection)  # type: ignore[arg-type]
    ensure_research_os_schema(connection)  # type: ignore[arg-type]

    assert len(connection.statements) == 2
    assert connection.statements[0] == connection.statements[1]
    assert connection.statements[0].startswith("CREATE TABLE IF NOT EXISTS research_os_goal_definitions")
