from __future__ import annotations

import copy
import json

import pytest
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2 import (
    prediction_v2_structural_baseline_comparison_route_decision as route_module,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_structural_baseline_comparison_route_decision import (
    CLASS_SUMMARIES,
    NEXT_RESEARCH_CONTRACT_EVENT,
    PREDICTION_RESEARCH_DISPOSITION,
    PREDICTION_V2_NEXT_RESULT_BLIND_RESEARCH_INTAKE_TASK_KEY,
    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_CAPABILITY,
    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_COMPLETION_FACT,
    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY,
    REPETITION_SCAN,
    ROUTE_DECISION,
    STRUCTURAL_ARTIFACT_ROLE,
    PredictionV2StructuralBaselineComparisonRouteDecisionError,
    build_prediction_v2_structural_baseline_comparison_route_decision_artifacts,
    load_prediction_v2_structural_baseline_comparison_route_decision_source_contract,
    replay_prediction_v2_structural_baseline_comparison_route_decision,
    verify_prediction_v2_structural_baseline_comparison_route_decision_source_bytes,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest, TaskStatus
from dehps.research_os.supervisor import ResearchEvidenceSupervisor

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)
EXECUTION_TASK_KEY = "prediction-v2-structural-baseline-comparison-execution"
EXECUTION_COMPLETION_FACT = (
    "prediction-v2-structural-baseline-comparison-execution:COMPLETE"
)
SOURCE_FACT_PREFIX = (
    "prediction-v2-structural-baseline-comparison-route-decision-source:"
)


def _artifact(body: dict, *, domain: str) -> dict:
    payload = {"artifact_digest": "", **body}
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _parents() -> dict[str, dict]:
    summaries = [dict(item) for item in CLASS_SUMMARIES]
    candidate_stats = {
        "singleton_square_sum": 33_796,
        "pair_square_sum": 14_152,
        "minimum_replacement_distance": 2,
        "sum_pairwise_replacement_distance": 76_030,
    }
    result = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-structural-baseline-comparison-result-index.v1"
            ),
            "artifact_type": (
                "prediction_v2_structural_baseline_comparison_result_index"
            ),
            "status": "COMPLETE",
            "baseline_class_ids": [
                "SINGLETON_FIRST_GREEDY_V1",
                "PAIR_FIRST_GREEDY_V1",
                "DISTANCE_FIRST_GREEDY_V1",
            ],
            "replicates_per_class": 128,
            "portfolio_budget": 176,
            "total_candidate_considerations": 17_301_504,
            "candidate_stats": candidate_stats,
            "class_summaries": summaries,
            "repetition_scan": REPETITION_SCAN,
            "parent_digests": [],
        },
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-result-index.v1"
        ),
    )
    gate = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-structural-baseline-comparison-gate-outcome.v1"
            ),
            "artifact_type": (
                "prediction_v2_structural_baseline_comparison_gate_outcome"
            ),
            "status": "COMPLETE",
            "valid_execution": True,
            "decision": "ARCHIVE_AS_ENGINEERING_EVIDENCE_ONLY",
            "result_index_digest": result["artifact_digest"],
            "candidate_stats": candidate_stats,
            "class_summaries": summaries,
            "required_candidate_dominated_replicates_per_class": 122,
            "maximum_baseline_replicates_dominating_candidate_per_class": 0,
            "repetition_scan": REPETITION_SCAN,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "portfolio_activation_authorized": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
            "parent_digests": [result["artifact_digest"]],
        },
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-gate-outcome.v1"
        ),
    )
    completion = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-structural-baseline-comparison-"
                "execution-completion.v1"
            ),
            "artifact_type": (
                "prediction_v2_structural_baseline_comparison_execution_completion"
            ),
            "status": "COMPLETE",
            "completion_fact": EXECUTION_COMPLETION_FACT,
            "result_index_digest": result["artifact_digest"],
            "gate_outcome_digest": gate["artifact_digest"],
            "decision": "ARCHIVE_AS_ENGINEERING_EVIDENCE_ONLY",
            "registered_child_count": 3,
            "baseline_replicates_executed": 384,
            "total_candidate_considerations": 17_301_504,
            "next_consumer": (
                PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
            ),
            "repetition_scan": REPETITION_SCAN,
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "portfolio_activation_authorized": False,
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
            "parent_digests": [
                result["artifact_digest"],
                gate["artifact_digest"],
            ],
        },
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-"
            "execution-completion.v1"
        ),
    )
    execution = _artifact(
        {
            "schema_version": "dehps-research-os-mainline-execution.v1",
            "artifact_type": "research_os_mainline_execution",
            "task_key": EXECUTION_TASK_KEY,
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "completion_fact": EXECUTION_COMPLETION_FACT,
            "structural_baseline_result_index_digest": result["artifact_digest"],
            "structural_baseline_gate_outcome_digest": gate["artifact_digest"],
            "structural_baseline_execution_completion_digest": completion[
                "artifact_digest"
            ],
            "decision": "ARCHIVE_AS_ENGINEERING_EVIDENCE_ONLY",
            "candidate_stats": candidate_stats,
            "class_summaries": summaries,
            "baseline_replicates_executed": 384,
            "total_candidate_considerations": 17_301_504,
            "repetition_scan": REPETITION_SCAN,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "portfolio_activation_authorized": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
            "parent_digests": [
                result["artifact_digest"],
                gate["artifact_digest"],
                completion["artifact_digest"],
            ],
        },
        domain="dehps.research-os.mainline-execution.v1",
    )
    return {
        "comparison_execution": execution,
        "result_index": result,
        "gate_outcome": gate,
        "execution_completion": completion,
    }


