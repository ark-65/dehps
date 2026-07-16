from __future__ import annotations

import ast
from pathlib import Path

import pytest

from dehps.training.research_fingerprint import (
    ResearchTaskFingerprint,
    ResearchTaskSpec,
    SeedPolicy,
)
from scripts.generate_analytic_null_baseline import build_analytic_null_baseline
from scripts import generate_next_candidates as next_candidates_script


WORKER_ROOT = Path(__file__).resolve().parents[1]


def task_fingerprint(spec: ResearchTaskSpec) -> ResearchTaskFingerprint:
    return ResearchTaskFingerprint(
        history_max_issue="2026080",
        history_fingerprint="history-a",
        training_mode="research",
        model_version="model-v1",
        feature_version="features-v1",
        candidate_algorithm_version="candidate-v1",
        code_commit="commit-a",
        spec=spec,
    )


def test_deterministic_task_rejects_seed_policy_and_random_config() -> None:
    policy = SeedPolicy(seeds=(11, 23, 37))
    with pytest.raises(ValueError, match="cannot declare a seed policy"):
        ResearchTaskSpec(
            task_type="walk-forward",
            execution_mode="deterministic",
            config={"eval_window": 100},
            evaluation_contract="fixed-walk-forward-v1",
            seed_policy=policy,
        )
    with pytest.raises(ValueError, match="contains random fields"):
        ResearchTaskSpec(
            task_type="weight-grid",
            execution_mode="deterministic",
            config={"eval_window": 100, "random_seeds": [11]},
            evaluation_contract="complete-grid-v1",
        )


def test_deterministic_task_identity_contains_no_random_fields() -> None:
    task = task_fingerprint(
        ResearchTaskSpec(
            task_type="weight-grid",
            execution_mode="deterministic",
            config={"eval_window": 100, "top_n": 10000},
            evaluation_contract="complete-grid-v1",
        )
    )

    assert "seed" not in task.payload
    assert "seed_policy" not in task.payload
    assert task.run_fingerprint() == task.experiment_fingerprint
    with pytest.raises(ValueError, match="does not accept a seed"):
        task.run_fingerprint(11)


def test_stochastic_experiment_and_replicate_identity_are_separate() -> None:
    first = task_fingerprint(
        ResearchTaskSpec(
            task_type="monte-carlo-controls",
            execution_mode="stochastic",
            config={"sampling_method": "uniform_rank", "trials": 100},
            evaluation_contract="monte-carlo-controls-v1",
            seed_policy=SeedPolicy(seeds=(37, 11, 23, 11)),
        )
    )
    repeated = task_fingerprint(
        ResearchTaskSpec(
            task_type="monte-carlo-controls",
            execution_mode="stochastic",
            config={"sampling_method": "uniform_rank", "trials": 100},
            evaluation_contract="monte-carlo-controls-v1",
            seed_policy=SeedPolicy(seeds=(11, 23, 37)),
        )
    )
    expanded = task_fingerprint(
        ResearchTaskSpec(
            task_type="monte-carlo-controls",
            execution_mode="stochastic",
            config={"sampling_method": "uniform_rank", "trials": 100},
            evaluation_contract="monte-carlo-controls-v1",
            seed_policy=SeedPolicy(seeds=(11, 23, 37, 41)),
        )
    )

    assert first.experiment_fingerprint == repeated.experiment_fingerprint
    assert first.experiment_fingerprint != expanded.experiment_fingerprint
    assert first.run_fingerprint(11) != first.run_fingerprint(23)
    assert first.run_fingerprint(11) == repeated.run_fingerprint(11)
    with pytest.raises(ValueError, match="outside the experiment seed policy"):
        first.run_fingerprint(41)


def test_seed_policy_forbids_best_seed_selection() -> None:
    with pytest.raises(ValueError, match="forbids best-seed selection"):
        SeedPolicy(seeds=(11,), selection_policy="best_seed_only")  # type: ignore[arg-type]


def test_analytic_null_baseline_is_seed_free_and_reproducible() -> None:
    arguments = {
        "as_of_issue": "2026080",
        "history_fingerprint_value": "history-a",
        "history_length": 1200,
        "train_mode": "expanding",
        "train_window": 900,
        "eval_window": 100,
        "top_n": 10000,
        "history_scope": "current_regime_default",
        "regime_years": 10,
    }

    first = build_analytic_null_baseline(**arguments)
    second = build_analytic_null_baseline(**arguments)

    assert first == second
    assert first["execution_mode"] == "deterministic"
    assert first["seed"] is None
    assert first["random_sampling_performed"] is False


def test_candidate_generation_never_falls_back_to_a_system_time_seed(monkeypatch) -> None:
    class ConnectionContext:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(next_candidates_script, "get_connection", ConnectionContext)
    monkeypatch.setattr(next_candidates_script, "load_history", lambda _conn: [])
    monkeypatch.setattr(next_candidates_script, "latest_draw", lambda _conn: None)

    with pytest.raises(ValueError, match="requires an explicit seed"):
        next_candidates_script.generate_next_candidates(limit=1, random_sets=1)


def test_all_runtime_rng_constructors_have_explicit_seeds() -> None:
    violations: list[str] = []
    source_roots = (WORKER_ROOT / "dehps", WORKER_ROOT / "scripts")
    for source_root in source_roots:
        for path in source_root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                call_name = ""
                if isinstance(node.func, ast.Name):
                    call_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    call_name = node.func.attr
                if call_name not in {"Random", "default_rng"}:
                    continue
                has_keyword_seed = any(keyword.arg == "seed" for keyword in node.keywords)
                positional_seed = node.args[0] if node.args else None
                if (
                    positional_seed is None
                    and not has_keyword_seed
                    or isinstance(positional_seed, ast.Constant)
                    and positional_seed.value is None
                ):
                    violations.append(f"{path.relative_to(WORKER_ROOT)}:{node.lineno}:{call_name}")
    assert violations == []


def test_runtime_never_derives_seed_variables_from_system_time() -> None:
    violations: list[str] = []
    source_roots = (WORKER_ROOT / "dehps", WORKER_ROOT / "scripts")
    time_call_names = {"now", "today", "time", "time_ns", "utcnow"}
    for source_root in source_roots:
        for path in source_root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                target_names = {
                    target.id
                    for target in targets
                    if isinstance(target, ast.Name)
                }
                if not any("seed" in name.lower() for name in target_names):
                    continue
                value = node.value
                if value is None:
                    continue
                for child in ast.walk(value):
                    if not isinstance(child, ast.Call):
                        continue
                    name = child.func.attr if isinstance(child.func, ast.Attribute) else (
                        child.func.id if isinstance(child.func, ast.Name) else ""
                    )
                    if name in time_call_names:
                        violations.append(f"{path.relative_to(WORKER_ROOT)}:{node.lineno}:{name}")
    assert violations == []
