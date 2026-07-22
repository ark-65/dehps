from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence

import numpy as np

from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.db import get_connection
from dehps.models.frequency_ranker import FrequencyRankerConfig, HistoryDraw
from dehps.optimization.walk_forward import (
    CONFIG_WEIGHT_FIELDS,
    build_ranked_universe,
)
from dehps.research.repository import HypothesisRepository
from dehps.research.status import ExperimentStatus, HypothesisStatus
from dehps.scoring_kernel import WeightMatrix, candidate_store_from_matrix
from dehps.scoring_kernel.full_score_artifact import FullScoreGridArtifactCompilerV1
from dehps.scoring_kernel.runtime_input import default_runtime_input_compiler
from dehps.seven_red.diversified import (
    DiversifiedSevenRedTop10Snapshot,
    SevenRedDiversificationWeights,
)
from dehps.seven_red.diversity import SevenRedDiversityAuditSnapshot
from dehps.seven_red.domain import SIX_RED_UNIVERSE, SixRedCombination
from dehps.seven_red.inner_selection import (
    SEVEN_RED_INNER_SELECTION_METRIC,
    SEVEN_RED_INNER_SELECTION_TIE_BREAK,
    SevenRedInnerSelectionProtocol,
    SevenRedInnerSelectionSnapshot,
    SevenRedParameterGrid,
    SevenRedParameterIssueEvaluation,
    SevenRedStrategyKind,
    SevenRedStrategyParameter,
)
from dehps.seven_red.portfolio import (
    EQUAL_COST_TICKET_BUDGET,
    EqualCostPortfolioSettlement,
    EqualCostSixRedPortfolio70,
    compile_diversified_equal_cost_portfolio,
    compile_raw_equal_cost_portfolio,
    compile_six_red_top70_portfolio,
)
from dehps.seven_red.random_control import (
    RandomControlCohortSettlement,
    RandomControlKind,
    RandomControlSeedPolicy,
    compile_random_control_cohort,
)
from dehps.seven_red.raw_top10 import RawSevenRedTop10Snapshot
from dehps.seven_red.scoring import (
    SevenRedScorePoolConfig,
    SixRedFullScoreVector,
    compile_seven_red_score_pool,
)
from dehps.seven_red.statistics import (
    ALL_SEED_RANDOM_MEAN,
    CIRCULAR_BLOCK_BOOTSTRAP,
    CONFIRMATORY_COMPARISONS,
    EXACT_SIGN_TEST,
    HOLM_MULTIPLICITY,
    NEAREST_RANK_PERCENTILE,
    SevenRedEndpoint,
    SevenRedStatisticalProtocol,
    SevenRedStatisticalSnapshot,
)
from dehps.seven_red.walk_forward import (
    SEVEN_RED_COMPLETE_ARM_POLICY,
    SEVEN_RED_MATCHED_RANDOM_POLICY,
    SEVEN_RED_OUTER_EVIDENCE_POLICY,
    SevenRedMatchedRandomEvidence,
    SevenRedOuterArmKind,
    SevenRedOuterRandomRowEvidence,
    SevenRedOuterStrategyArmEvidence,
    SevenRedOuterTrial,
    SevenRedWalkForwardProtocol,
    SevenRedWalkForwardSnapshot,
)
from dehps.source_version import resolve_git_commit
from dehps.storage.postgres_store import load_history_until_with_dates


