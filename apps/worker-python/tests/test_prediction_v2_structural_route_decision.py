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
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_structural_route_decision import (
    ARCHIVE_CONDITION,
    EVALUATION_COMPLETION_DIGEST,
    EVALUATION_DECISION,
    EVALUATION_DECISION_DIGEST,
    EVALUATION_EXECUTION_DIGEST,
    EVALUATION_ROUTE_HANDOFF_DIGEST,
    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY,
    PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_CAPABILITY,
    PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_COMPLETION_FACT,
    PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY,
    ROUTE_DECISION,
    STRUCTURAL_ARTIFACT_ROLE,
    PredictionV2StructuralRouteDecisionError,
    build_prediction_v2_structural_route_decision_artifacts,
    load_prediction_v2_structural_route_decision_source_contract,
    verify_prediction_v2_structural_route_decision_source_bytes,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest, TaskStatus
from dehps.research_os.supervisor import (
    PredictionV2StructuralRouteDecisionCapability,
    ResearchEvidenceSupervisor,
)

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)
EVALUATION_TASK_KEY = "prediction-v2-structural-portfolio-evaluation"
EVALUATION_COMPLETION_FACT = "prediction-v2-structural-portfolio-evaluation:COMPLETE"


def _artifact(body: dict, *, domain: str) -> dict:
    payload = {"artifact_digest": "", **body}
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _evaluation_parents() -> dict[str, dict]:
    decision = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-structural-portfolio-evaluation-decision.v1"
            ),
            "artifact_type": ("prediction_v2_structural_portfolio_evaluation_decision"),
            "status": "COMPLETE",
            "decision": EVALUATION_DECISION,
            "hypothesis_scope": "FIXED_B176_OPTIMIZER_VERSUS_UNIFORM_SAME_BUDGET",
            "candidate_budget": 176,
            "selected_stats": {
                "singleton_square_sum": 33_796,
                "pair_square_sum": 14_152,
                "minimum_replacement_distance": 2,
                "sum_pairwise_replacement_distance": 76_030,
            },
            "selected_strictly_dominated_null_count": 4_096,
            "selected_null_strictly_dominating_count": 0,
            "p_value_claim": False,
            "global_optimality_claim": False,
            "decision_usefulness_claim": False,
            "prediction_probability_claim": False,
            "parent_digests": [],
        },
        domain="dehps.prediction-v2.structural-portfolio-evaluation-decision.v1",
    )
    handoff = _artifact(
        {
            "schema_version": "dehps-prediction-v2-structural-route-handoff.v1",
            "artifact_type": "prediction_v2_structural_route_handoff",
            "status": "COMPLETE",
            "evaluation_decision": EVALUATION_DECISION,
            "route_disposition": "ADVANCE_TO_SEPARATE_STRUCTURAL_ROUTE_DECISION",
            "portfolio_activation_authorized": False,
            "decision_usefulness_established": False,
            "next_consumer": PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY,
            "parent_digests": [decision["artifact_digest"]],
        },
        domain="dehps.prediction-v2.structural-route-handoff.v1",
    )
    completion = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-structural-portfolio-evaluation-completion.v1"
            ),
            "artifact_type": (
                "prediction_v2_structural_portfolio_evaluation_completion"
            ),
            "status": "COMPLETE",
            "completion_fact": EVALUATION_COMPLETION_FACT,
            "evaluation_decision_digest": decision["artifact_digest"],
            "route_handoff_digest": handoff["artifact_digest"],
            "decision": EVALUATION_DECISION,
            "route_disposition": "ADVANCE_TO_SEPARATE_STRUCTURAL_ROUTE_DECISION",
            "next_consumer": PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY,
            "parent_digests": [
                decision["artifact_digest"],
                handoff["artifact_digest"],
            ],
        },
        domain=("dehps.prediction-v2.structural-portfolio-evaluation-completion.v1"),
    )
    execution = _artifact(
        {
            "schema_version": "dehps-research-os-mainline-execution.v1",
            "artifact_type": "research_os_mainline_execution",
            "task_key": EVALUATION_TASK_KEY,
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "completion_fact": EVALUATION_COMPLETION_FACT,
            "evaluation_decision": EVALUATION_DECISION,
            "route_disposition": "ADVANCE_TO_SEPARATE_STRUCTURAL_ROUTE_DECISION",
            "structural_evaluation_decision_digest": decision["artifact_digest"],
            "structural_route_handoff_digest": handoff["artifact_digest"],
            "structural_evaluation_completion_digest": completion["artifact_digest"],
            "decision_usefulness_claim": False,
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
        "evaluation_execution": execution,
        "evaluation_decision": decision,
        "evaluation_route_handoff": handoff,
        "evaluation_completion": completion,
    }


def _recursive_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(
            *(_recursive_keys(item) for item in value.values()), set()
        )
    if isinstance(value, list):
        return set().union(*(_recursive_keys(item) for item in value), set())
    return set()


def test_source_contract_and_route_artifacts_are_bounded_and_zero_work() -> None:
    source = load_prediction_v2_structural_route_decision_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_structural_route_decision_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    run = build_prediction_v2_structural_route_decision_artifacts(
        source_contract=source,
        require_registered_identities=False,
        **_evaluation_parents(),
    )
    assert run.decision["decision"] == ROUTE_DECISION
    assert run.decision["structural_artifact_role"] == STRUCTURAL_ARTIFACT_ROLE
    assert run.decision["archive_condition"] == ARCHIVE_CONDITION
    assert run.decision["stronger_baseline_comparison_required"] is True
    assert run.decision["portfolio_activation_authorized"] is False
    assert run.baseline_preregistration_handoff["baseline_classes_frozen"] is False
    assert (
        run.baseline_preregistration_handoff["comparison_execution_authorized"] is False
    )
    assert run.completion["next_consumer"] == (
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
    )
    assert not {
        "duplicate_validation",
        "duplicate_check",
        "uniqueness_validation",
    }.intersection(_recursive_keys(run.artifacts))


def test_route_decision_fails_closed_on_parent_semantic_drift() -> None:
    source = load_prediction_v2_structural_route_decision_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_SOURCE_CONTRACT_PATH
    )
    parents = _evaluation_parents()
    changed = copy.deepcopy(parents["evaluation_decision"])
    changed["candidate_budget"] = 175
    identity = {
        key: value for key, value in changed.items() if key != "artifact_digest"
    }
    changed["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.prediction-v2.structural-portfolio-evaluation-decision.v1",
    )
    parents["evaluation_decision"] = changed
    with pytest.raises(
        PredictionV2StructuralRouteDecisionError,
        match="parent_consistency_invalid",
    ):
        build_prediction_v2_structural_route_decision_artifacts(
            source_contract=source,
            require_registered_identities=False,
            **parents,
        )