def _recursive_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(
            *(_recursive_keys(item) for item in value.values()), set()
        )
    if isinstance(value, (list, tuple)):
        return set().union(*(_recursive_keys(item) for item in value), set())
    return set()


def _source() -> dict:
    source = load_prediction_v2_structural_baseline_comparison_route_decision_source_contract(
        ROOT_DIR
        / PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_structural_baseline_comparison_route_decision_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    return source


def test_route_artifacts_archive_b176_and_replay_without_workload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source()
    parents = _parents()
    run = build_prediction_v2_structural_baseline_comparison_route_decision_artifacts(
        source_contract=source,
        require_registered_identities=False,
        **parents,
    )
    assert run.decision["decision"] == ROUTE_DECISION
    assert run.decision["structural_artifact_role"] == STRUCTURAL_ARTIFACT_ROLE
    assert run.decision["prediction_research_disposition"] == (
        PREDICTION_RESEARCH_DISPOSITION
    )
    assert run.decision["threshold_retuned"] is False
    assert run.decision["legacy_prediction_mainline_reactivation_authorized"] is False
    assert run.research_intake_handoff["required_external_event"] == (
        NEXT_RESEARCH_CONTRACT_EVENT
    )
    assert run.completion["candidate_considerations_executed"] == 0
    assert run.completion["repetition_scan"] == REPETITION_SCAN
    assert not {
        "duplicate_validation",
        "duplicate_check",
        "uniqueness_validation",
        "duplicate_scan",
    }.intersection(_recursive_keys(run.artifacts))
    rebuilt_directly = (
        build_prediction_v2_structural_baseline_comparison_route_decision_artifacts(
            source_contract=source,
            require_registered_identities=False,
            **parents,
        )
    )
    assert rebuilt_directly.artifacts == run.artifacts
    monkeypatch.setattr(
        route_module,
        "build_prediction_v2_structural_baseline_comparison_route_decision_artifacts",
        lambda **_: run,
    )
    rebuilt, replay = replay_prediction_v2_structural_baseline_comparison_route_decision(
        source_contract=source,
        **parents,
    )
    assert rebuilt.artifacts == run.artifacts
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["workload_rerun"] is False
    assert replay["candidate_considerations_replayed"] == 0


def test_route_decision_fails_closed_on_parent_result_drift() -> None:
    parents = _parents()
    changed = copy.deepcopy(parents["gate_outcome"])
    changed["required_candidate_dominated_replicates_per_class"] = 121
    identity = {key: value for key, value in changed.items() if key != "artifact_digest"}
    changed["artifact_digest"] = canonical_digest(
        identity,
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-gate-outcome.v1"
        ),
    )
    parents["gate_outcome"] = changed
    with pytest.raises(
        PredictionV2StructuralBaselineComparisonRouteDecisionError,
        match="parent_consistency_invalid",
    ):
        build_prediction_v2_structural_baseline_comparison_route_decision_artifacts(
            source_contract=_source(),
            require_registered_identities=False,
            **parents,
        )


def test_additive_migration_revises_route_and_adds_only_external_wait_intake() -> None:
    source = load_m4_manifest(MANIFEST_PATH).to_dict(include_digest=False)
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"]
        != PREDICTION_V2_NEXT_RESULT_BLIND_RESEARCH_INTAKE_TASK_KEY
    ]
    route = next(
        item
        for item in live["tasks"]
        if item["task_key"]
        == PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
    )
    route["requested_capability"] = None
    route["input_artifact_digests"] = []
    route["metric_contract"]["engineering_complete"] = False
    route["metric_contract"]["engineering_increment_percent"] = 0
    source_fact = SOURCE_FACT_PREFIX + _source()["artifact_digest"]
    live["facts"]["artifacts"] = [
        fact for fact in live["facts"]["artifacts"] if fact != source_fact
    ]
    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            PREDICTION_V2_NEXT_RESULT_BLIND_RESEARCH_INTAKE_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_NEXT_RESULT_BLIND_RESEARCH_INTAKE_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert len(migrated["tasks"]) == len(live["tasks"]) + 1


