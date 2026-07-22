from __future__ import annotations

from copy import deepcopy
import json

import pytest

from dehps.seven_red.inner_selection import SevenRedStrategyKind
from dehps.seven_red.run_walk_forward import (
    EXPECTED_EXPERIMENT_KEY,
    RUNNER_VERSION,
    SevenRedRunnerError,
    _load_checkpoint,
    _write_checkpoint,
    _write_json,
    build_frozen_run_plan,
)


SEEDS = [
    "3373d379bea077511e8c1c24e086128effd75200796c29d4699ad65b674c2bf6",
    "4f8d713d7752fe2791beb7978ae9b2094c14cc885fff7eb4cdd99426ebc33392",
    "e08d29977707cdedc9ff7e32a59fc2ac1ff21b9fe027d29d7d76ed949c4a9543",
    "20b828e2a0f82a74d00a516d9b4a15310100b57df3aad3b28bdf84ad4e8bfe52",
    "7e16b238b9ba480d08425f61960bbdf7a080e0cd75ccebb22016e13ff8a9704e",
    "b62348c0a28e7a9be954469f3e577dd472080185598f795dae3fa18ff1cbe58a",
    "7317880af057f2f71ee8d10eb9c6269b348484a0c58be31b6f11dc3ff07a98f3",
    "75acfacc3feee99d5d105d633183980afc197dc8136f2a3f0422da9ed53b802a",
]


def frozen_config() -> dict:
    return {
        "as_of_issue": "2026083",
        "ordered_issues": {
            "inner_burn_in": ["2026004", "2026023"],
            "inner_count": 20,
            "outer_count": 60,
            "outer_targets": ["2026024", "2026083"],
        },
        "history_mode": "expanding; strictly before target",
        "score_config": {
            "type": "FrequencyRankerConfig",
            "weights": {
                "cooccurrence": 0,
                "distribution": 0,
                "frequency": 0.3,
                "matching": 0,
                "omission": 0.25,
                "omission_extreme": 0,
                "previous_consecutive": 0.05,
                "shape": 0,
                "structural": 0.4,
                "trend": 0,
            },
        },
        "legal_universe": {
            "expected_rows": 1_107_568,
            "include_hard_filter_exclusions": True,
        },
        "inner_selection": {
            "independent_family_selection": True,
            "metric_order": [
                "exact6_count",
                "red5_plus_count",
                "best_unique_matched_red_sum",
                "lower_parameter_digest",
            ],
            "window": 20,
        },
        "raw_grid": [
            {
                "parameter_id": "raw-a",
                "pool_top_n": 270,
                "seed_top_n": 50,
                "selector": "exact_raw_order",
            },
            {
                "parameter_id": "raw-b",
                "pool_top_n": 540,
                "seed_top_n": 100,
                "selector": "exact_raw_order",
            },
        ],
        "diversified_grid": [
            {
                "parameter_id": "div-a",
                "pool_top_n": 270,
                "seed_top_n": 50,
                "weights": {"coverage": 1, "edge": 1, "redundancy": 1, "score": 1},
            },
            {
                "parameter_id": "div-b",
                "pool_top_n": 540,
                "seed_top_n": 100,
                "weights": {"coverage": 1, "edge": 1, "redundancy": 1, "score": 2},
            },
        ],
        "portfolio_size": 10,
        "expanded_ticket_cost": 70,
        "random_seed_digests": list(SEEDS),
        "statistics": {
            "alpha": {"denominator": 20, "numerator": 1},
            "block_length": 5,
            "bootstrap_seed_digest": "3cb0ec5cc2e0d7dcfd94b2912bd9667d0d3ce1083ba0e8f5da926f1fd259d275",
            "confidence": {"denominator": 20, "numerator": 19},
            "minimum_effect": {"denominator": 1, "numerator": 0},
            "resamples": 10_000,
        },
        "decision_rule": (
            "Broad outperformance for a family requires all 3 comparisons: mean difference > 0; "
            "Holm adjusted p <= 1/20; bootstrap lower > 0; descriptive red5+ direction >= 0. "
            "Integrity failure invalidates; otherwise unmet criteria are unsupported/inconclusive."
        ),
    }


