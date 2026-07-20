from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts/run_isolated_research_lane.py"
SPEC = importlib.util.spec_from_file_location("isolated_research_lane", SCRIPT_PATH)
assert SPEC and SPEC.loader
research_lane = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(research_lane)


def test_clean_worktree_preflight_accepts_an_empty_porcelain_status(monkeypatch) -> None:
    monkeypatch.setattr(
        research_lane.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=""),
    )

    research_lane.require_clean_worktree(Path("/repo"))


def test_clean_worktree_preflight_fails_closed_on_source_changes(monkeypatch) -> None:
    monkeypatch.setattr(
        research_lane.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout=" M scripts/run_isolated_research_lane.py\n?? new_feature.py\n"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="research_requires_clean_worktree:change_count=2",
    ):
        research_lane.require_clean_worktree(Path("/repo"))


def test_clean_worktree_preflight_fails_closed_when_git_status_errors(monkeypatch) -> None:
    def fail(*_args, **_kwargs):
        raise subprocess.CalledProcessError(128, ["git", "status"])

    monkeypatch.setattr(research_lane.subprocess, "run", fail)

    with pytest.raises(RuntimeError, match="research_worktree_status_unavailable"):
        research_lane.require_clean_worktree(Path("/repo"))


def test_completed_manifest_is_reused_only_for_the_identical_training_fingerprint() -> None:
    manifest = {
        "status": "completed",
        "lane_key": research_lane.LANE_KEY,
        "suite_version": research_lane.SUITE_VERSION,
        "as_of_issue": "2026079",
        "history_fingerprint": "history-a",
        "training_fingerprint": "training-a",
    }

    assert research_lane.manifest_matches(
        manifest,
        training_fingerprint="training-a",
    )
    assert not research_lane.manifest_matches(
        manifest,
        training_fingerprint="training-b",
    )


def test_each_training_fingerprint_has_a_stable_manifest_path(tmp_path: Path) -> None:
    first = research_lane.fingerprint_manifest_path(tmp_path, "fingerprint-a")
    second = research_lane.fingerprint_manifest_path(tmp_path, "fingerprint-b")

    assert first != second
    assert first.name == "isolated-research-lane-fingerprint-a.json"


def test_fixed_research_suite_cannot_invoke_or_write_the_main_supervisor(tmp_path: Path) -> None:
    commands = research_lane.research_commands(
        as_of_issue="2026079",
        workers=8,
        output_dir=tmp_path,
        train_mode="rolling",
        train_window=600,
        eval_window=80,
        top_n=5000,
        history_scope="current_regime_default",
        regime_years=8,
        random_seeds="7,19,31",
        tasks=("dynamic-kdj", "frozen-controls"),
    )

    flattened = "\n".join(" ".join(command) for _, _, command in commands)
    assert [task for task, _, _ in commands] == ["dynamic-kdj", "frozen-controls"]
    assert [name for _, name, _ in commands] == [
        "dynamic_kdj_frozen_backtest",
        "kdj_advisor_frozen_controls",
    ]
    assert "run_training_supervisor.py" not in flattened
    assert "generate_training_next_candidates.py" not in flattened
    assert "--as-of-issue 2026079" in flattened
    assert "--train-mode rolling" in flattened
    assert "--train-window 600" in flattened
    assert "--random-seeds 7,19,31" in flattened
    assert str(tmp_path) in flattened


def test_idle_optimization_suite_prioritizes_guardrails_then_adaptive_success_training(tmp_path: Path) -> None:
    commands = research_lane.research_commands(
        as_of_issue="2026080",
        workers=16,
        output_dir=tmp_path,
        train_mode="expanding",
        train_window=900,
        eval_window=100,
        top_n=10000,
        history_scope="current_regime_default",
        regime_years=10,
        random_seeds=None,
        tasks=research_lane.DEFAULT_TASKS,
    )

    flattened = "\n".join(" ".join(command) for _, _, command in commands)
    assert [task for task, _, _ in commands] == list(research_lane.DEFAULT_TASKS)
    assert [name for _, name, _ in commands] == [
        "training_diagnostics",
        "analytic_null_baseline",
        "adaptive_success_training",
    ]
    assert "generate_training_diagnostics.py --read-only" in flattened
    assert "generate_analytic_null_baseline.py" in flattened
    assert "--random-seeds" not in flattened
    assert "run_training_supervisor.py --observability-only --max-rounds 512" in flattened
    assert "--eval-window 100" in flattened
    assert "--enable-weight-kdj-advisor" in flattened
    assert "--enable-ridge-kdj-advisor" in flattened
    assert "--enable-neural-kdj-advisor" not in flattened
    assert "generate_training_next_candidates.py" not in flattened


def test_report_states_the_main_line_boundary() -> None:
    report = research_lane.render_report(
        {
            "status": "completed",
            "as_of_issue": "2026079",
            "suite_version": research_lane.SUITE_VERSION,
            "history_fingerprint": "history-a",
            "runs": [],
        }
    )

    assert "observability-only policy" in report
    assert "local research champion" in report