RUNNER_VERSION = "seven_red_isolated_walk_forward_runner.v1"
EXPECTED_EXPERIMENT_KEY = "seven-red-compound-top10-last60-v1"
EXPECTED_HYPOTHESIS_KEY = "seven-red-compound-top10-walk-forward-v1"
EXPECTED_AS_OF_ISSUE = "2026083"
EXPECTED_FIRST_ISSUE = "2026004"
EXPECTED_FIRST_OUTER_ISSUE = "2026024"
EXPECTED_INNER_COUNT = 20
EXPECTED_OUTER_COUNT = 60
EXPECTED_SCORE_CONFIG = {
    "type": "FrequencyRankerConfig",
    "weights": {
        "structural": 0.4,
        "frequency": 0.3,
        "omission": 0.25,
        "previous_consecutive": 0.05,
        "trend": 0,
        "shape": 0,
        "matching": 0,
        "omission_extreme": 0,
        "cooccurrence": 0,
        "distribution": 0,
    },
}
EXPECTED_SEED_DIGESTS = [
    "3373d379bea077511e8c1c24e086128effd75200796c29d4699ad65b674c2bf6",
    "4f8d713d7752fe2791beb7978ae9b2094c14cc885fff7eb4cdd99426ebc33392",
    "e08d29977707cdedc9ff7e32a59fc2ac1ff21b9fe027d29d7d76ed949c4a9543",
    "20b828e2a0f82a74d00a516d9b4a15310100b57df3aad3b28bdf84ad4e8bfe52",
    "7e16b238b9ba480d08425f61960bbdf7a080e0cd75ccebb22016e13ff8a9704e",
    "b62348c0a28e7a9be954469f3e577dd472080185598f795dae3fa18ff1cbe58a",
    "7317880af057f2f71ee8d10eb9c6269b348484a0c58be31b6f11dc3ff07a98f3",
    "75acfacc3feee99d5d105d633183980afc197dc8136f2a3f0422da9ed53b802a",
]
EXPECTED_STATISTICS = {
    "alpha": {"denominator": 20, "numerator": 1},
    "minimum_effect": {"denominator": 1, "numerator": 0},
    "confidence": {"denominator": 20, "numerator": 19},
    "block_length": 5,
    "resamples": 10_000,
    "bootstrap_seed_digest": "3cb0ec5cc2e0d7dcfd94b2912bd9667d0d3ce1083ba0e8f5da926f1fd259d275",
}
EXPECTED_DECISION_RULE = (
    "Broad outperformance for a family requires all 3 comparisons: mean difference > 0; "
    "Holm adjusted p <= 1/20; bootstrap lower > 0; descriptive red5+ direction >= 0. "
    "Integrity failure invalidates; otherwise unmet criteria are unsupported/inconclusive."
)


class SevenRedRunnerError(RuntimeError):
    pass


@dataclass(frozen=True)
class FrozenRunPlan:
    experiment_key: str
    config_snapshot: dict[str, Any]
    issue_slice: tuple[str, ...]
    outer_targets: tuple[str, ...]
    parameter_grid: SevenRedParameterGrid
    inner_protocol: SevenRedInnerSelectionProtocol
    seed_policy: RandomControlSeedPolicy
    walk_forward_protocol: SevenRedWalkForwardProtocol
    statistical_protocol: SevenRedStatisticalProtocol
    plan_digest: str


@dataclass(frozen=True)
class _StrategyBundle:
    parameter: SevenRedStrategyParameter
    score_pool: Any
    strategy: Any
    portfolio: EqualCostSixRedPortfolio70


def _fail(message: str) -> None:
    raise SevenRedRunnerError(message)


def _fraction(value: Mapping[str, object], *, field: str) -> Fraction:
    try:
        return Fraction(int(value["numerator"]), int(value["denominator"]))
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise SevenRedRunnerError(f"invalid frozen fraction: {field}") from exc


def _validate_frozen_config(config: Mapping[str, Any]) -> None:
    required = {
        "as_of_issue",
        "ordered_issues",
        "history_mode",
        "score_config",
        "legal_universe",
        "inner_selection",
        "raw_grid",
        "diversified_grid",
        "portfolio_size",
        "expanded_ticket_cost",
        "random_seed_digests",
        "statistics",
        "decision_rule",
    }
    if set(config) != required:
        _fail("registered experiment config fields do not match the frozen runner contract")
    ordered = config["ordered_issues"]
    universe = config["legal_universe"]
    if config["as_of_issue"] != EXPECTED_AS_OF_ISSUE:
        _fail("as-of issue differs from the preregistered boundary")
    if ordered != {
        "inner_burn_in": [EXPECTED_FIRST_ISSUE, "2026023"],
        "outer_targets": [EXPECTED_FIRST_OUTER_ISSUE, EXPECTED_AS_OF_ISSUE],
        "inner_count": EXPECTED_INNER_COUNT,
        "outer_count": EXPECTED_OUTER_COUNT,
    }:
        _fail("ordered issue boundary differs from the preregistered 20+60 split")
    if config["history_mode"] != "expanding; strictly before target":
        _fail("history mode is not the preregistered expanding prior-only mode")
    if config["score_config"] != EXPECTED_SCORE_CONFIG:
        _fail("score configuration differs from the preregistered baseline")
    if universe != {
        "include_hard_filter_exclusions": True,
        "expected_rows": SIX_RED_UNIVERSE.cardinality,
    }:
        _fail("legal universe differs from the complete six-red universe")
    if config["portfolio_size"] != 10 or config["expanded_ticket_cost"] != 70:
        _fail("portfolio size or equal-cost ticket budget drifted")
    if config["inner_selection"] != {
        "window": 20,
        "metric_order": [
            "exact6_count",
            "red5_plus_count",
            "best_unique_matched_red_sum",
            "lower_parameter_digest",
        ],
        "independent_family_selection": True,
    }:
        _fail("inner-selection policy differs from the preregistered contract")
    if config["decision_rule"] != EXPECTED_DECISION_RULE:
        _fail("research decision rule differs from the preregistered contract")


