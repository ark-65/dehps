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
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_structural_baseline_comparison_preregistration import (
    BASELINE_CLASSES,
    CANDIDATE_CONSIDERATIONS_PER_CLASS,
    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY,
    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_CAPABILITY,
    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_COMPLETION_FACT,
    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY,
    PREREGISTRATION_DECISION,
    ROUTE_COMPLETION_DIGEST,
    ROUTE_DECISION,
    ROUTE_DECISION_DIGEST,
    ROUTE_EXECUTION_DIGEST,
    ROUTE_HANDOFF_DIGEST,
    STRUCTURAL_ARTIFACT_ROLE,
    TOTAL_CANDIDATE_CONSIDERATIONS,
    PredictionV2StructuralBaselineComparisonPreregistrationError,
    build_prediction_v2_structural_baseline_comparison_preregistration_artifacts,
    load_prediction_v2_structural_baseline_comparison_preregistration_source_contract,
    verify_prediction_v2_structural_baseline_comparison_preregistration_source_bytes,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest, TaskStatus
from dehps.research_os.supervisor import (
    PredictionV2StructuralBaselineComparisonPreregistrationCapability,
    ResearchEvidenceSupervisor,
)

MANIFEST_PATH = ROOT_DIR / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)
ROUTE_TASK_KEY = "prediction-v2-structural-route-decision"
ROUTE_COMPLETION_FACT = "prediction-v2-structural-route-decision:COMPLETE"
ARCHIVE_CONDITION = (
    "IF_RESULT_BLIND_PREREGISTRATION_CANNOT_FREEZE_STRONGER_SIMPLE_SAME_BUDGET_"
    "LABEL_SYMMETRIC_BASELINES_AND_AN_OBSERVED_RESULT_INDEPENDENT_FAILURE_RULE_"
    "ARCHIVE_AS_ENGINEERING_EVIDENCE_ONLY"
)


def _artifact(body: dict, *, domain: str) -> dict:
    payload = {"artifact_digest": "", **body}
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _route_parents() -> dict[str, dict]:
    decision = _artifact(
        {
            "schema_version": "dehps-prediction-v2-structural-route-decision.v1",
            "artifact_type": "prediction_v2_structural_route_decision",
            "status": "COMPLETE",
            "decision": ROUTE_DECISION,
            "structural_artifact_role": STRUCTURAL_ARTIFACT_ROLE,
            "archive_condition": ARCHIVE_CONDITION,
            "stronger_baseline_comparison_required": True,
            "portfolio_activation_authorized": False,
            "decision_usefulness_established": False,
            "parent_digests": [],
        },
        domain="dehps.prediction-v2.structural-route-decision.v1",
    )
    handoff = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-structural-baseline-comparison-"
                "preregistration-handoff.v1"
            ),
            "artifact_type": (
                "prediction_v2_structural_baseline_comparison_preregistration_handoff"
            ),
            "status": "COMPLETE",
            "route_decision": ROUTE_DECISION,
            "preregistration_scope": (
                "STRONGER_SIMPLE_SAME_BUDGET_LABEL_SYMMETRIC_BASELINE_COMPARISON"
            ),
            "result_blind_preregistration_required": True,
            "observed_result_may_define_thresholds": False,
            "baseline_classes_frozen": False,
            "comparison_execution_authorized": False,
            "next_consumer": (
                PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
            ),
            "parent_digests": [decision["artifact_digest"]],
        },
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-"
            "preregistration-handoff.v1"
        ),
    )
    completion = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-structural-route-decision-completion.v1"
            ),
            "artifact_type": "prediction_v2_structural_route_decision_completion",
            "status": "COMPLETE",
            "completion_fact": ROUTE_COMPLETION_FACT,
            "route_decision_digest": decision["artifact_digest"],
            "baseline_preregistration_handoff_digest": handoff["artifact_digest"],
            "decision": ROUTE_DECISION,
            "next_consumer": (
                PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
            ),
            "parent_digests": [
                decision["artifact_digest"],
                handoff["artifact_digest"],
            ],
        },
        domain="dehps.prediction-v2.structural-route-decision-completion.v1",
    )
    execution = _artifact(
        {
            "schema_version": "dehps-research-os-mainline-execution.v1",
            "artifact_type": "research_os_mainline_execution",
            "task_key": ROUTE_TASK_KEY,
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "completion_fact": ROUTE_COMPLETION_FACT,
            "route_decision": ROUTE_DECISION,
            "structural_artifact_role": STRUCTURAL_ARTIFACT_ROLE,
            "structural_route_decision_digest": decision["artifact_digest"],
            "structural_baseline_preregistration_handoff_digest": handoff[
                "artifact_digest"
            ],
            "structural_route_decision_completion_digest": completion[
                "artifact_digest"
            ],
            "stronger_baseline_comparison_required": True,
            "same_budget_required": True,
            "label_symmetry_required": True,
            "transparent_baselines_required": True,
            "observed_result_independent_failure_rule_required": True,
            "portfolio_activation_authorized": False,
            "decision_usefulness_established": False,
            "prediction_probability_claim": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
            "parent_digests": [
                decision["artifact_digest"],
                handoff["artifact_digest"],
                completion["artifact_digest"],
            ],
        },
        domain="dehps.research-os.mainline-execution.v1",
    )
    return {
        "route_execution": execution,
        "route_decision": decision,
        "route_handoff": handoff,
        "route_completion": completion,
    }


