from __future__ import annotations

import copy
import json
import shutil
from dataclasses import asdict, replace

import pytest
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.prediction.v2.contracts import CONTRACT_PATH, load_shadow_contract
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_historical_gate import (
    MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT,
    MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_forward_evidence_or_pivot_planner import (
    HISTORICAL_EVIDENCE_DIGEST,
    PREDICTION_RESEARCH_DISPOSITION,
    PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_CAPABILITY,
    PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_COMPLETION_FACT,
    PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY,
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY,
    PredictionV2ForwardOrPivotPlannerError,
    build_prediction_v2_forward_or_pivot_artifacts,
    load_prediction_v2_forward_or_pivot_source_contract,
    verify_prediction_v2_forward_or_pivot_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_promotion_planner import (
    PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT,
    PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
    build_prediction_v2_promotion_planner_artifacts,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    PredictionV2ForwardEvidenceOrPivotPlannerCapability,
    ResearchEvidenceSupervisor,
)
from test_m4_v2_marginal_static_historical_gate import _run as _gate_run
from test_prediction_v2_promotion_planner import _planner_inputs

MANIFEST_PATH = ROOT_DIR / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)


def _seal(payload: dict, *, domain: str) -> dict:
    value = dict(payload)
    value["artifact_digest"] = ""
    identity = dict(value)
    identity.pop("artifact_digest")
    value["artifact_digest"] = canonical_digest(identity, domain=domain)
    return value


def _promotion_summaries() -> tuple[dict, object]:
    gate = _gate_run(
        raw_p=0.5,
        lower=-0.02,
        upper=0.009,
        equivalence_upper=0.008,
        mde=0.02,
        power_sufficient=False,
        half_means=[-0.001, 0.001],
    )
    promotion = build_prediction_v2_promotion_planner_artifacts(
        **_planner_inputs(gate),
        require_registered_identities=False,
    )
    execution = _seal(
        {
            "artifact_type": "research_os_mainline_execution",
            "task_key": PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "registered_artifact_count": 4,
            "completion_fact": PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT,
            "promotion_plan_digest": promotion.promotion_plan["artifact_digest"],
            "downstream_route_digest": promotion.downstream_route["artifact_digest"],
            "promotion_planner_completion_digest": promotion.completion[
                "artifact_digest"
            ],
            "historical_evidence_artifact_digest": HISTORICAL_EVIDENCE_DIGEST,
            "historical_evidence": "INCONCLUSIVE",
            "plan_decision": "HOLD_BASELINE_ONLY",
            "route": "FUTURE_EVIDENCE_OR_STRUCTURAL_PIVOT_REVIEW",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "candidate_expert_authorized": False,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "formal_historical_folds_executed": 0,
            "bootstrap_children_executed": 0,
            "duplicate_validation": False,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
        },
        domain="dehps.research-os.mainline-execution.v1",
    )
    return execution, promotion


def _inputs() -> dict:
    execution, promotion = _promotion_summaries()
    return {
        "source_contract": load_prediction_v2_forward_or_pivot_source_contract(
            ROOT_DIR
            / PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_SOURCE_CONTRACT_PATH
        ),
        "promotion_execution": execution,
        "promotion_plan": promotion.promotion_plan,
        "upstream_route": promotion.downstream_route,
        "promotion_completion": promotion.completion,
        "shadow_contract": load_shadow_contract(ROOT_DIR),
    }


def test_source_contract_and_projection_are_content_addressed_zero_work() -> None:
    source = load_prediction_v2_forward_or_pivot_source_contract(
        ROOT_DIR / PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_forward_or_pivot_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    frozen = source["frozen_contract"]
    projection = frozen["planning_projection"]
    assert projection["required_total_issues"] == 4676
    assert projection["additional_issues_required"] == 2095
    assert projection["operational_horizon_days"] == 14
    assert projection["maximum_new_issues_in_horizon"] == 6
    assert projection["projected_mde_after_horizon_bits_per_issue"] == pytest.approx(
        0.01344429029293817
    )
    assert frozen["formal_power_claim"] is False
    assert frozen["selected_program"] == "STRUCTURAL_DECISION_SUPPORT_PIVOT"
    assert source["historical_rows_read"] == 0
    assert source["folds_executed"] == 0
    assert source["bootstrap_children_executed"] == 0
    assert source["duplicate_validation"] is False


def test_builder_selects_structural_pivot_without_relabelling_evidence() -> None:
    run = build_prediction_v2_forward_or_pivot_artifacts(
        **_inputs(),
        require_registered_identities=False,
    )
    assert len(run.artifacts) == 3
    assert run.selected_program == "STRUCTURAL_DECISION_SUPPORT_PIVOT"
    assert run.feasibility["historical_evidence"] == "INCONCLUSIVE"
    assert run.feasibility["classification"] == (
        "NON_EVIDENTIARY_SAME_LAW_SQUARE_ROOT_PROJECTION"
    )
    assert run.feasibility["formal_power_claim"] is False
    assert run.feasibility["candidate_forward_evidence_eligible"] is False
    assert run.structural_pivot_plan["prediction_research_disposition"] == (
        PREDICTION_RESEARCH_DISPOSITION
    )
    assert run.structural_pivot_plan["structural_algorithm_implemented"] is False
    assert run.structural_pivot_plan["prediction_v2_route"] == "BASELINE_ONLY"
    assert all(item["duplicate_validation"] is False for item in run.artifacts)
    assert all(item["new_evidence_created"] is False for item in run.artifacts)


def test_builder_fails_closed_on_upstream_route_tamper() -> None:
    inputs = _inputs()
    route = copy.deepcopy(inputs["upstream_route"])
    route["selected_route"] = "FUTURE_ONLY_PREDICTION_V2_CANDIDATE_EVIDENCE"
    route = _seal(
        {key: value for key, value in route.items() if key != "artifact_digest"},
        domain="dehps.prediction-v2.forward-evidence-or-pivot-route.v1",
    )
    inputs["upstream_route"] = route
    with pytest.raises(
        PredictionV2ForwardOrPivotPlannerError,
        match="parent_consistency_invalid",
    ):
        build_prediction_v2_forward_or_pivot_artifacts(
            **inputs,
            require_registered_identities=False,
        )


def test_additive_migration_revises_only_planner_and_adds_structural_design() -> None:
    source_payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source_payload.pop("manifest_digest")
    source = ControlPlaneManifest.from_dict(source_payload).to_dict(
        include_digest=False
    )
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY
    ]
    planner = next(
        item
        for item in live["tasks"]
        if item["task_key"] == PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY
    )
    planner["requested_capability"] = None
    planner["input_artifact_digests"] = []
    planner["metric_contract"] = {
        "engineering_complete": False,
        "engineering_increment_percent": 0,
        "evidence_complete": False,
        "evidence_increment_percent": 0,
        "phase": "PREDICTION-V2-FORWARD-EVIDENCE-OR-PIVOT-PLANNER",
        "scope": (
            "choose_a_separately_preregistered_future_evidence_program_or_"
            "structural_decision_support_pivot_without_relabelling_inconclusive_evidence"
        ),
        "reason": (
            "the_frozen_promotion_planner_holds_BASELINE_ONLY_and_routes_the_"
            "unresolved_measurement_question_to_a_separate_prospective_contract"
        ),
        "mainline_integration": {
            "goal": "M4_INFORMATION_THEORY_EVIDENCE",
            "ready_condition": (
                "the_prediction_v2_promotion_plan_and_route_are_"
                "VALIDATED_IN_MAINLINE_and_replay_verified"
            ),
            "runner": "research_evidence_supervisor",
            "upstream_artifacts": [
                "Prediction v2 promotion plan",
                "forward-evidence or structural-pivot route",
                "promotion-planner replay proof",
            ],
            "downstream_artifacts": [
                "separately preregistered prospective evidence plan or structural decision-support pivot plan"
            ],
            "status_projection": "unified_m4_status.measurement_system_v2.prediction_v2_forward_evidence_or_pivot_planner",
            "evidence_progress_rule": (
                "planning_does_not_create_evidence_or_authorize_an_expert"
            ),
            "decision_consumer": (
                "separately authorized future-evidence executor or structural decision-support design task"
            ),
            "downstream_consumer": "to_be_selected_by_the_frozen_route_review",
        },
        "evidence_created": False,
        "duplicate_validation": False,
        "promotion_gate_opened": False,
        "p3_authorized": False,
        "production_action": "none",
    }
    contract = load_prediction_v2_forward_or_pivot_source_contract(
        ROOT_DIR / PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_SOURCE_CONTRACT_PATH
    )
    source_fact = (
        f"prediction-v2-forward-or-pivot-planner-source:{contract['artifact_digest']}"
    )
    live["facts"]["artifacts"] = [
        fact for fact in live["facts"]["artifacts"] if fact != source_fact
    ]
    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_status_projects_completed_planner_to_structural_design() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    task_keys = (
        MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
        PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
        PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY,
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
            *(
                mainline_completion_fact(task=tasks[key], execution_id=char * 64)
                for key, char in zip(task_keys, "efd", strict=True)
            ),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": (
                PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY
            ),
            "historical_evidence": "INCONCLUSIVE",
            "upstream_plan_decision": "HOLD_BASELINE_ONLY",
            "upstream_route": "FUTURE_EVIDENCE_OR_STRUCTURAL_PIVOT_REVIEW",
            "selected_program": "STRUCTURAL_DECISION_SUPPORT_PIVOT",
            "prediction_research_disposition": PREDICTION_RESEARCH_DISPOSITION,
            "projection_classification": (
                "NON_EVIDENTIARY_SAME_LAW_SQUARE_ROOT_PROJECTION"
            ),
            "required_total_issues": 4676,
            "additional_issues_required": 2095,
            "operational_horizon_days": 14,
            "projected_mde_after_horizon_bits_per_issue": (0.01344429029293817),
            "registered_artifact_count": 4,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == ("PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN")
    assert projection["live_mainline_status"] == (
        "PREDICTION_V2_FORWARD_OR_PIVOT_VALIDATED_IN_MAINLINE"
    )
    assert projection["next_consumer"] == (
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY
    )
    planner = projection["prediction_v2_forward_evidence_or_pivot_planner"]
    assert planner["resolver_status"] == "completed"
    assert planner["selected_program"] == "STRUCTURAL_DECISION_SUPPORT_PIVOT"
    assert planner["formal_power_claim"] is False
    assert planner["required_total_issues"] == 4676
    assert planner["additional_issues_required"] == 2095
    assert planner["next_consumer_resolver_status"] == "ready"
    assert planner["duplicate_validation"] is False
    assert planner["promotion_gate_opened"] is False


def test_supervisor_executes_and_replays_without_duplicate_validation(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = load_prediction_v2_forward_or_pivot_source_contract(
        ROOT_DIR / PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_SOURCE_CONTRACT_PATH
    )
    for entry in source["source_entries"]:
        destination = tmp_path / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / entry["path"], destination)
    for relative in (
        PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_SOURCE_CONTRACT_PATH,
        CONTRACT_PATH,
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / relative, destination)

    promotion_execution, promotion = _promotion_summaries()
    artifact_by_type = {item["artifact_type"]: item for item in promotion.artifacts}
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, promotion_execution, []),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda *, artifact_type, **_: artifact_by_type[artifact_type],
    )
    original_build = build_prediction_v2_forward_or_pivot_artifacts
    monkeypatch.setattr(
        supervisor_module,
        "build_prediction_v2_forward_or_pivot_artifacts",
        lambda **kwargs: original_build(
            **kwargs,
            require_registered_identities=False,
        ),
    )
    task = next(
        item
        for item in load_m4_manifest(MANIFEST_PATH).tasks
        if item.task_key == PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY
    )
    expected_inputs = (
        source["artifact_digest"],
        promotion_execution["artifact_digest"],
        *(str(item["artifact_digest"]) for item in promotion.artifacts),
    )
    task = replace(task, input_artifact_digests=expected_inputs)
    result = PredictionV2ForwardEvidenceOrPivotPlannerCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="b" * 64,
        git_commit="c" * 40,
    )
    artifact = result.execution_artifact
    assert len(result.registrations) == 4
    assert artifact["selected_program"] == "STRUCTURAL_DECISION_SUPPORT_PIVOT"
    assert artifact["projection_classification"] == (
        "NON_EVIDENTIARY_SAME_LAW_SQUARE_ROOT_PROJECTION"
    )
    assert artifact["formal_power_claim"] is False
    assert artifact["required_total_issues"] == 4676
    assert artifact["additional_issues_required"] == 2095
    assert artifact["database_queries_during_capability"] == 0
    assert artifact["historical_rows_read"] == 0
    assert artifact["formal_historical_folds_executed"] == 0
    assert artifact["bootstrap_children_executed"] == 0
    assert artifact["duplicate_validation"] is False
    assert artifact["evidence_created"] is False
    assert artifact["new_model_created"] is False
    assert artifact["structural_algorithm_implemented"] is False
    assert result.completion_facts == (
        PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_COMPLETION_FACT,
    )

    class ReplayRepository:
        def list_mainline_execution_events(self, **_: object) -> list[dict]:
            return [
                {
                    "event_type": "completed",
                    "execution_id": "b" * 64,
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

    replay = ResearchEvidenceSupervisor(
        repository=ReplayRepository(),
        root_dir=tmp_path,
        require_clean_tree=False,
    ).replay(
        task_key=PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY,
        execution_id="b" * 64,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["selected_program"] == (
        "STRUCTURAL_DECISION_SUPPORT_PIVOT"
    )
    assert capability_replay["formal_power_claim"] is False
    assert capability_replay["database_queries_during_replay"] == 0
    assert capability_replay["historical_rows_read"] == 0
    assert capability_replay["formal_historical_folds_replayed"] == 0
    assert capability_replay["bootstrap_children_replayed"] == 0
    assert capability_replay["duplicate_validation"] is False
    assert capability_replay["evidence_created"] is False


def test_artifact_index_and_supervisor_register_planner() -> None:
    source = load_prediction_v2_forward_or_pivot_source_contract(
        ROOT_DIR / PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_SOURCE_CONTRACT_PATH
    )
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    entry = index[source["artifact_digest"]]
    assert entry["path"] == str(
        PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_SOURCE_CONTRACT_PATH
    )
    assert entry["identity_field"] == "artifact_digest"
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert (
        PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_CAPABILITY
        in supervisor.capabilities
    )