def _parameter_grid(config: Mapping[str, Any]) -> SevenRedParameterGrid:
    raw_expected = [
        {"parameter_id": "raw-a", "seed_top_n": 50, "pool_top_n": 270, "selector": "exact_raw_order"},
        {"parameter_id": "raw-b", "seed_top_n": 100, "pool_top_n": 540, "selector": "exact_raw_order"},
    ]
    diversified_expected = [
        {
            "parameter_id": "div-a",
            "seed_top_n": 50,
            "pool_top_n": 270,
            "weights": {"score": 1, "redundancy": 1, "edge": 1, "coverage": 1},
        },
        {
            "parameter_id": "div-b",
            "seed_top_n": 100,
            "pool_top_n": 540,
            "weights": {"score": 2, "redundancy": 1, "edge": 1, "coverage": 1},
        },
    ]
    if config["raw_grid"] != raw_expected or config["diversified_grid"] != diversified_expected:
        _fail("parameter grid differs from the preregistered four rows")
    rows: list[SevenRedStrategyParameter] = []
    for item in raw_expected:
        rows.append(
            SevenRedStrategyParameter(
                strategy_kind=SevenRedStrategyKind.RAW,
                score_pool_config=SevenRedScorePoolConfig(
                    seed_top_n=item["seed_top_n"], pool_top_n=item["pool_top_n"]
                ),
                diversification_weights=None,
            )
        )
    for item in diversified_expected:
        weights = item["weights"]
        rows.append(
            SevenRedStrategyParameter(
                strategy_kind=SevenRedStrategyKind.DIVERSIFIED,
                score_pool_config=SevenRedScorePoolConfig(
                    seed_top_n=item["seed_top_n"], pool_top_n=item["pool_top_n"]
                ),
                diversification_weights=SevenRedDiversificationWeights(
                    source_quality_weight=weights["score"],
                    pair_coverage_weight=weights["redundancy"],
                    triple_coverage_weight=weights["edge"],
                    exposure_balance_weight=weights["coverage"],
                ),
            )
        )
    return SevenRedParameterGrid.build(rows)


def build_frozen_run_plan(
    *, experiment_key: str, config_snapshot: Mapping[str, Any], issue_slice: Sequence[str]
) -> FrozenRunPlan:
    if experiment_key != EXPECTED_EXPERIMENT_KEY:
        _fail("runner only accepts the approved experiment key")
    config = dict(config_snapshot)
    _validate_frozen_config(config)
    issues = tuple(issue_slice)
    if (
        len(issues) != EXPECTED_INNER_COUNT + EXPECTED_OUTER_COUNT
        or issues[0] != EXPECTED_FIRST_ISSUE
        or issues[EXPECTED_INNER_COUNT] != EXPECTED_FIRST_OUTER_ISSUE
        or issues[-1] != EXPECTED_AS_OF_ISSUE
        or tuple(sorted(set(issues), key=int)) != issues
    ):
        _fail("database does not provide the exact ordered 80-issue evaluation slice")
    grid = _parameter_grid(config)
    seed_values = config["random_seed_digests"]
    if seed_values != EXPECTED_SEED_DIGESTS:
        _fail("random seed set differs from the preregistered eight unique digests")
    seed_policy = RandomControlSeedPolicy(tuple(sorted(seed_values)))
    outer_targets = issues[EXPECTED_INNER_COUNT:]
    inner_protocol = SevenRedInnerSelectionProtocol(
        inner_window_size=EXPECTED_INNER_COUNT,
        metric_contract=SEVEN_RED_INNER_SELECTION_METRIC,
        tie_break_contract=SEVEN_RED_INNER_SELECTION_TIE_BREAK,
    )
    walk_protocol = SevenRedWalkForwardProtocol(
        outer_target_issues=outer_targets,
        seed_policy=seed_policy,
        paid_ticket_budget=EQUAL_COST_TICKET_BUDGET,
        matched_random_policy=SEVEN_RED_MATCHED_RANDOM_POLICY,
        complete_arm_policy=SEVEN_RED_COMPLETE_ARM_POLICY,
        evidence_policy=SEVEN_RED_OUTER_EVIDENCE_POLICY,
    )
    stats = config["statistics"]
    if stats != EXPECTED_STATISTICS:
        _fail("statistical settings differ from the preregistered contract")
    statistical_protocol = SevenRedStatisticalProtocol(
        walk_forward_protocol_digest=walk_protocol.protocol_digest,
        confirmatory_endpoint=SevenRedEndpoint.BEST_UNIQUE_MATCHED_RED,
        confirmatory_comparisons=CONFIRMATORY_COMPARISONS,
        alternative="greater",
        sign_test_contract=EXACT_SIGN_TEST,
        alpha=_fraction(stats["alpha"], field="alpha"),
        minimum_effect=_fraction(stats["minimum_effect"], field="minimum_effect"),
        multiplicity_contract=HOLM_MULTIPLICITY,
        random_aggregation_contract=ALL_SEED_RANDOM_MEAN,
        confidence_level=_fraction(stats["confidence"], field="confidence"),
        bootstrap_block_length=int(stats["block_length"]),
        bootstrap_resample_count=int(stats["resamples"]),
        bootstrap_seed_digest=str(stats["bootstrap_seed_digest"]),
        bootstrap_contract=CIRCULAR_BLOCK_BOOTSTRAP,
        percentile_contract=NEAREST_RANK_PERCENTILE,
    )
    plan_payload = {
        "runner_version": RUNNER_VERSION,
        "experiment_key": experiment_key,
        "config_snapshot": config,
        "issue_slice": list(issues),
        "parameter_grid_digest": grid.grid_digest,
        "inner_protocol_digest": inner_protocol.protocol_digest,
        "walk_forward_protocol_digest": walk_protocol.protocol_digest,
        "statistical_protocol_digest": statistical_protocol.protocol_digest,
    }
    return FrozenRunPlan(
        experiment_key=experiment_key,
        config_snapshot=config,
        issue_slice=issues,
        outer_targets=outer_targets,
        parameter_grid=grid,
        inner_protocol=inner_protocol,
        seed_policy=seed_policy,
        walk_forward_protocol=walk_protocol,
        statistical_protocol=statistical_protocol,
        plan_digest=canonical_digest(plan_payload, domain="dehps.seven-red.isolated-run-plan.v1"),
    )


