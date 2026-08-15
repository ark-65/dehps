from __future__ import annotations

import copy
import hashlib
import itertools
import json
import shutil
from dataclasses import asdict
from pathlib import Path

import dehps.research_os.information_theory.measurement_system_v2.prediction_v2_structural_portfolio_execution as execution_module
import numpy as np
import pytest
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_historical_gate import (
    MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT,
    MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_forward_evidence_or_pivot_planner import (
    PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_COMPLETION_FACT,
    PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_promotion_planner import (
    PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT,
    PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_structural_decision_support_design import (
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_COMPLETION_FACT,
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_structural_decision_support_preregistration import (
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_COMPLETION_FACT,
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_structural_portfolio_execution import (
    NULL_ROOT_SEED_HEX,
    OPTIMIZER_ROOT_SEED_HEX,
    PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY,
    PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_CAPABILITY,
    PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_COMPLETION_FACT,
    PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY,
    UPSTREAM_EXECUTION_CONTRACT_DIGEST,
    UPSTREAM_EXECUTION_HANDOFF_DIGEST,
    UPSTREAM_PREREGISTRATION_COMPLETION_DIGEST,
    UPSTREAM_PREREGISTRATION_DIGEST,
    UPSTREAM_PREREGISTRATION_EXECUTION_DIGEST,
    CounterRng,
    ExecutionSettings,
    StructuralPortfolioExecutionRun,
    StructuralStats,
    build_universe_tables,
    execute_structural_portfolio_program,
    load_prediction_v2_structural_portfolio_execution_source_contract,
    replay_structural_portfolio_artifacts,
    run_reference_preflight,
    strictly_dominates,
    structural_stats,
    verify_prediction_v2_structural_portfolio_execution_source_bytes,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    PredictionV2StructuralPortfolioExecutionCapability,
    ResearchEvidenceSupervisor,
)

MANIFEST_PATH = ROOT_DIR / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)


def _test_source() -> dict[str, object]:
    return {
        "artifact_digest": "test-source-contract",
        "source_set_digest": "test-source-set",
        "test_mode_allowed": True,
    }


def _upstream() -> dict[str, dict[str, object]]:
    return {
        "preregistration_execution": {
            "artifact_digest": UPSTREAM_PREREGISTRATION_EXECUTION_DIGEST
        },
        "preregistration": {
            "artifact_digest": UPSTREAM_PREREGISTRATION_DIGEST,
            "execution_contract_digest": UPSTREAM_EXECUTION_CONTRACT_DIGEST,
        },
        "execution_handoff": {"artifact_digest": UPSTREAM_EXECUTION_HANDOFF_DIGEST},
        "preregistration_completion": {
            "artifact_digest": UPSTREAM_PREREGISTRATION_COMPLETION_DIGEST
        },
    }


def _settings(**overrides: int) -> ExecutionSettings:
    values = {
        "candidate_budget": 12,
        "island_count": 2,
        "proposals_per_island": 128,
        "null_replicate_count": 32,
        "null_shard_size": 8,
        "parallel_workers": 2,
        "reference_preflight_proposals": 16,
        "checkpoint_boundary_proposals": 32,
        "optimizer_wall_clock_limit_seconds": 60,
        "null_wall_clock_limit_seconds": 60,
        "resident_memory_limit_bytes": 2_147_483_648,
    }
    values.update(overrides)
    return ExecutionSettings(**values)


def _run(tmp_path: Path, settings: ExecutionSettings | None = None):
    return execute_structural_portfolio_program(
        source_contract=_test_source(),
        checkpoint_dir=tmp_path,
        settings=settings or _settings(),
        **_upstream(),
    )


def _recursive_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(
            *(_recursive_keys(item) for item in value.values()), set()
        )
    if isinstance(value, list):
        return set().union(*(_recursive_keys(item) for item in value), set())
    return set()


def test_source_contract_binds_frozen_execution_source() -> None:
    contract = load_prediction_v2_structural_portfolio_execution_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_structural_portfolio_execution_source_bytes(
        root_dir=ROOT_DIR, contract=contract
    )


def test_universe_tables_exhaustively_match_lexicographic_combinations() -> None:
    tables = build_universe_tables()
    assert tables.numbers.shape == (1_107_568, 6)
    assert tables.masks.shape == (1_107_568,)
    assert tables.pairs.shape == (1_107_568, 15)
    assert tables.resident_bytes == 48_732_992
    digest = hashlib.sha256()
    for rank, combination in enumerate(itertools.combinations(range(1, 34), 6)):
        observed = tuple(int(item) for item in tables.numbers[rank])
        assert observed == combination
        digest.update(bytes(observed))
    assert rank == 1_107_567
    assert (
        digest.hexdigest()
        == "422dbfff86c51708368f2bb5fe84523e6ac939f719f3731881970999e96277ba"
    )


def test_counter_rng_has_frozen_golden_vectors_and_restores() -> None:
    optimizer = CounterRng.from_root(OPTIMIZER_ROOT_SEED_HEX, "island", 0)
    observed = [optimizer.bounded(bound) for bound in (176, 1_107_392, 33, 528)]
    assert observed == [172, 197965, 29, 75]
    snapshot = optimizer.snapshot()
    restored = CounterRng.restore(optimizer.seed, snapshot)
    assert [optimizer.bounded(10_003) for _ in range(12)] == [
        restored.bounded(10_003) for _ in range(12)
    ]
    null = CounterRng.from_root(NULL_ROOT_SEED_HEX, "replicate", 4095)
    assert [null.bounded(1_107_568 - index) for index in range(4)] == [
        286249,
        767889,
        129195,
        827144,
    ]


def test_exact_stats_obey_distance_identity_and_scalar_preflight() -> None:
    tables = build_universe_tables()
    ranks = np.asarray([0, 1, 42, 999, 100_000, 1_107_567], dtype=np.uint32)
    stats, singleton_counts, pair_counts, histogram = structural_stats(ranks, tables)
    assert int(singleton_counts.sum()) == 36
    assert int(pair_counts.sum()) == 90
    assert int(histogram.sum()) == 15
    assert stats.sum_pairwise_replacement_distance == (
        6 * 15 - (stats.singleton_square_sum - 36) // 2
    )
    preflight = run_reference_preflight(tables=tables, proposal_count=32)
    assert preflight["status"] == "PASS"
    assert preflight["proposal_count"] == 32


def test_dominance_is_exact_and_rejects_tradeoffs() -> None:
    reference = StructuralStats(100, 200, 2, 500)
    assert strictly_dominates(StructuralStats(99, 200, 2, 500), reference)
    assert not strictly_dominates(reference, reference)
    assert not strictly_dominates(StructuralStats(99, 201, 2, 500), reference)
    assert not strictly_dominates(StructuralStats(100, 200, 1, 501), reference)


def test_tiny_execution_directly_skips_completed_children_with_same_identity(
    tmp_path: Path,
) -> None:
    first = _run(tmp_path)
    second = _run(tmp_path)
    assert [item["artifact_digest"] for item in first.artifacts] == [
        item["artifact_digest"] for item in second.artifacts
    ]
    assert first.completion["optimizer_proposals_executed"] == 256
    assert first.completion["null_replicates_executed"] == 32
    assert first.optimizer_index["checkpoint_resume_policy"].startswith("MATCHING")
    assert first.null_comparison["checkpoint_resume_policy"].startswith("MATCHING")
    replay = replay_structural_portfolio_artifacts(
        portfolio=first.portfolio,
        optimizer_index=first.optimizer_index,
        null_comparison=first.null_comparison,
        completion=first.completion,
    )
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["workload_rerun"] is False
    forbidden = {
        "duplicate_validation",
        "duplicate_check",
        "uniqueness_validation",
    }
    assert not forbidden.intersection(_recursive_keys([*first.artifacts, replay]))


def test_partial_island_resume_matches_uninterrupted_result(tmp_path: Path) -> None:
    tables = build_universe_tables()
    execution_module._WORKER_TABLES = tables
    settings = _settings(
        island_count=1,
        proposals_per_island=32,
        null_replicate_count=1,
        null_shard_size=1,
        parallel_workers=1,
        checkpoint_boundary_proposals=16,
    )
    identity = execution_module._child_identity(
        source_set_digest="test-source-set",
        kind="island",
        index=0,
        settings=settings,
    )
    interrupted_dir = tmp_path / "interrupted"
    partial_path, _ = execution_module._island_paths(interrupted_dir, identity)
    rng = CounterRng.from_root(OPTIMIZER_ROOT_SEED_HEX, "island", 0)
    permutation = execution_module._initialize_permutation_kernel(
        execution_module._initialization_draws(rng, settings.candidate_budget)
    )
    singleton_counts, pair_counts, histogram, stats = (
        execution_module._state_from_permutation(
            permutation, settings.candidate_budget, tables
        )
    )
    selected, suffix = execution_module._proposal_draws(
        rng, 16, settings.candidate_budget
    )
    block = execution_module._run_proposal_block_kernel(
        permutation,
        singleton_counts,
        pair_counts,
        histogram,
        stats.singleton_square_sum,
        stats.pair_square_sum,
        stats.minimum_replacement_distance,
        stats.sum_pairwise_replacement_distance,
        selected,
        suffix,
        tables.numbers,
        tables.masks,
        tables.pairs,
        settings.candidate_budget,
    )
    stats = execution_module._stats_tuple(*block[1:])
    execution_module._save_partial_island(
        partial_path,
        identity=identity,
        permutation=permutation,
        singleton_counts=singleton_counts,
        pair_counts=pair_counts,
        distance_histogram=histogram,
        stats=stats,
        rng=rng,
        proposal_index=16,
        accepted_move_count=int(block[0]),
    )
    resumed = execution_module._run_island_child(
        (0, identity, str(interrupted_dir), settings)
    )
    uninterrupted = execution_module._run_island_child(
        (0, identity, str(tmp_path / "uninterrupted"), settings)
    )
    for key in (
        "child_identity",
        "proposals_executed",
        "accepted_move_count",
        "selected_ranks",
        "stats",
        "rng_final",
    ):
        assert resumed[key] == uninterrupted[key]
    assert resumed["resumed_from_proposal"] == 16
    assert uninterrupted["resumed_from_proposal"] == 0


def test_upstream_and_replay_identity_drift_fail_closed(tmp_path: Path) -> None:
    upstream = _upstream()
    upstream["preregistration"]["artifact_digest"] = "changed"
    with pytest.raises(
        execution_module.PredictionV2StructuralPortfolioExecutionError,
        match="upstream_identity_changed",
    ):
        execute_structural_portfolio_program(
            source_contract=_test_source(),
            checkpoint_dir=tmp_path,
            settings=_settings(),
            **upstream,
        )
    run = _run(tmp_path / "valid")
    changed = json.loads(json.dumps(run.completion))
    changed["portfolio_digest"] = "changed"
    with pytest.raises(
        execution_module.PredictionV2StructuralPortfolioExecutionError,
        match="replay_cross_identity_changed",
    ):
        replay_structural_portfolio_artifacts(
            portfolio=run.portfolio,
            optimizer_index=run.optimizer_index,
            null_comparison=run.null_comparison,
            completion=changed,
        )


def test_additive_migration_revises_execution_and_adds_only_evaluation() -> None:
    source_payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source_payload.pop("manifest_digest")
    source = ControlPlaneManifest.from_dict(source_payload).to_dict(
        include_digest=False
    )
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY
    ]
    execution = next(
        item
        for item in live["tasks"]
        if item["task_key"] == PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY
    )
    execution["requested_capability"] = None
    execution["input_artifact_digests"] = []
    execution["metric_contract"]["engineering_complete"] = False
    execution["metric_contract"]["engineering_increment_percent"] = 0
    source_contract = load_prediction_v2_structural_portfolio_execution_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_SOURCE_CONTRACT_PATH
    )
    source_fact = (
        "prediction-v2-structural-portfolio-execution-source:"
        f"{source_contract['artifact_digest']}"
    )
    live["facts"]["artifacts"] = [
        fact for fact in live["facts"]["artifacts"] if fact != source_fact
    ]
    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert len(migrated["tasks"]) == len(live["tasks"]) + 1
    assert source_fact in migrated["facts"]["artifacts"]


def test_status_routes_completed_execution_to_structural_evaluation() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    task_keys = (
        MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
        PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
        PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY,
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY,
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY,
        PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY,
    )
    tasks = {item.task_key: item for item in manifest.tasks}
    for item in payload["tasks"]:
        if item["task_key"] in task_keys:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT,
            "m4-v2-marginal-static-historical-evidence:INCONCLUSIVE",
            PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT,
            PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_COMPLETION_FACT,
            PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_COMPLETION_FACT,
            PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_COMPLETION_FACT,
            PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_COMPLETION_FACT,
            *(
                mainline_completion_fact(task=tasks[key], execution_id=char * 64)
                for key, char in zip(task_keys, "efdc9a", strict=True)
            ),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY,
            "structural_gate_status": "PASS",
            "structural_disposition": (
                "STRUCTURAL_DECISION_SUPPORT_HYPOTHESIS_SUPPORTED_AT_FROZEN_BUDGET_ONLY"
            ),
            "structural_portfolio_digest": "1" * 64,
            "structural_optimizer_index_digest": "2" * 64,
            "structural_null_comparison_digest": "3" * 64,
            "selected_island_index": 7,
            "selected_exact_stats": {
                "singleton_square_sum": 33_792,
                "pair_square_sum": 14_080,
                "minimum_replacement_distance": 2,
                "sum_pairwise_replacement_distance": 76_032,
            },
            "strictly_dominated_null_count": 3_900,
            "null_strictly_dominating_count": 0,
            "candidate_portfolios_generated": 22,
            "optimizer_proposals_executed": 5_767_168,
            "null_replicates_executed": 4_096,
            "registered_artifact_count": 5,
            "structural_algorithm_implemented": True,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION"
    assert projection["live_mainline_status"] == (
        "PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_VALIDATED_IN_MAINLINE"
    )
    assert projection["next_consumer"] == (
        PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY
    )
    execution_projection = projection["prediction_v2_structural_portfolio_execution"]
    assert execution_projection["resolver_status"] == "completed"
    assert execution_projection["execution_complete"] is True
    assert execution_projection["optimizer_proposals_executed"] == 5_767_168
    assert execution_projection["next_consumer_resolver_status"] == "ready"
    assert not {
        "duplicate_validation",
        "duplicate_check",
        "uniqueness_validation",
    }.intersection(_recursive_keys(execution_projection))


def test_supervisor_executes_and_replays_registered_outputs_without_duplicate_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = load_prediction_v2_structural_portfolio_execution_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_SOURCE_CONTRACT_PATH
    )
    for entry in source["source_entries"]:
        destination = tmp_path / str(entry["path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / str(entry["path"]), destination)
    contract_destination = (
        tmp_path / PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_SOURCE_CONTRACT_PATH
    )
    contract_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_SOURCE_CONTRACT_PATH,
        contract_destination,
    )
    preregistration_execution = {
        "artifact_digest": UPSTREAM_PREREGISTRATION_EXECUTION_DIGEST
    }
    parent_by_type = {
        "prediction_v2_structural_execution_preregistration": {
            "artifact_digest": UPSTREAM_PREREGISTRATION_DIGEST,
            "execution_contract_digest": UPSTREAM_EXECUTION_CONTRACT_DIGEST,
        },
        "prediction_v2_structural_portfolio_execution_handoff": {
            "artifact_digest": UPSTREAM_EXECUTION_HANDOFF_DIGEST
        },
        "prediction_v2_structural_decision_support_preregistration_completion": {
            "artifact_digest": UPSTREAM_PREREGISTRATION_COMPLETION_DIGEST
        },
    }
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, preregistration_execution, []),
    )
    original_load_type = supervisor_module._load_registered_type

    def load_type(*, artifact_type: str, **kwargs: object) -> dict:
        if artifact_type in parent_by_type:
            return parent_by_type[artifact_type]
        return original_load_type(artifact_type=artifact_type, **kwargs)

    monkeypatch.setattr(supervisor_module, "_load_registered_type", load_type)
    original_execute = execute_structural_portfolio_program

    def execute_tiny(**kwargs: object) -> StructuralPortfolioExecutionRun:
        arguments = dict(kwargs)
        arguments["source_contract"] = {
            **dict(kwargs["source_contract"]),
            "test_mode_allowed": True,
        }
        run = original_execute(
            **arguments,
            settings=_settings(),
        )
        completion = dict(run.completion)
        completion.update(
            {
                "candidate_portfolios_generated": 22,
                "optimizer_proposals_executed": 5_767_168,
                "null_replicates_executed": 4_096,
            }
        )
        identity = {
            key: value for key, value in completion.items() if key != "artifact_digest"
        }
        completion["artifact_digest"] = canonical_digest(
            identity,
            domain=("dehps.prediction-v2.structural-portfolio-execution-completion.v1"),
        )
        return StructuralPortfolioExecutionRun(
            portfolio=run.portfolio,
            optimizer_index=run.optimizer_index,
            null_comparison=run.null_comparison,
            completion=completion,
        )

    monkeypatch.setattr(
        supervisor_module, "execute_structural_portfolio_program", execute_tiny
    )
    task = next(
        item
        for item in load_m4_manifest(MANIFEST_PATH).tasks
        if item.task_key == PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY
    )
    result = PredictionV2StructuralPortfolioExecutionCapability(
        repository=object(), root_dir=tmp_path
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="a" * 64,
        git_commit="b" * 40,
    )
    assert len(result.registrations) == 5
    assert result.execution_artifact["registered_artifact_count"] == 5
    assert result.execution_artifact["optimizer_proposals_executed"] == 5_767_168
    assert not {
        "duplicate_validation",
        "duplicate_check",
        "uniqueness_validation",
    }.intersection(_recursive_keys([result.execution_artifact, *result.registrations]))

    class ReplayRepository:
        def list_mainline_execution_events(self, **_: object) -> list[dict]:
            return [
                {
                    "event_type": "completed",
                    "execution_id": "a" * 64,
                    "payload": [
                        [
                            "execution_artifact_path",
                            result.execution_artifact_path.relative_to(
                                tmp_path
                            ).as_posix(),
                        ],
                        ["registered_artifact_count", 5],
                    ],
                }
            ]

        def list_mainline_artifacts(self, **_: object) -> list[dict]:
            return [asdict(item) for item in result.registrations]

    replay = ResearchEvidenceSupervisor(
        repository=ReplayRepository(), root_dir=tmp_path, require_clean_tree=False
    ).replay(
        task_key=PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY,
        execution_id="a" * 64,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["same_registered_content"] is True
    assert capability_replay["workload_rerun"] is False
    assert capability_replay["optimizer_proposals_replayed"] == 0
    assert capability_replay["null_replicates_replayed"] == 0
    assert not {
        "duplicate_validation",
        "duplicate_check",
        "uniqueness_validation",
    }.intersection(_recursive_keys(capability_replay))


def test_artifact_index_and_supervisor_register_execution() -> None:
    source = load_prediction_v2_structural_portfolio_execution_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_SOURCE_CONTRACT_PATH
    )
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    entry = index[source["artifact_digest"]]
    assert entry["path"] == str(
        PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_SOURCE_CONTRACT_PATH
    )
    assert entry["identity_field"] == "artifact_digest"
    manifest = load_m4_manifest(MANIFEST_PATH)
    assert index[manifest.artifact_digest]["identity_field"] == "manifest_digest"
    supervisor = ResearchEvidenceSupervisor(
        repository=object(), require_clean_tree=False
    )
    assert PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_CAPABILITY in (
        supervisor.capabilities
    )