def _recursive_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(
            *(_recursive_keys(item) for item in value.values()), set()
        )
    if isinstance(value, list):
        return set().union(*(_recursive_keys(item) for item in value), set())
    return set()


def test_source_contract_freezes_zero_work_program_without_repeat_scan() -> None:
    source = load_prediction_v2_structural_baseline_comparison_preregistration_source_contract(
        ROOT_DIR
        / PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_structural_baseline_comparison_preregistration_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    run = build_prediction_v2_structural_baseline_comparison_preregistration_artifacts(
        source_contract=source,
        require_registered_identities=False,
        **_route_parents(),
    )
    assert run.preregistration["decision"] == PREREGISTRATION_DECISION
    assert (
        len(run.preregistration["program"]["baseline_classes"])
        == len(BASELINE_CLASSES)
        == 3
    )
    assert run.execution_handoff["candidate_considerations_per_class"] == (
        CANDIDATE_CONSIDERATIONS_PER_CLASS
    )
    assert run.execution_handoff["total_candidate_considerations"] == (
        TOTAL_CANDIDATE_CONSIDERATIONS
    )
    assert run.execution_handoff["next_consumer"] == (
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
    )
    forbidden = {
        "duplicate_validation",
        "duplicate_check",
        "uniqueness_validation",
        "repeat_validation",
    }
    assert not forbidden.intersection(_recursive_keys(source))
    assert not forbidden.intersection(_recursive_keys(run.artifacts))


def test_preregistration_fails_closed_on_parent_semantic_drift() -> None:
    source = load_prediction_v2_structural_baseline_comparison_preregistration_source_contract(
        ROOT_DIR
        / PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    parents = _route_parents()
    changed = copy.deepcopy(parents["route_handoff"])
    changed["observed_result_may_define_thresholds"] = True
    identity = {
        key: value for key, value in changed.items() if key != "artifact_digest"
    }
    changed["artifact_digest"] = canonical_digest(
        identity,
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-"
            "preregistration-handoff.v1"
        ),
    )
    parents["route_handoff"] = changed
    with pytest.raises(
        PredictionV2StructuralBaselineComparisonPreregistrationError,
        match="parent_consistency_invalid",
    ):
        build_prediction_v2_structural_baseline_comparison_preregistration_artifacts(
            source_contract=source,
            require_registered_identities=False,
            **parents,
        )


def test_additive_migration_revises_preregistration_and_adds_only_execution() -> None:
    source = load_m4_manifest(MANIFEST_PATH).to_dict(include_digest=False)
    source["tasks"] = [
        item
        for item in source["tasks"]
        if item["task_key"]
        not in {
            "prediction-v2-structural-baseline-comparison-route-decision",
            "prediction-v2-next-result-blind-research-intake",
        }
    ]
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"]
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
    ]
    current = next(
        item
        for item in live["tasks"]
        if item["task_key"]
        == PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
    )
    current["requested_capability"] = None
    current["input_artifact_digests"] = []
    current["metric_contract"]["engineering_complete"] = False
    current["metric_contract"]["engineering_increment_percent"] = 0
    source_contract = load_prediction_v2_structural_baseline_comparison_preregistration_source_contract(
        ROOT_DIR
        / PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    source_fact = (
        "prediction-v2-structural-baseline-comparison-preregistration-source:"
        f"{source_contract['artifact_digest']}"
    )
    live["facts"]["artifacts"].remove(source_fact)
    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert len(migrated["tasks"]) == len(live["tasks"]) + 1


def test_status_routes_completed_preregistration_to_execution() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    tasks = {item.task_key: item for item in manifest.tasks}
    task_keys = (
        "prediction-v2-structural-portfolio-execution",
        "prediction-v2-structural-portfolio-evaluation",
        ROUTE_TASK_KEY,
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY,
    )
    completion_facts = (
        "prediction-v2-structural-portfolio-execution:COMPLETE",
        "prediction-v2-structural-portfolio-evaluation:COMPLETE",
        ROUTE_COMPLETION_FACT,
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_COMPLETION_FACT,
    )
    for item in payload["tasks"]:
        if item["task_key"] in task_keys:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            *completion_facts,
            *(
                mainline_completion_fact(task=tasks[key], execution_id=char * 64)
                for key, char in zip(task_keys, "abcd", strict=True)
            ),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": (
                PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
            ),
            "preregistration_decision": PREREGISTRATION_DECISION,
            "comparison_execution_authorized": True,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == (
        "PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION"
    )
    assert projection["live_mainline_status"] == (
        "PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_"
        "VALIDATED_IN_MAINLINE"
    )
    assert projection["next_consumer"] == (
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
    )
    preregistration = projection[
        "prediction_v2_structural_baseline_comparison_preregistration"
    ]
    assert preregistration["preregistration_complete"] is True
    assert preregistration["comparison_execution_authorized"] is True
    assert preregistration["next_consumer_resolver_status"] == "ready"