def test_additive_migration_revises_route_and_adds_only_baseline_preregistration() -> (
    None
):
    source_manifest = load_m4_manifest(MANIFEST_PATH)
    source = source_manifest.to_dict(include_digest=False)
    source["tasks"] = [
        item
        for item in source["tasks"]
        if item["task_key"]
        not in {
            "prediction-v2-structural-baseline-comparison-execution",
            "prediction-v2-structural-baseline-comparison-route-decision",
            "prediction-v2-next-result-blind-research-intake",
        }
    ]
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"]
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
    ]
    route = next(
        item
        for item in live["tasks"]
        if item["task_key"] == PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY
    )
    route["requested_capability"] = None
    route["input_artifact_digests"] = []
    route["metric_contract"]["engineering_complete"] = False
    route["metric_contract"]["engineering_increment_percent"] = 0
    source_contract = load_prediction_v2_structural_route_decision_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_SOURCE_CONTRACT_PATH
    )
    source_fact = (
        "prediction-v2-structural-route-decision-source:"
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
            PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert len(migrated["tasks"]) == len(live["tasks"]) + 1 == 67


def test_status_routes_completed_decision_to_baseline_preregistration() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    tasks = {item.task_key: item for item in manifest.tasks}
    task_keys = (
        "prediction-v2-structural-portfolio-execution",
        EVALUATION_TASK_KEY,
        PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY,
    )
    for item in payload["tasks"]:
        if item["task_key"] in task_keys:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            "prediction-v2-structural-portfolio-execution:COMPLETE",
            EVALUATION_COMPLETION_FACT,
            PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_COMPLETION_FACT,
            *(
                mainline_completion_fact(task=tasks[key], execution_id=char * 64)
                for key, char in zip(task_keys, "abc", strict=True)
            ),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY,
            "route_decision": ROUTE_DECISION,
            "structural_artifact_role": STRUCTURAL_ARTIFACT_ROLE,
            "archive_condition": ARCHIVE_CONDITION,
            "stronger_baseline_comparison_required": True,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == (
        "PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION"
    )
    assert projection["live_mainline_status"] == (
        "PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_VALIDATED_IN_MAINLINE"
    )
    assert projection["next_consumer"] == (
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_PREREGISTRATION_TASK_KEY
    )
    route = projection["prediction_v2_structural_route_decision"]
    assert route["route_complete"] is True
    assert route["route_decision"] == ROUTE_DECISION
    assert route["next_consumer_resolver_status"] == "ready"


def test_latest_v2_summary_prefers_route_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolutions = [
        type(
            "Resolution",
            (),
            {
                "task_key": EVALUATION_TASK_KEY,
                "status": TaskStatus.COMPLETED,
            },
        )(),
        type(
            "Resolution",
            (),
            {
                "task_key": PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY,
                "status": TaskStatus.COMPLETED,
            },
        )(),
    ]
    requested: list[str] = []
    execution = {
        "artifact_digest": "1" * 64,
        "route_decision": ROUTE_DECISION,
        "structural_artifact_role": STRUCTURAL_ARTIFACT_ROLE,
    }
    event = {"payload": [["registered_artifact_count", 4]]}

    def load_execution(**kwargs: object) -> tuple[dict, dict, tuple]:
        requested.append(str(kwargs["task_key"]))
        return event, execution, ()

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        load_execution,
    )
    summary = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )._latest_completed_v2_summary(type("Snapshot", (), {"resolutions": resolutions})())
    assert summary is not None
    assert requested == [PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY]
    assert summary["execution_task_key"] == (
        PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY
    )
    assert summary["route_decision"] == ROUTE_DECISION
    assert summary["registered_artifact_count"] == 4


