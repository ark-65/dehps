from pathlib import Path

from dehps.experiments.ranking_disagreement.artifacts import validate_manifest
from dehps.experiments.ranking_disagreement.executor import RankingDisagreementExecutor
from ranking_disagreement_fixtures import small_history, small_universe


def test_executor_runs_three_isolated_stages_and_keeps_forward_planned(tmp_path: Path) -> None:
    executor = RankingDisagreementExecutor(
        output_directory=tmp_path,
        history=small_history(10),
        legal_universe=small_universe(40),
        search_issue_count=3,
        frozen_issue_count=2,
        minimum_training_issues=3,
        update_registry=False,
    )

    result = executor.run_isolated(cpu_limit=2, memory_limit_gb=1.0, timeout_seconds=30)

    assert result["status"] == "completed"
    assert result["forward_validation_executed"] is False
    assert validate_manifest(tmp_path / "manifest.json")["valid"] is True