def test_status_projects_archive_and_exact_external_wait() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    tasks = {item.task_key: item for item in manifest.tasks}
    for item in payload["tasks"]:
        if item["task_key"] in {
            EXECUTION_TASK_KEY,
            PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY,
        }:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["external_events"] = [
        event
        for event in payload["facts"]["external_events"]
        if event != NEXT_RESEARCH_CONTRACT_EVENT
    ]
    payload["facts"]["artifacts"] = list(
        dict.fromkeys(
            (
                *payload["facts"]["artifacts"],
                EXECUTION_COMPLETION_FACT,
                PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_COMPLETION_FACT,
                mainline_completion_fact(
                    task=tasks[EXECUTION_TASK_KEY], execution_id="a" * 64
                ),
                mainline_completion_fact(
                    task=tasks[
                        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
                    ],
                    execution_id="b" * 64,
                ),
            )
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": (
                PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
            ),
            "decision": ROUTE_DECISION,
            "comparison_decision": "ARCHIVE_AS_ENGINEERING_EVIDENCE_ONLY",
            "structural_artifact_role": STRUCTURAL_ARTIFACT_ROLE,
            "prediction_research_disposition": PREDICTION_RESEARCH_DISPOSITION,
            "candidate_stats": {},
            "class_summaries": [dict(item) for item in CLASS_SUMMARIES],
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "PREDICTION_V2_NEXT_RESULT_BLIND_RESEARCH_INTAKE"
    assert projection["live_mainline_status"] == (
        "PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_"
        "VALIDATED_IN_MAINLINE"
    )
    route = projection[
        "prediction_v2_structural_baseline_comparison_route_decision"
    ]
    assert route["route_complete"] is True
    assert route["decision"] == ROUTE_DECISION
    assert route["legacy_prediction_mainline_reactivation_authorized"] is False
    intake = projection["prediction_v2_next_result_blind_research_intake"]
    assert intake["resolver_status"] == "external_wait"
    assert intake["required_external_event"] == NEXT_RESEARCH_CONTRACT_EVENT
    assert intake["requested_capability"] == (
        "prediction_v2_balanced_design_feasibility_design"
    )


def test_manifest_index_and_supervisor_bind_the_singular_capability() -> None:
    source = _source()
    manifest = load_m4_manifest(MANIFEST_PATH)
    task = next(
        item
        for item in manifest.tasks
        if item.task_key
        == PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
    )
    assert task.requested_capability == (
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_CAPABILITY
    )
    assert task.input_artifact_digests[0] == source["artifact_digest"]
    assert len(task.input_artifact_digests) == 5
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[source["artifact_digest"]]["path"] == str(
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_SOURCE_CONTRACT_PATH
    )
    assert index[manifest.artifact_digest]["identity_field"] == "manifest_digest"
    supervisor = ResearchEvidenceSupervisor(
        repository=object(), require_clean_tree=False
    )
    assert PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_CAPABILITY in (
        supervisor.capabilities
    )


def test_latest_summary_prefers_completed_archive_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolutions = [
        type(
            "Resolution",
            (),
            {
                "task_key": EXECUTION_TASK_KEY,
                "status": TaskStatus.COMPLETED,
            },
        )(),
        type(
            "Resolution",
            (),
            {
                "task_key": (
                    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
                ),
                "status": TaskStatus.COMPLETED,
            },
        )(),
    ]
    requested: list[str] = []

    def load_execution(**kwargs: object) -> tuple[dict, dict, tuple]:
        requested.append(str(kwargs["task_key"]))
        return (
            {"payload": [["registered_artifact_count", 4]]},
            {"artifact_digest": "1" * 64, "decision": ROUTE_DECISION},
            (),
        )

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        load_execution,
    )
    summary = ResearchEvidenceSupervisor(
        repository=object(), require_clean_tree=False
    )._latest_completed_v2_summary(type("Snapshot", (), {"resolutions": resolutions})())
    assert summary is not None
    assert requested == [
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
    ]
    assert summary["execution_task_key"] == (
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
    )
    assert summary["decision"] == ROUTE_DECISION
    assert summary["registered_artifact_count"] == 4