def _assert_clean_repository() -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        _fail("repository must be clean before an isolated run")
    commit = resolve_git_commit()
    if not isinstance(commit, str) or len(commit) != 40:
        _fail("isolated run requires a full source commit")
    return commit


def _load_registry_experiment(experiment_key: str):
    repository = HypothesisRepository()
    repository.ensure_schema()
    hypothesis = repository.get_hypothesis(EXPECTED_HYPOTHESIS_KEY)
    if hypothesis.status not in {HypothesisStatus.PREREGISTERED, HypothesisStatus.RUNNING}:
        _fail("hypothesis must be preregistered or running")
    experiments = [
        row for row in repository.list_experiments(EXPECTED_HYPOTHESIS_KEY)
        if row.experiment_key == experiment_key
    ]
    if len(experiments) != 1:
        _fail("approved experiment key is missing or duplicated")
    experiment = experiments[0]
    if experiment.status not in {ExperimentStatus.PLANNED, ExperimentStatus.RUNNING}:
        _fail("experiment must be planned or running")
    return experiment


def _load_history() -> list[HistoryDraw]:
    with get_connection() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        return list(load_history_until_with_dates(conn, EXPECTED_AS_OF_ISSUE))


def _evaluation_from_dict(
    payload: Mapping[str, Any], parameters: Mapping[str, SevenRedStrategyParameter]
) -> SevenRedParameterIssueEvaluation:
    parameter = parameters.get(str(payload["parameter_digest"]))
    if parameter is None:
        _fail("checkpoint contains an unknown parameter digest")
    row = SevenRedParameterIssueEvaluation(
        parameter=parameter,
        target_issue=str(payload["target_issue"]),
        source_history_latest_issue=str(payload["source_history_latest_issue"]),
        score_pool_snapshot_digest=str(payload["score_pool_snapshot_digest"]),
        source_candidate_pool_digest=str(payload["source_candidate_pool_digest"]),
        source_strategy_artifact_digest=str(payload["source_strategy_artifact_digest"]),
        portfolio_digest=str(payload["portfolio_digest"]),
        settlement_digest=str(payload["settlement_digest"]),
        unique_ticket_hit_histogram=tuple(payload["unique_ticket_hit_histogram"]),
    )
    if row.evaluation_digest != payload.get("evaluation_digest"):
        _fail("checkpoint evaluation digest does not replay")
    return row