def test_supervisor_executes_and_replays_route_without_workload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = load_prediction_v2_structural_route_decision_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_SOURCE_CONTRACT_PATH
    )
    for entry in source["source_entries"]:
        destination = tmp_path / str(entry["path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / str(entry["path"]), destination)
    contract_destination = (
        tmp_path / PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_SOURCE_CONTRACT_PATH
    )
    contract_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_SOURCE_CONTRACT_PATH,
        contract_destination,
    )
    parents = _evaluation_parents()
    for key, digest in zip(
        (
            "evaluation_execution",
            "evaluation_decision",
            "evaluation_route_handoff",
            "evaluation_completion",
        ),
        (
            EVALUATION_EXECUTION_DIGEST,
            EVALUATION_DECISION_DIGEST,
            EVALUATION_ROUTE_HANDOFF_DIGEST,
            EVALUATION_COMPLETION_DIGEST,
        ),
        strict=True,
    ):
        parents[key]["artifact_digest"] = digest
    parent_by_type = {
        "prediction_v2_structural_portfolio_evaluation_decision": parents[
            "evaluation_decision"
        ],
        "prediction_v2_structural_route_handoff": parents["evaluation_route_handoff"],
        "prediction_v2_structural_portfolio_evaluation_completion": parents[
            "evaluation_completion"
        ],
    }
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, parents["evaluation_execution"], []),
    )
    original_load_type = supervisor_module._load_registered_type

    def load_type(*, artifact_type: str, **kwargs: object) -> dict:
        if artifact_type in parent_by_type:
            return parent_by_type[artifact_type]
        return original_load_type(artifact_type=artifact_type, **kwargs)

    monkeypatch.setattr(supervisor_module, "_load_registered_type", load_type)
    synthetic = build_prediction_v2_structural_route_decision_artifacts(
        source_contract=source,
        require_registered_identities=False,
        **_evaluation_parents(),
    )
    monkeypatch.setattr(
        supervisor_module,
        "build_prediction_v2_structural_route_decision_artifacts",
        lambda **_: synthetic,
    )
    task = next(
        item
        for item in load_m4_manifest(MANIFEST_PATH).tasks
        if item.task_key == PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY
    )
    result = PredictionV2StructuralRouteDecisionCapability(
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
    assert result.execution_artifact["optimizer_proposals_executed"] == 0
    assert result.execution_artifact["route_decision"] == ROUTE_DECISION

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
        "replay_prediction_v2_structural_route_decision",
        lambda **_: (
            synthetic,
            {
                "status": "REPLAY_VERIFIED",
                "same_registered_content": True,
                "workload_rerun": False,
                "folds_replayed": 0,
                "optimizer_proposals_replayed": 0,
                "null_replicates_replayed": 0,
            },
        ),
    )
    replay = ResearchEvidenceSupervisor(
        repository=ReplayRepository(),
        root_dir=tmp_path,
        require_clean_tree=False,
    ).replay(
        task_key=PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY,
        execution_id="c" * 64,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["workload_rerun"] is False
    assert capability_replay["optimizer_proposals_replayed"] == 0
    assert capability_replay["null_replicates_replayed"] == 0


def test_artifact_index_capability_and_deterministic_children() -> None:
    source = load_prediction_v2_structural_route_decision_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_SOURCE_CONTRACT_PATH
    )
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[source["artifact_digest"]]["path"] == str(
        PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_SOURCE_CONTRACT_PATH
    )
    manifest = load_m4_manifest(MANIFEST_PATH)
    assert index[manifest.artifact_digest]["identity_field"] == "manifest_digest"
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_CAPABILITY in (
        supervisor.capabilities
    )
    parents = _evaluation_parents()
    first = build_prediction_v2_structural_route_decision_artifacts(
        source_contract=source,
        require_registered_identities=False,
        **parents,
    )
    rebuilt = build_prediction_v2_structural_route_decision_artifacts(
        source_contract=source,
        require_registered_identities=False,
        **parents,
    )
    assert rebuilt.artifacts == first.artifacts