def test_deterministic_research_contract_changes_for_parameter_and_code_not_seed(monkeypatch) -> None:
    args = research_lane.build_parser().parse_args(
        ["--as-of-issue", "2026080", "--train-window", "900"]
    )
    monkeypatch.setattr(research_lane, "resolve_git_commit", lambda _root: "commit-a")
    first = research_lane.build_training_contract(
        args=args,
        history_fingerprint_value="history-a",
    )

    changed_args = research_lane.build_parser().parse_args(
        ["--as-of-issue", "2026080", "--train-window", "700"]
    )
    changed = research_lane.build_training_contract(
        args=changed_args,
        history_fingerprint_value="history-a",
    )
    monkeypatch.setattr(research_lane, "resolve_git_commit", lambda _root: "commit-b")
    code_changed = research_lane.build_training_contract(
        args=args,
        history_fingerprint_value="history-a",
    )

    assert first.value != changed.value
    assert first.value != code_changed.value
    assert first.payload["training_mode"] == "research"
    assert first.config_hash != changed.config_hash
    assert "seed" not in first.payload
    assert "random_seeds" not in first.payload
    assert all(task.spec.execution_mode == "deterministic" for task in first.tasks)
    assert all("seed" not in task.payload for task in first.tasks)
    contracts = {task.spec.task_type: task.spec.ranking_contract for task in first.tasks}
    assert contracts == {
        "training-diagnostics": None,
        "analytic-null-baseline": None,
        "adaptive-success-training": "strict_v1",
    }


def test_adaptive_continuation_fingerprint_uses_semantic_search_state(tmp_path: Path) -> None:
    task_dir = tmp_path / "adaptive-success-training"
    task_dir.mkdir(parents=True)
    status_path = task_dir / "training-supervisor-one.json"
    status_path.write_text(
        """{
          "execution_mode": "observability_only",
          "train_mode": "expanding",
          "train_window": 900,
          "eval_window": 100,
          "top_n": 10000,
          "search_base": {"config_hash": "search-a"},
          "research_learning": {"champion": {"config_hash": "champion-a"}},
          "research_candidate_state": {
            "candidates": [
              {"as_of_issue": "2026082", "config_hash": "champion-a"},
              {"as_of_issue": "2026082", "config_hash": "candidate-a"}
            ]
          }
        }""",
        encoding="utf-8",
    )

    first = research_lane.adaptive_continuation_snapshot(
        tmp_path,
        as_of_issue="2026082",
        train_mode="expanding",
        train_window=900,
        eval_window=100,
        top_n=10000,
    )
    status_path.write_text(status_path.read_text(encoding="utf-8").replace("candidate-a", "candidate-b"), encoding="utf-8")
    second = research_lane.adaptive_continuation_snapshot(
        tmp_path,
        as_of_issue="2026082",
        train_mode="expanding",
        train_window=900,
        eval_window=100,
        top_n=10000,
    )

    assert first["evaluated_config_count"] == 2
    assert first["semantic_state_digest"] != second["semantic_state_digest"]


def test_deterministic_suite_rejects_seed_only_reruns(monkeypatch) -> None:
    args = research_lane.build_parser().parse_args(
        ["--as-of-issue", "2026080", "--random-seeds", "11"]
    )
    monkeypatch.setattr(research_lane, "resolve_git_commit", lambda _root: "commit-a")

    with pytest.raises(ValueError, match="deterministic research suite does not accept"):
        research_lane.build_training_contract(args=args, history_fingerprint_value="history-a")


def test_task_config_projection_prevents_random_config_pollution() -> None:
    full_config = {
        "profile_key": "default",
        "train_mode": "expanding",
        "train_window": 900,
        "eval_window": 100,
        "top_n": 10000,
        "history_scope": "current_regime_default",
        "regime_years": 10,
        "random_algorithm_version": "rng-v1",
        "sampling_method": "uniform",
        "monte_carlo_trials": 100,
        "random_seeds": [11, 23, 37],
    }

    deterministic = research_lane.project_config_for_task(full_config, task_type="weight-grid")
    stochastic = research_lane.project_config_for_task(full_config, task_type="frozen-controls")

    assert "random_seeds" not in deterministic
    assert "monte_carlo_trials" not in deterministic
    assert stochastic["monte_carlo_trials"] == 100


def test_stochastic_task_has_experiment_and_replicate_fingerprints(monkeypatch) -> None:
    args = research_lane.build_parser().parse_args(
        [
            "--as-of-issue",
            "2026080",
            "--tasks",
            "frozen-controls",
            "--random-seeds",
            "37,11,23,11",
        ]
    )
    monkeypatch.setattr(research_lane, "resolve_git_commit", lambda _root: "commit-a")
    contract = research_lane.build_training_contract(args=args, history_fingerprint_value="history-a")
    task = contract.tasks[0]

    assert task.spec.execution_mode == "stochastic"
    assert task.spec.seed_policy is not None
    assert task.spec.seed_policy.seeds == (11, 23, 37)
    assert task.spec.seed_policy.selection_policy == "no_best_seed"
    assert task.run_fingerprint(11) != task.run_fingerprint(23)
    assert task.experiment_fingerprint == contract.payload["task_experiment_fingerprints"][0]["experiment_fingerprint"]


def test_stochastic_task_rejects_missing_seed_policy(monkeypatch) -> None:
    args = research_lane.build_parser().parse_args(
        ["--as-of-issue", "2026080", "--tasks", "frozen-controls"]
    )
    monkeypatch.setattr(research_lane, "resolve_git_commit", lambda _root: "commit-a")

    with pytest.raises(ValueError, match="explicit seed policy"):
        research_lane.build_training_contract(args=args, history_fingerprint_value="history-a")
