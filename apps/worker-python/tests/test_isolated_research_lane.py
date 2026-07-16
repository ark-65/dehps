from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts/run_isolated_research_lane.py"
SPEC = importlib.util.spec_from_file_location("isolated_research_lane", SCRIPT_PATH)
assert SPEC and SPEC.loader
research_lane = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(research_lane)


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

    flattened = "\n".join(" ".join(command) for _, command in commands)
    assert [name for name, _ in commands] == [
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


def test_idle_optimization_suite_uses_only_existing_read_only_research_commands(tmp_path: Path) -> None:
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
        random_seeds="11,23,37",
        tasks=research_lane.DEFAULT_TASKS,
    )

    flattened = "\n".join(" ".join(command) for _, command in commands)
    assert [name for name, _ in commands] == [
        "training_diagnostics",
        "walk_forward_optimization",
        "weight_grid_search",
        "feature_family_ablation",
        "dynamic_kdj_frozen_backtest",
        "kdj_advisor_frozen_controls",
    ]
    assert "generate_training_diagnostics.py --read-only" in flattened
    assert "run_feature_ablation.py --read-only" in flattened
    assert "run_dynamic_kdj_backtest.py --read-only" in flattened
    assert "run_control_experiments.py --read-only" in flattened
    assert "run_walk_forward_optimization.py" in flattened
    assert "run_weight_grid_search.py" in flattened
    assert "run_feature_ablation.py" in flattened
    assert "run_training_supervisor.py" not in flattened
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

    assert "does not run the training supervisor" in report
    assert "cannot change line selection" not in report


def test_research_contract_changes_for_parameter_code_and_seed(monkeypatch) -> None:
    args = research_lane.build_parser().parse_args(
        ["--as-of-issue", "2026080", "--train-window", "900", "--random-seeds", "11,23,37"]
    )
    monkeypatch.setattr(research_lane, "resolve_git_commit", lambda _root: "commit-a")
    first = research_lane.build_training_contract(
        args=args,
        history_fingerprint_value="history-a",
    )

    changed_args = research_lane.build_parser().parse_args(
        ["--as-of-issue", "2026080", "--train-window", "700", "--random-seeds", "13,29,41"]
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
    assert first.payload["history_max_issue"] == "2026080"
    assert first.payload["code_commit"] == "commit-a"
    assert first.payload["seed"] == 11
    assert first.config_hash != changed.config_hash