def _trial_from_dict(
    payload: Mapping[str, Any], seed_policy: RandomControlSeedPolicy
) -> SevenRedOuterTrial:
    arms = tuple(
        SevenRedOuterStrategyArmEvidence(
            arm_kind=SevenRedOuterArmKind(row["arm_kind"]),
            parameter_digest=row["parameter_digest"],
            source_vector_digest=row["source_vector_digest"],
            source_score_pool_snapshot_digest=row["source_score_pool_snapshot_digest"],
            source_strategy_artifact_digest=row["source_strategy_artifact_digest"],
            portfolio_digest=row["portfolio_digest"],
            settlement_digest=row["settlement_digest"],
            paid_ticket_count=row["paid_ticket_count"],
            unique_ticket_count=row["unique_ticket_count"],
            duplicate_slot_count=row["duplicate_slot_count"],
            slot_hit_histogram=tuple(row["slot_hit_histogram"]),
            unique_ticket_hit_histogram=tuple(row["unique_ticket_hit_histogram"]),
        )
        for row in payload["strategy_arms"]
    )
    matched = []
    for family in payload["matched_random_evidence"]:
        rows = tuple(
            SevenRedOuterRandomRowEvidence(
                seed_digest=row["seed_digest"],
                control_kind=RandomControlKind(row["control_kind"]),
                portfolio_digest=row["portfolio_digest"],
                settlement_row_digest=row["settlement_row_digest"],
                paid_ticket_count=row["paid_ticket_count"],
                unique_ticket_count=row["unique_ticket_count"],
                duplicate_slot_count=row["duplicate_slot_count"],
                slot_hit_histogram=tuple(row["slot_hit_histogram"]),
                unique_ticket_hit_histogram=tuple(row["unique_ticket_hit_histogram"]),
            )
            for row in family["rows"]
        )
        matched.append(
            SevenRedMatchedRandomEvidence(
                matched_family=SevenRedStrategyKind(family["matched_family"]),
                source_score_pool_snapshot_digest=family["source_score_pool_snapshot_digest"],
                seed_policy=seed_policy,
                cohort_digest=family["cohort_digest"],
                settlement_digest=family["settlement_digest"],
                rows=rows,
            )
        )
    trial = SevenRedOuterTrial(
        target_issue=payload["target_issue"],
        protocol_digest=payload["protocol_digest"],
        inner_selection_snapshot_digest=payload["inner_selection_snapshot_digest"],
        source_history_latest_issue=payload["source_history_latest_issue"],
        source_vector_digest=payload["source_vector_digest"],
        actual=SixRedCombination.from_numbers(payload["actual"]["sorted_red_numbers"]),
        strategy_arms=arms,
        matched_random_evidence=tuple(matched),
    )
    if trial.trial_digest != payload.get("trial_digest"):
        _fail("checkpoint outer-trial digest does not replay")
    return trial


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(_canonical_json(value), encoding="utf-8")
    os.replace(temporary, path)


def _load_checkpoint(
    path: Path, *, plan: FrozenRunPlan, source_commit: str
) -> tuple[list[SevenRedParameterIssueEvaluation], list[SevenRedOuterTrial]]:
    if not path.exists():
        return [], []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("runner_version") != RUNNER_VERSION
        or payload.get("plan_digest") != plan.plan_digest
        or payload.get("source_commit") != source_commit
    ):
        _fail("checkpoint does not bind the current frozen run plan")
    parameters = {row.parameter_digest: row for row in plan.parameter_grid.parameters}
    evaluations = [
        _evaluation_from_dict(row, parameters) for row in payload.get("evaluations", [])
    ]
    trials = [
        _trial_from_dict(row, plan.seed_policy) for row in payload.get("trials", [])
    ]
    completed = tuple(payload.get("completed_issues", []))
    if completed != plan.issue_slice[: len(completed)]:
        _fail("checkpoint issue prefix is not canonical")
    expected_cells = len(completed) * len(plan.parameter_grid.parameters)
    if len(evaluations) != expected_cells:
        _fail("checkpoint parameter-evaluation rectangle is incomplete")
    expected_trials = max(0, len(completed) - EXPECTED_INNER_COUNT)
    if len(trials) != expected_trials:
        _fail("checkpoint outer-trial prefix is incomplete")
    expected_cells = tuple(
        (parameter.parameter_digest, issue)
        for issue in completed
        for parameter in plan.parameter_grid.parameters
    )
    actual_cells = tuple(
        (row.parameter.parameter_digest, row.target_issue) for row in evaluations
    )
    if actual_cells != expected_cells:
        _fail("checkpoint parameter-evaluation rectangle is not canonical")
    expected_trial_targets = tuple(
        issue for issue in completed if issue in plan.outer_targets
    )
    if tuple(row.target_issue for row in trials) != expected_trial_targets or any(
        row.protocol_digest != plan.walk_forward_protocol.protocol_digest for row in trials
    ):
        _fail("checkpoint outer-trial prefix does not bind the frozen protocol")
    return evaluations, trials


