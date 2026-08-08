from __future__ import annotations

import copy
import json
import shutil
from dataclasses import asdict
from pathlib import Path

import pytest
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_structural_portfolio_evaluation import (
    EVALUATION_DECISION,
    PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_CAPABILITY,
    PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_COMPLETION_FACT,
    PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY,
    PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY,
    ROUTE_DISPOSITION,
    PredictionV2StructuralPortfolioEvaluationError,
    build_prediction_v2_structural_portfolio_evaluation_artifacts,
    load_prediction_v2_structural_portfolio_evaluation_source_contract,
    verify_prediction_v2_structural_portfolio_evaluation_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_structural_portfolio_execution import (
    PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_COMPLETION_FACT,
    PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    PredictionV2StructuralPortfolioEvaluationCapability,
    ResearchEvidenceSupervisor,
)

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)


def _artifact(body: dict, *, domain: str) -> dict:
    payload = {"artifact_digest": "", **body}
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _parents() -> dict[str, dict]:
    null_rows = [
        {
            "replicate_index": index,
            "stats": {
                "singleton_square_sum": 34_200,
                "pair_square_sum": 15_300,
                "minimum_replacement_distance": 1,
                "sum_pairwise_replacement_distance": 75_800,
            },
        }
        for index in range(4_096)
    ]
    null_rows[0]["stats"]["singleton_square_sum"] = 34_104
    null_rows[1]["stats"]["pair_square_sum"] = 15_144
    null_rows[2]["stats"]["minimum_replacement_distance"] = 2
    null_rows[3]["stats"]["sum_pairwise_replacement_distance"] = 75_876
    comparisons = [
        {
            "island_index": index,
            "stats": {
                "singleton_square_sum": 33_796,
                "pair_square_sum": 14_100 + index * 2,
                "minimum_replacement_distance": 2 if index < 16 else 1,
                "sum_pairwise_replacement_distance": 76_030,
            },
            "strictly_dominated_null_count": 4_096 if index < 16 else 4_095,
            "null_strictly_dominating_count": 0,
        }
        for index in range(22)
    ]
    optimizer_index = _artifact(
        {
            "schema_version": "dehps-prediction-v2-structural-optimizer-index.v1",
            "artifact_type": "prediction_v2_structural_optimizer_result_index",
            "status": "COMPLETE",
            "candidate_budget": 176,
            "island_count": 22,
            "total_proposals_executed": 5_767_168,
            "islands": [
                {"island_index": index, "stats": row["stats"]}
                for index, row in enumerate(comparisons)
            ],
            "parent_digests": [],
        },
        domain="dehps.prediction-v2.structural-optimizer-index.v1",
    )
    null_comparison = _artifact(
        {
            "schema_version": "dehps-prediction-v2-structural-null-comparison.v1",
            "artifact_type": "prediction_v2_structural_same_budget_null_comparison",
            "status": "COMPLETE",
            "candidate_budget": 176,
            "replicate_count": 4_096,
            "ordered_replicates": null_rows,
            "island_comparisons": comparisons,
            "selected_island_index": 14,
            "selected_strictly_dominated_null_count": 4_096,
            "selected_null_strictly_dominating_count": 0,
            "mechanical_gate_status": "PASS",
            "gate_semantics": "STRUCTURAL_PERFORMANCE_GATE_NOT_PREDICTIVE_P_VALUE",
            "optimizer_index_digest": optimizer_index["artifact_digest"],
            "parent_digests": [optimizer_index["artifact_digest"]],
        },
        domain="dehps.prediction-v2.structural-null-comparison.v1",
    )
    portfolio = _artifact(
        {
            "schema_version": "dehps-prediction-v2-canonical-structural-portfolio.v1",
            "artifact_type": "prediction_v2_canonical_b176_structural_portfolio",
            "status": "COMPLETE",
            "candidate_budget": 176,
            "selected_island_index": 14,
            "exact_stats": {
                "singleton_square_sum": 33_796,
                "pair_square_sum": 14_152,
                "minimum_replacement_distance": 2,
                "sum_pairwise_replacement_distance": 76_030,
            },
            "structural_gate_status": "PASS",
            "prediction_probability_claim": False,
            "global_optimality_claim": False,
            "optimizer_index_digest": optimizer_index["artifact_digest"],
            "null_comparison_digest": null_comparison["artifact_digest"],
            "parent_digests": [
                optimizer_index["artifact_digest"],
                null_comparison["artifact_digest"],
            ],
        },
        domain="dehps.prediction-v2.canonical-structural-portfolio.v1",
    )
    execution_completion = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-structural-portfolio-execution-completion.v1"
            ),
            "artifact_type": "prediction_v2_structural_portfolio_execution_completion",
            "status": "COMPLETE",
            "portfolio_digest": portfolio["artifact_digest"],
            "optimizer_index_digest": optimizer_index["artifact_digest"],
            "null_comparison_digest": null_comparison["artifact_digest"],
            "next_consumer": PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY,
            "parent_digests": [
                portfolio["artifact_digest"],
                optimizer_index["artifact_digest"],
                null_comparison["artifact_digest"],
            ],
        },
        domain=("dehps.prediction-v2.structural-portfolio-execution-completion.v1"),
    )
    structural_execution = _artifact(
        {
            "schema_version": "dehps-research-os-mainline-execution.v1",
            "artifact_type": "research_os_mainline_execution",
            "task_key": PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY,
            "completion_fact": (
                PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_COMPLETION_FACT
            ),
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "structural_gate_status": "PASS",
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
            "structural_portfolio_digest": portfolio["artifact_digest"],
            "structural_optimizer_index_digest": optimizer_index["artifact_digest"],
            "structural_null_comparison_digest": null_comparison["artifact_digest"],
            "structural_execution_completion_digest": execution_completion[
                "artifact_digest"
            ],
            "parent_digests": [],
        },
        domain="dehps.research-os.mainline-execution.v1",
    )
    return {
        "structural_execution": structural_execution,
        "portfolio": portfolio,
        "optimizer_index": optimizer_index,
        "null_comparison": null_comparison,
        "execution_completion": execution_completion,
    }