def test_supervisor_executes_and_replays_preregistration_without_workload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = load_prediction_v2_structural_baseline_comparison_preregistration_source_contract(
        ROOT_DIR
        / PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    for entry in source["source_entries"]:
        destination = tmp_path / str(entry["path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / str(entry["path"]), destination)
    contract_destination = (
        tmp_path
        / PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    contract_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT_DIR
        / PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_SOURCE_CONTRACT_PATH,
        contract_destination,
    )
    parents = _route_parents()
    synthetic = (
        build_prediction_v2_structural_baseline_comparison_preregistration_artifacts(
            source_contract=source,
            require_registered_identities=False,
            **parents,
        )
    )
    for key, digest in zip(
        ("route_execution", "route_decision", "route_handoff", "route_completion"),
        (
            ROUTE_EXECUTION_DIGEST,
            ROUTE_DECISION_DIGEST,
            ROUTE_HANDOFF_DIGEST,
            ROUTE_COMPLETION_DIGEST,
        ),
        strict=True,
    ):
        parents[key]["artifact_digest"] = digest
    parent_by_type = {
        "prediction_v2_structural_route_decision": parents["route_decision"],
        "prediction_v2_structural_baseline_comparison_preregistration_handoff": parents[
            "route_handoff"
        ],
        "prediction_v2_structural_route_decision_completion": parents[
            "route_completion"
        ],
    }
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, parents["route_execution"], []),
    )
    original_load_type = supervisor_module._load_registered_type

    def load_type(*, artifact_type: str, **kwargs: object) -> dict:
        if artifact_type in parent_by_type:
            return parent_by_type[artifact_type]
        return original_load_type(artifact_type=artifact_type, **kwargs)

    monkeypatch.setattr(supervisor_module, "_load_registered_type", load_type)
    monkeypatch.setattr(
        supervisor_module,
        "build_prediction_v2_structural_baseline_comparison_preregistration_artifacts",
        lambda **_: synthetic,
    )
    task = next(
        item
        for item in load_m4_manifest(MANIFEST_PATH).tasks
        if item.task_key
        == PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
    )
    result = PredictionV2StructuralBaselineComparisonPreregistrationCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="c" * 64,
        git_commit="d" * 40,
    )
    assert len(result.registrations) == 4
    assert result.execution_artifact["actual_fold_count"] == 0
    assert result.execution_artifact["baseline_proposals_executed"] == 0
    assert result.execution_artifact["result_blind"] is True

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
        "replay_prediction_v2_structural_baseline_comparison_preregistration",
        lambda **_: (
            synthetic,
            {
                "status": "REPLAY_VERIFIED",
                "same_registered_content": True,
                "workload_rerun": False,
                "folds_replayed": 0,
                "baseline_proposals_replayed": 0,
            },
        ),
    )
    replay = ResearchEvidenceSupervisor(
        repository=ReplayRepository(),
        root_dir=tmp_path,
        require_clean_tree=False,
    ).replay(
        task_key=(
            PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
        ),
        execution_id="c" * 64,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["workload_rerun"] is False
    assert capability_replay["baseline_proposals_replayed"] == 0


def test_latest_summary_and_artifact_index_use_preregistration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolutions = [
        type(
            "Resolution",
            (),
            {
                "task_key": (
                    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
                ),
                "status": TaskStatus.COMPLETED,
            },
        )()
    ]
    requested: list[str] = []

    def load_execution(**kwargs: object) -> tuple[dict, dict, tuple]:
        requested.append(str(kwargs["task_key"]))
        return (
            {"payload": [["registered_artifact_count", 4]]},
            {
                "artifact_digest": "1" * 64,
                "preregistration_decision": PREREGISTRATION_DECISION,
            },
            (),
        )

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        load_execution,
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    summary = supervisor._latest_completed_v2_summary(
        type("Snapshot", (), {"resolutions": resolutions})()
    )
    assert summary is not None
    assert requested == [
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
    ]
    assert summary["preregistration_decision"] == PREREGISTRATION_DECISION
    source = load_prediction_v2_structural_baseline_comparison_preregistration_source_contract(
        ROOT_DIR
        / PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[source["artifact_digest"]]["path"] == str(
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    manifest = load_m4_manifest(MANIFEST_PATH)
    assert index[manifest.artifact_digest]["identity_field"] == "manifest_digest"
    assert PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_CAPABILITY in (
        supervisor.capabilities
    )