def _write_checkpoint(
    path: Path,
    *,
    plan: FrozenRunPlan,
    source_commit: str,
    completed_issues: Sequence[str],
    evaluations: Sequence[SevenRedParameterIssueEvaluation],
    trials: Sequence[SevenRedOuterTrial],
) -> None:
    _write_json(
        path,
        {
            "runner_version": RUNNER_VERSION,
            "plan_digest": plan.plan_digest,
            "source_commit": source_commit,
            "completed_issues": list(completed_issues),
            "evaluations": [row.as_dict() for row in evaluations],
            "trials": [row.as_dict() for row in trials],
        },
    )


def _compile_score_vector(
    *, candidate_store: Any, history: list[HistoryDraw], target: HistoryDraw
) -> SixRedFullScoreVector:
    config = FrequencyRankerConfig()
    weights = WeightMatrix(
        np.ascontiguousarray(
            [[float(getattr(config, field)) for field in CONFIG_WEIGHT_FIELDS]],
            dtype=np.float64,
        )
    )
    chunk_size = max(1, int(os.getenv("DEHPS_SCORING_CHUNK_SIZE", "262144")))
    runtime_inputs = default_runtime_input_compiler().compile_effective_history(
        history=history,
        candidate_store=candidate_store,
        tile_size=chunk_size,
        target_draw_date=target[1] if len(target) == 3 else None,
        target_issue=target[0],
        source="seven_red_isolated_walk_forward_prior_history",
    )
    artifact = FullScoreGridArtifactCompilerV1().compile(
        verified_runtime=runtime_inputs.verified_runtime,
        weights=weights,
        code_commit=resolve_git_commit(),
    )
    return SixRedFullScoreVector.from_full_score_grid(
        artifact,
        verified_runtime=runtime_inputs.verified_runtime,
        weights=weights,
        config_index=0,
    )


def _build_strategy_bundles(
    *, plan: FrozenRunPlan, source_vector: SixRedFullScoreVector, target_issue: str
) -> dict[str, _StrategyBundle]:
    pools: dict[str, Any] = {}
    bundles: dict[str, _StrategyBundle] = {}
    for parameter in plan.parameter_grid.parameters:
        config_digest = parameter.score_pool_config.configuration_digest
        pool = pools.get(config_digest)
        if pool is None:
            pool = compile_seven_red_score_pool(
                source_vector=source_vector,
                configuration=parameter.score_pool_config,
                target_issue=target_issue,
            )
            pools[config_digest] = pool
        raw = RawSevenRedTop10Snapshot.build(pool.candidate_pool)
        if parameter.strategy_kind is SevenRedStrategyKind.RAW:
            strategy = raw
            portfolio = compile_raw_equal_cost_portfolio(score_pool=pool, raw_top10=raw)
        else:
            audit = SevenRedDiversityAuditSnapshot.build(pool.candidate_pool, raw)
            strategy = DiversifiedSevenRedTop10Snapshot.build(
                audit, parameter.diversification_weights
            )
            portfolio = compile_diversified_equal_cost_portfolio(
                score_pool=pool, diversified_top10=strategy
            )
        bundles[parameter.parameter_digest] = _StrategyBundle(
            parameter=parameter, score_pool=pool, strategy=strategy, portfolio=portfolio
        )
    return bundles


def _selected_bundle(
    snapshot: SevenRedInnerSelectionSnapshot,
    bundles: Mapping[str, _StrategyBundle],
    kind: SevenRedStrategyKind,
) -> _StrategyBundle:
    digest = snapshot.selected_parameter_digest(kind)
    try:
        return bundles[digest]
    except KeyError as exc:
        raise SevenRedRunnerError("selected parameter is absent from pre-outcome bundles") from exc


def _report(statistical: SevenRedStatisticalSnapshot) -> str:
    lines = [
        "# Seven-red isolated walk-forward numerical report",
        "",
        f"- runner: `{RUNNER_VERSION}`",
        f"- walk-forward snapshot: `{statistical.source_walk_forward.snapshot_digest}`",
        f"- statistical snapshot: `{statistical.snapshot_digest}`",
        f"- outer targets: {len(statistical.source_walk_forward.trials)}",
        "- decision: not evaluated by this Engineering/Operator artifact",
        "",
        "| comparison | wins | losses | ties | mean difference | raw p | Holm p | bootstrap interval |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in statistical.comparisons:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.comparison_id.value,
                    str(row.win_count),
                    str(row.loss_count),
                    str(row.tie_count),
                    str(row.mean_difference),
                    str(row.raw_sign_test_p_value),
                    str(row.holm_adjusted_p_value),
                    f"[{row.bootstrap_interval_lower}, {row.bootstrap_interval_upper}]",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "This report contains numerical evidence only. It makes no winner, hypothesis, betting, promotion, or production decision.",
            "",
        ]
    )
    return "\n".join(lines)