def _recursive_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(
            *(_recursive_keys(item) for item in value.values()), set()
        )
    if isinstance(value, list):
        return set().union(*(_recursive_keys(item) for item in value), set())
    return set()


def test_source_contract_and_exact_registered_summary_evaluation() -> None:
    source = load_prediction_v2_structural_portfolio_evaluation_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_structural_portfolio_evaluation_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    run = build_prediction_v2_structural_portfolio_evaluation_artifacts(
        source_contract=source,
        require_registered_identities=False,
        **_parents(),
    )
    assert run.decision["decision"] == EVALUATION_DECISION
    assert run.decision["finite_design_ideals"] == {
        "singleton_square_sum": 33_792,
        "pair_square_sum": 13_200,
        "sum_pairwise_replacement_distance": 76_032,
    }
    assert run.decision["selected_ideal_gaps"] == {
        "singleton_square_sum_excess": 4,
        "pair_square_sum_excess": 952,
        "sum_pairwise_replacement_distance_deficit": 2,
    }
    assert run.decision["islands_passing_frozen_gate"] == 16
    assert run.decision["islands_dominating_every_null"] == 16
    assert run.route_handoff["route_disposition"] == ROUTE_DISPOSITION
    assert run.route_handoff["portfolio_activation_authorized"] is False
    assert run.completion["next_consumer"] == (
        PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY
    )
    assert not {
        "duplicate_validation",
        "duplicate_check",
        "uniqueness_validation",
    }.intersection(_recursive_keys(run.artifacts))


def test_evaluator_fails_closed_on_null_extrema_or_island_drift() -> None:
    source = load_prediction_v2_structural_portfolio_evaluation_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_SOURCE_CONTRACT_PATH
    )
    parents = _parents()
    changed = copy.deepcopy(parents["null_comparison"])
    changed["ordered_replicates"][0]["stats"]["singleton_square_sum"] = 34_106
    identity = {
        key: value for key, value in changed.items() if key != "artifact_digest"
    }
    changed["artifact_digest"] = canonical_digest(
        identity, domain="dehps.prediction-v2.structural-null-comparison.v1"
    )
    parents["null_comparison"] = changed
    with pytest.raises(
        PredictionV2StructuralPortfolioEvaluationError,
        match="parent_consistency_invalid",
    ):
        build_prediction_v2_structural_portfolio_evaluation_artifacts(
            source_contract=source,
            require_registered_identities=False,
            **parents,
        )