def issue_slice() -> tuple[str, ...]:
    return tuple(f"2026{number:03d}" for number in range(4, 84))


def test_frozen_plan_compiles_exact_protocols_and_canonical_seed_order() -> None:
    plan = build_frozen_run_plan(
        experiment_key=EXPECTED_EXPERIMENT_KEY,
        config_snapshot=frozen_config(),
        issue_slice=issue_slice(),
    )

    assert plan.issue_slice[:2] == ("2026004", "2026005")
    assert plan.outer_targets == issue_slice()[20:]
    assert plan.seed_policy.seed_digests == tuple(sorted(SEEDS))
    assert len(plan.parameter_grid.parameters) == 4
    assert sum(
        row.strategy_kind is SevenRedStrategyKind.RAW
        for row in plan.parameter_grid.parameters
    ) == 2
    assert plan.statistical_protocol.bootstrap_resample_count == 10_000
    assert len(plan.plan_digest) == 64


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda value: value.update(as_of_issue="2026082"), "as-of issue"),
        (
            lambda value: value["raw_grid"][0].update(seed_top_n=51),
            "parameter grid",
        ),
        (
            lambda value: value["statistics"].update(block_length=10),
            "statistical",
        ),
    ],
)
def test_frozen_plan_fails_closed_on_registered_contract_drift(mutator, message) -> None:
    config = deepcopy(frozen_config())
    mutator(config)

    with pytest.raises(SevenRedRunnerError, match=message):
        build_frozen_run_plan(
            experiment_key=EXPECTED_EXPERIMENT_KEY,
            config_snapshot=config,
            issue_slice=issue_slice(),
        )


def test_frozen_plan_rejects_missing_or_reordered_issue_slice() -> None:
    bad = list(issue_slice())
    bad[0], bad[1] = bad[1], bad[0]

    with pytest.raises(SevenRedRunnerError, match="exact ordered 80-issue"):
        build_frozen_run_plan(
            experiment_key=EXPECTED_EXPERIMENT_KEY,
            config_snapshot=frozen_config(),
            issue_slice=bad,
        )


def test_checkpoint_binds_runner_plan_and_exact_source_commit(tmp_path) -> None:
    plan = build_frozen_run_plan(
        experiment_key=EXPECTED_EXPERIMENT_KEY,
        config_snapshot=frozen_config(),
        issue_slice=issue_slice(),
    )
    path = tmp_path / "checkpoint.json"
    commit = "a" * 40
    _write_checkpoint(
        path,
        plan=plan,
        source_commit=commit,
        completed_issues=(),
        evaluations=(),
        trials=(),
    )

    assert _load_checkpoint(path, plan=plan, source_commit=commit) == ([], [])
    with pytest.raises(SevenRedRunnerError, match="does not bind"):
        _load_checkpoint(path, plan=plan, source_commit="b" * 40)


def test_checkpoint_rejects_noncanonical_completed_prefix(tmp_path) -> None:
    plan = build_frozen_run_plan(
        experiment_key=EXPECTED_EXPERIMENT_KEY,
        config_snapshot=frozen_config(),
        issue_slice=issue_slice(),
    )
    path = tmp_path / "checkpoint.json"
    path.write_text(
        json.dumps(
            {
                "runner_version": RUNNER_VERSION,
                "plan_digest": plan.plan_digest,
                "source_commit": "a" * 40,
                "completed_issues": ["2026005"],
                "evaluations": [],
                "trials": [],
            }
        )
    )

    with pytest.raises(SevenRedRunnerError, match="issue prefix"):
        _load_checkpoint(path, plan=plan, source_commit="a" * 40)


def test_json_writer_is_canonical_and_replaces_temporary_file(tmp_path) -> None:
    path = tmp_path / "artifact.json"
    _write_json(path, {"z": 1, "a": [2, 3]})

    assert path.read_text() == '{"a":[2,3],"z":1}\n'
    assert not path.with_suffix(".json.tmp").exists()