def run(*, experiment_key: str, output_dir: Path) -> dict[str, Any]:
    output = output_dir.resolve()
    allowed = (ROOT_DIR / "data/output").resolve()
    if not output.is_relative_to(allowed):
        _fail("output directory must remain under data/output")
    source_commit = _assert_clean_repository()
    experiment = _load_registry_experiment(experiment_key)
    history = _load_history()
    by_issue = {row[0]: row for row in history}
    issue_slice = tuple(row[0] for row in history[-80:])
    plan = build_frozen_run_plan(
        experiment_key=experiment.experiment_key,
        config_snapshot=experiment.config_snapshot,
        issue_slice=issue_slice,
    )
    if any(issue not in by_issue for issue in plan.issue_slice):
        _fail("evaluation issue missing from database history")
    output.mkdir(parents=True, exist_ok=True)
    _write_json(
        output / "protocol.json",
        {
            "runner_version": RUNNER_VERSION,
            "source_commit": source_commit,
            "plan_digest": plan.plan_digest,
            "experiment_config_snapshot": plan.config_snapshot,
            "parameter_grid": plan.parameter_grid.as_dict(),
            "inner_protocol": plan.inner_protocol.as_dict(),
            "walk_forward_protocol": plan.walk_forward_protocol.as_dict(),
            "statistical_protocol": plan.statistical_protocol.as_dict(),
        },
    )
    checkpoint_path = output / "checkpoint.json"
    evaluations, trials = _load_checkpoint(
        checkpoint_path, plan=plan, source_commit=source_commit
    )
    completed_count = len(evaluations) // len(plan.parameter_grid.parameters)
    completed_issues = list(plan.issue_slice[:completed_count])
    candidate_store = None
    if completed_count < len(plan.issue_slice):
        matrix = build_ranked_universe(include_hard_filter_exclusions=True)
        if len(matrix) != SIX_RED_UNIVERSE.cardinality:
            _fail("full legal six-red matrix cardinality mismatch")
        candidate_store = candidate_store_from_matrix(matrix)
    evaluation_by_cell = {
        (row.parameter.parameter_digest, row.target_issue): row for row in evaluations
    }
    history_index = {row[0]: index for index, row in enumerate(history)}
    for ordinal, issue in enumerate(plan.issue_slice[completed_count:], start=completed_count + 1):
        target = by_issue[issue]
        prior_history = history[: history_index[issue]]
        if not prior_history or int(prior_history[-1][0]) >= int(issue):
            _fail("target history is not strictly prior")
        source_vector = _compile_score_vector(
            candidate_store=candidate_store,
            history=prior_history,
            target=target,
        )
        bundles = _build_strategy_bundles(
            plan=plan, source_vector=source_vector, target_issue=issue
        )
        inner_snapshot: SevenRedInnerSelectionSnapshot | None = None
        selected: dict[SevenRedStrategyKind, _StrategyBundle] = {}
        random_cohorts: dict[SevenRedStrategyKind, Any] = {}
        six_top70: EqualCostSixRedPortfolio70 | None = None
        if issue in plan.outer_targets:
            outer_index = plan.outer_targets.index(issue)
            inner_issues = plan.issue_slice[outer_index : outer_index + EXPECTED_INNER_COUNT]
            inner_rows = [
                evaluation_by_cell[(parameter.parameter_digest, inner_issue)]
                for parameter in plan.parameter_grid.parameters
                for inner_issue in inner_issues
            ]
            inner_snapshot = SevenRedInnerSelectionSnapshot.build(
                outer_target_issue=issue,
                parameter_grid=plan.parameter_grid,
                protocol=plan.inner_protocol,
                inner_issues=inner_issues,
                evaluations=inner_rows,
            )
            selected = {
                kind: _selected_bundle(inner_snapshot, bundles, kind)
                for kind in (SevenRedStrategyKind.RAW, SevenRedStrategyKind.DIVERSIFIED)
            }
            random_cohorts = {
                kind: compile_random_control_cohort(
                    score_pool=bundle.score_pool, seed_policy=plan.seed_policy
                )
                for kind, bundle in selected.items()
            }
            six_top70 = compile_six_red_top70_portfolio(
                source_vector=source_vector, target_issue=issue
            )
        actual_numbers = target[2] if len(target) == 3 else target[1]
        current_rows: list[SevenRedParameterIssueEvaluation] = []
        settlements: dict[str, EqualCostPortfolioSettlement] = {}
        for parameter in plan.parameter_grid.parameters:
            bundle = bundles[parameter.parameter_digest]
            settlement = EqualCostPortfolioSettlement.evaluate(
                portfolio=bundle.portfolio,
                actual_issue=issue,
                actual_red_numbers=actual_numbers,
            )
            settlements[parameter.parameter_digest] = settlement
            if parameter.strategy_kind is SevenRedStrategyKind.RAW:
                row = SevenRedParameterIssueEvaluation.compile_raw(
                    parameter=parameter,
                    score_pool=bundle.score_pool,
                    portfolio=bundle.portfolio,
                    settlement=settlement,
                )
            else:
                row = SevenRedParameterIssueEvaluation.compile_diversified(
                    parameter=parameter,
                    score_pool=bundle.score_pool,
                    diversified_top10=bundle.strategy,
                    portfolio=bundle.portfolio,
                    settlement=settlement,
                )
            current_rows.append(row)
            evaluation_by_cell[(parameter.parameter_digest, issue)] = row
        evaluations.extend(current_rows)
        if inner_snapshot is not None and six_top70 is not None:
            raw_bundle = selected[SevenRedStrategyKind.RAW]
            div_bundle = selected[SevenRedStrategyKind.DIVERSIFIED]
            six_settlement = EqualCostPortfolioSettlement.evaluate(
                portfolio=six_top70,
                actual_issue=issue,
                actual_red_numbers=actual_numbers,
            )
            random_settlements = {
                kind: RandomControlCohortSettlement.evaluate(
                    cohort=cohort,
                    actual_issue=issue,
                    actual_red_numbers=actual_numbers,
                )
                for kind, cohort in random_cohorts.items()
            }
            trials.append(
                SevenRedOuterTrial.compile(
                    protocol=plan.walk_forward_protocol,
                    inner_selection=inner_snapshot,
                    raw_score_pool=raw_bundle.score_pool,
                    diversified_score_pool=div_bundle.score_pool,
                    diversified_top10=div_bundle.strategy,
                    raw_portfolio=raw_bundle.portfolio,
                    diversified_portfolio=div_bundle.portfolio,
                    six_red_top70_portfolio=six_top70,
                    raw_settlement=settlements[raw_bundle.parameter.parameter_digest],
                    diversified_settlement=settlements[div_bundle.parameter.parameter_digest],
                    six_red_top70_settlement=six_settlement,
                    raw_random_cohort=random_cohorts[SevenRedStrategyKind.RAW],
                    diversified_random_cohort=random_cohorts[SevenRedStrategyKind.DIVERSIFIED],
                    raw_random_settlement=random_settlements[SevenRedStrategyKind.RAW],
                    diversified_random_settlement=random_settlements[SevenRedStrategyKind.DIVERSIFIED],
                )
            )
        completed_issues.append(issue)
        _write_checkpoint(
            checkpoint_path,
            plan=plan,
            source_commit=source_commit,
            completed_issues=completed_issues,
            evaluations=evaluations,
            trials=trials,
        )
        print(f"[{ordinal}/80] completed issue {issue}", flush=True)
    walk_forward = SevenRedWalkForwardSnapshot.build(
        protocol=plan.walk_forward_protocol, trials=trials
    )
    statistical = SevenRedStatisticalSnapshot.compile(
        source_walk_forward=walk_forward, protocol=plan.statistical_protocol
    )
    _write_json(output / "walk_forward_snapshot.json", walk_forward.as_dict())
    _write_json(output / "statistical_snapshot.json", statistical.as_dict())
    manifest = {
        "runner_version": RUNNER_VERSION,
        "experiment_key": experiment_key,
        "source_commit": source_commit,
        "plan_digest": plan.plan_digest,
        "completed_issue_count": len(completed_issues),
        "outer_trial_count": len(trials),
        "walk_forward_snapshot_digest": walk_forward.snapshot_digest,
        "statistical_snapshot_digest": statistical.snapshot_digest,
        "generated_files": [
            "protocol.json",
            "checkpoint.json",
            "walk_forward_snapshot.json",
            "statistical_snapshot.json",
            "run_manifest.json",
            "run_report.md",
        ],
        "research_decision": None,
        "production_impact": "none",
    }
    _write_json(output / "run_manifest.json", manifest)
    (output / "run_report.md").write_text(_report(statistical), encoding="utf-8")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the preregistered seven-red walk-forward")
    parser.add_argument("--experiment-key", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args(argv)
    try:
        manifest = run(
            experiment_key=arguments.experiment_key,
            output_dir=arguments.output_dir,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(_canonical_json(manifest), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