def test_additive_migration_revises_evaluation_and_adds_only_route_decision() -> None:
    source_manifest = load_m4_manifest(MANIFEST_PATH)
    source = source_manifest.to_dict(include_digest=False)
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY
    ]
    evaluation = next(
        item
        for item in live["tasks"]
        if item["task_key"] == PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY
    )
    evaluation["requested_capability"] = None
    evaluation["input_artifact_digests"] = []
    evaluation["metric_contract"]["engineering_complete"] = False
    evaluation["metric_contract"]["engineering_increment_percent"] = 0
    source_contract = (
        load_prediction_v2_structural_portfolio_evaluation_source_contract(
            ROOT_DIR
            / PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_SOURCE_CONTRACT_PATH
        )
    )
    source_fact = (
        "prediction-v2-structural-portfolio-evaluation-source:"
        f"{source_contract['artifact_digest']}"
    )
    live["facts"]["artifacts"] = [
        fact for fact in live["facts"]["artifacts"] if fact != source_fact
    ]
    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY,),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert len(migrated["tasks"]) == len(live["tasks"]) + 1


def test_status_routes_completed_evaluation_to_structural_route_decision() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    tasks = {item.task_key: item for item in manifest.tasks}
    task_keys = (
        PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY,
        PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY,
    )
    for item in payload["tasks"]:
        if item["task_key"] in task_keys:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_COMPLETION_FACT,
            PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_COMPLETION_FACT,
            *(
                mainline_completion_fact(task=tasks[key], execution_id=char * 64)
                for key, char in zip(task_keys, "ab", strict=True)
            ),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": (
                PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY
            ),
            "evaluation_decision": EVALUATION_DECISION,
            "route_disposition": ROUTE_DISPOSITION,
            "selected_stats": {"minimum_replacement_distance": 2},
            "finite_design_ideals": {"singleton_square_sum": 33_792},
            "selected_ideal_gaps": {"singleton_square_sum_excess": 4},
            "uniform_null_extrema": {"singleton_square_sum_minimum": 34_104},
            "islands_passing_frozen_gate": 16,
            "islands_dominating_every_null": 16,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "PREDICTION_V2_STRUCTURAL_ROUTE_DECISION"
    assert projection["live_mainline_status"] == (
        "PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_VALIDATED_IN_MAINLINE"
    )
    assert projection["next_consumer"] == (
        PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY
    )
    evaluation = projection["prediction_v2_structural_portfolio_evaluation"]
    assert evaluation["evaluation_complete"] is True
    assert evaluation["evaluation_decision"] == EVALUATION_DECISION
    assert evaluation["next_consumer_resolver_status"] == "ready"


def test_supervisor_executes_and_replays_evaluation_without_workload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = load_prediction_v2_structural_portfolio_evaluation_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_SOURCE_CONTRACT_PATH
    )
    for entry in source["source_entries"]:
        destination = tmp_path / str(entry["path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / str(entry["path"]), destination)
    contract_destination = (
        tmp_path / PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_SOURCE_CONTRACT_PATH
    )
    contract_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_SOURCE_CONTRACT_PATH,
        contract_destination,
    )
    parents = _parents()
    fixed = source["frozen_contract"]["registered_input_digests"]
    for key, digest in zip(
        (
            "structural_execution",
            "portfolio",
            "optimizer_index",
            "null_comparison",
            "execution_completion",
        ),
        fixed,
        strict=True,
    ):
        parents[key]["artifact_digest"] = digest
    parent_by_type = {
        "prediction_v2_canonical_b176_structural_portfolio": parents["portfolio"],
        "prediction_v2_structural_optimizer_result_index": parents["optimizer_index"],
        "prediction_v2_structural_same_budget_null_comparison": parents[
            "null_comparison"
        ],
        "prediction_v2_structural_portfolio_execution_completion": parents[
            "execution_completion"
        ],
    }
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, parents["structural_execution"], []),
    )
    original_load_type = supervisor_module._load_registered_type

    def load_type(*, artifact_type: str, **kwargs: object) -> dict:
        if artifact_type in parent_by_type:
            return parent_by_type[artifact_type]
        return original_load_type(artifact_type=artifact_type, **kwargs)

    monkeypatch.setattr(supervisor_module, "_load_registered_type", load_type)
    synthetic = build_prediction_v2_structural_portfolio_evaluation_artifacts(
        source_contract=source,
        require_registered_identities=False,
        **_parents(),
    )
    monkeypatch.setattr(
        supervisor_module,
        "build_prediction_v2_structural_portfolio_evaluation_artifacts",
        lambda **_: synthetic,
    )
    task = next(
        item
        for item in load_m4_manifest(MANIFEST_PATH).tasks
        if item.task_key == PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY
    )
    result = PredictionV2StructuralPortfolioEvaluationCapability(
        repository=object(), root_dir=tmp_path
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="c" * 64,
        git_commit="d" * 40,
    )
    assert len(result.registrations) == 4
    assert result.execution_artifact["optimizer_proposals_executed"] == 0
    assert result.execution_artifact["null_replicates_executed"] == 0
    assert result.execution_artifact["evaluation_decision"] == EVALUATION_DECISION

    class ReplayRepository:
        def list_mainline_execution_events(self, **_: object) -> list[dict]:
            return [
                {
                    "event_type": "completed",
                    "execution_id": "c" * 64,
                    "payload": [
                        [
                            "execution_artifact_path",
                            result.execution_artifact_path.relative_to(
                                tmp_path
                            ).as_posix(),
                        ],
                        ["registered_artifact_count", 4],
                    ],
                }
            ]

        def list_mainline_artifacts(self, **_: object) -> list[dict]:
            return [asdict(item) for item in result.registrations]

    monkeypatch.setattr(
        supervisor_module,
        "replay_prediction_v2_structural_portfolio_evaluation",
        lambda **_: (
            synthetic,
            {
                "status": "REPLAY_VERIFIED",
                "same_registered_content": True,
                "workload_rerun": False,
                "optimizer_proposals_replayed": 0,
                "null_replicates_replayed": 0,
            },
        ),
    )
    replay = ResearchEvidenceSupervisor(
        repository=ReplayRepository(), root_dir=tmp_path, require_clean_tree=False
    ).replay(
        task_key=PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY,
        execution_id="c" * 64,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["workload_rerun"] is False
    assert capability_replay["optimizer_proposals_replayed"] == 0
    assert capability_replay["null_replicates_replayed"] == 0


def test_artifact_index_and_supervisor_register_evaluator() -> None:
    source = load_prediction_v2_structural_portfolio_evaluation_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_SOURCE_CONTRACT_PATH
    )
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[source["artifact_digest"]]["path"] == str(
        PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_SOURCE_CONTRACT_PATH
    )
    manifest = load_m4_manifest(MANIFEST_PATH)
    assert index[manifest.artifact_digest]["identity_field"] == "manifest_digest"
    supervisor = ResearchEvidenceSupervisor(
        repository=object(), require_clean_tree=False
    )
    assert PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_CAPABILITY in (
        supervisor.capabilities
    )


def test_direct_replay_rebuilds_same_three_children() -> None:
    source = load_prediction_v2_structural_portfolio_evaluation_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_SOURCE_CONTRACT_PATH
    )
    parents = _parents()
    first = build_prediction_v2_structural_portfolio_evaluation_artifacts(
        source_contract=source,
        require_registered_identities=False,
        **parents,
    )
    rebuilt = build_prediction_v2_structural_portfolio_evaluation_artifacts(
        source_contract=source,
        require_registered_identities=False,
        **parents,
    )
    assert rebuilt.artifacts == first.artifacts
    assert all(item.get("p_value_claim", False) is False for item in first.artifacts)
