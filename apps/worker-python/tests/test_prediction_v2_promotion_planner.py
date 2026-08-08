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
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_promotion_planner import (
    PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY,
    PREDICTION_V2_PROMOTION_PLANNER_CAPABILITY,
    PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT,
    PREDICTION_V2_PROMOTION_PLANNER_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
    PredictionV2PromotionPlannerError,
    build_prediction_v2_promotion_planner_artifacts,
    load_prediction_v2_promotion_planner_source_contract,
    verify_prediction_v2_promotion_planner_source_bytes,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    PredictionV2PromotionPlannerCapability,
    ResearchEvidenceSupervisor,
)
from test_m4_v2_marginal_static_historical_gate import _run as _gate_run

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
INDEX_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"


def _seal(payload: dict, *, domain: str) -> dict:
    value = dict(payload)
    value["artifact_digest"] = ""
    identity = dict(value)
    identity.pop("artifact_digest")
    value["artifact_digest"] = canonical_digest(identity, domain=domain)
    return value


def _gate_execution(run) -> dict:
    evidence = run.historical_evidence
    eligible = evidence == "POSITIVE"
    return _seal(
        {
            "artifact_type": "research_os_mainline_execution",
            "task_key": MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "registered_artifact_count": 7,
            "completion_fact": MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT,
            "baseline_model_artifact_digest": run.baseline_model["artifact_digest"],
            "evaluated_model_artifact_digest": run.candidate_model["artifact_digest"],
            "accepted_model_artifact_digest": (
                run.candidate_model["artifact_digest"] if eligible else None
            ),
            "hierarchical_gate_output_digest": run.gate_output["artifact_digest"],
            "historical_evidence_artifact_digest": run.evidence["artifact_digest"],
            "promotion_planning_eligibility_digest": run.eligibility[
                "artifact_digest"
            ],
            "historical_gate_completion_digest": run.completion["artifact_digest"],
            "historical_evidence": evidence,
            "evidence_fact": run.evidence_fact,
            "prediction_v2_planning_eligible": eligible,
            "formal_historical_folds_executed": 0,
            "bootstrap_children_executed": 0,
            "database_queries_during_capability": 0,
            "duplicate_validation": False,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
        domain="dehps.research-os.mainline-execution.v1",
    )


def _planner_inputs(gate_run) -> dict:
    return {
        "source_contract": load_prediction_v2_promotion_planner_source_contract(
            ROOT_DIR / PREDICTION_V2_PROMOTION_PLANNER_SOURCE_CONTRACT_PATH
        ),
        "gate_execution": _gate_execution(gate_run),
        "baseline_model": gate_run.baseline_model,
        "evaluated_candidate_model": gate_run.candidate_model,
        "gate_output": gate_run.gate_output,
        "historical_evidence": gate_run.evidence,
        "planning_eligibility": gate_run.eligibility,
        "gate_completion": gate_run.completion,
        "shadow_contract": load_shadow_contract(ROOT_DIR),
    }


def test_source_contract_is_content_addressed_and_forbids_duplicate_validation() -> None:
    source = load_prediction_v2_promotion_planner_source_contract(
        ROOT_DIR / PREDICTION_V2_PROMOTION_PLANNER_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_promotion_planner_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    assert source["historical_rows_read"] == 0
    assert source["folds_executed"] == 0
    assert source["bootstrap_children_executed"] == 0
    assert source["duplicate_validation"] is False
    assert source["frozen_contract"]["duplicate_validation"] is False


@pytest.mark.parametrize(
    ("gate_kwargs", "expected_decision", "expected_route"),
    [
        (
            {
                "raw_p": 0.001,
                "lower": 0.02,
                "upper": 0.04,
                "equivalence_upper": 0.03,
                "mde": 0.005,
                "power_sufficient": True,
                "half_means": [0.02, 0.03],
            },
            "FORWARD_SHADOW_EVIDENCE_PLAN_ELIGIBLE",
            "FUTURE_ONLY_PREDICTION_V2_CANDIDATE_EVIDENCE",
        ),
        (
            {
                "raw_p": 0.5,
                "lower": -0.02,
                "upper": 0.009,
                "equivalence_upper": 0.008,
                "mde": 0.005,
                "power_sufficient": True,
                "half_means": [-0.001, 0.001],
            },
            "PREDICTIVE_PROMOTION_CLOSED",
            "STRUCTURAL_DECISION_SUPPORT_PIVOT_REVIEW",
        ),
        (
            {
                "raw_p": 0.5,
                "lower": -0.02,
                "upper": 0.009,
                "equivalence_upper": 0.008,
                "mde": 0.02,
                "power_sufficient": False,
                "half_means": [-0.001, 0.001],
            },
            "HOLD_BASELINE_ONLY",
            "FUTURE_EVIDENCE_OR_STRUCTURAL_PIVOT_REVIEW",
        ),
    ],
)
def test_exhaustive_route_mapping_uses_only_registered_summaries(
    gate_kwargs: dict,
    expected_decision: str,
    expected_route: str,
) -> None:
    inputs = _planner_inputs(_gate_run(**gate_kwargs))
    run = build_prediction_v2_promotion_planner_artifacts(
        **inputs,
        require_registered_identities=False,
    )
    assert run.plan_decision == expected_decision
    assert run.route == expected_route
    assert len(run.artifacts) == 3
    assert all(item["duplicate_validation"] is False for item in run.artifacts)
    assert run.promotion_plan["database_queries_during_capability"] == 0
    assert run.promotion_plan["historical_rows_read"] == 0
    assert run.promotion_plan["folds_executed"] == 0
    assert run.promotion_plan["bootstrap_children_executed"] == 0
    assert run.promotion_plan["prediction_v2_route"] == "BASELINE_ONLY"
    assert run.promotion_plan["candidate_expert_authorized"] is False
    assert run.promotion_plan["direct_promotion"] is False
    assert run.promotion_plan["promotion_gate_opened"] is False
    assert run.promotion_plan["p3_authorized"] is False


def test_planner_fails_closed_on_evidence_eligibility_mismatch() -> None:
    gate = _gate_run(
        raw_p=0.5,
        lower=-0.02,
        upper=0.009,
        equivalence_upper=0.008,
        mde=0.02,
        power_sufficient=False,
        half_means=[-0.001, 0.001],
    )
    inputs = _planner_inputs(gate)
    eligibility = copy.deepcopy(inputs["planning_eligibility"])
    eligibility["eligible_for_prediction_v2_promotion_planning"] = True
    eligibility = _seal(
        {key: value for key, value in eligibility.items() if key != "artifact_digest"},
        domain="dehps.prediction-v2.promotion-planning-eligibility.v1",
    )
    inputs["planning_eligibility"] = eligibility
    with pytest.raises(
        PredictionV2PromotionPlannerError,
        match="parent_consistency_invalid",
    ):
        build_prediction_v2_promotion_planner_artifacts(
            **inputs,
            require_registered_identities=False,
        )


def test_additive_migration_revises_only_planner_and_adds_one_consumer() -> None:
    source_payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source_payload.pop("manifest_digest")
    source = ControlPlaneManifest.from_dict(source_payload).to_dict(
        include_digest=False
    )
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"]
        != PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY
    ]
    planner = next(
        item
        for item in live["tasks"]
        if item["task_key"] == PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY
    )
    planner["requested_capability"] = None
    planner["input_artifact_digests"] = []
    planner["metric_contract"] = {
        key: value
        for key, value in planner["metric_contract"].items()
        if key
        not in {
            "registered_child_count",
            "database_queries_during_capability",
            "historical_rows_read",
            "formal_historical_folds_executed",
            "bootstrap_children_executed",
            "duplicate_validation",
            "prediction_v2_mode",
            "prediction_v2_route",
            "p3_authorized",
        }
    }
    planner["metric_contract"]["engineering_complete"] = False
    planner["metric_contract"]["engineering_increment_percent"] = 0
    source_contract = load_prediction_v2_promotion_planner_source_contract(
        ROOT_DIR / PREDICTION_V2_PROMOTION_PLANNER_SOURCE_CONTRACT_PATH
    )
    source_fact = (
        "prediction-v2-promotion-planner-source:"
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
            PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_status_projects_completed_planner_to_future_or_pivot_review() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    gate_task = next(
        item
        for item in manifest.tasks
        if item.task_key == MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY
    )
    planner_task = next(
        item
        for item in manifest.tasks
        if item.task_key == PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY
    )
    for item in payload["tasks"]:
        if item["task_key"] in {
            MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
            PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
        }:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT,
            "m4-v2-marginal-static-historical-evidence:INCONCLUSIVE",
            PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT,
            mainline_completion_fact(task=gate_task, execution_id="e" * 64),
            mainline_completion_fact(task=planner_task, execution_id="f" * 64),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
            "historical_evidence": "INCONCLUSIVE",
            "plan_decision": "HOLD_BASELINE_ONLY",
            "route": "FUTURE_EVIDENCE_OR_STRUCTURAL_PIVOT_REVIEW",
            "registered_artifact_count": 4,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == (
        "PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER"
    )
    assert projection["live_mainline_status"] == (
        "PREDICTION_V2_PROMOTION_PLANNER_VALIDATED_IN_MAINLINE"
    )
    assert projection["next_consumer"] == (
        PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY
    )
    planner = projection["prediction_v2_promotion_planner"]
    assert planner["completed"] is True
    assert planner["historical_evidence"] == "INCONCLUSIVE"
    assert planner["plan_decision"] == "HOLD_BASELINE_ONLY"
    assert planner["route"] == "FUTURE_EVIDENCE_OR_STRUCTURAL_PIVOT_REVIEW"
    assert planner["prediction_v2_route"] == "BASELINE_ONLY"
    assert planner["duplicate_validation"] is False
    assert planner["promotion_gate_opened"] is False
    assert planner["p3_authorized"] is False
    downstream = projection["prediction_v2_forward_evidence_or_pivot_planner"]
    assert downstream["resolver_status"] == "ready"
    assert downstream["promotion_plan_ready"] is True


def test_supervisor_executes_and_replays_planner_without_duplicate_validation(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = load_prediction_v2_promotion_planner_source_contract(
        ROOT_DIR / PREDICTION_V2_PROMOTION_PLANNER_SOURCE_CONTRACT_PATH
    )
    for entry in source["source_entries"]:
        destination = tmp_path / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / entry["path"], destination)
    for relative in (
        PREDICTION_V2_PROMOTION_PLANNER_SOURCE_CONTRACT_PATH,
        CONTRACT_PATH,
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / relative, destination)

    gate = _gate_run(
        raw_p=0.5,
        lower=-0.02,
        upper=0.009,
        equivalence_upper=0.008,
        mde=0.02,
        power_sufficient=False,
        half_means=[-0.001, 0.001],
    )
    gate_execution = _gate_execution(gate)
    artifact_by_type = {
        item["artifact_type"]: item for item in gate.artifacts
    }

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, gate_execution, []),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda *, artifact_type, **_: artifact_by_type[artifact_type],
    )
    original_build = build_prediction_v2_promotion_planner_artifacts
    monkeypatch.setattr(
        supervisor_module,
        "build_prediction_v2_promotion_planner_artifacts",
        lambda **kwargs: original_build(
            **kwargs,
            require_registered_identities=False,
        ),
    )
    task = next(
        item
        for item in load_m4_manifest(MANIFEST_PATH).tasks
        if item.task_key == PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY
    )
    expected_inputs = (
        source["artifact_digest"],
        gate_execution["artifact_digest"],
        *(str(item["artifact_digest"]) for item in gate.artifacts),
    )
    task = replace(task, input_artifact_digests=expected_inputs)
    result = PredictionV2PromotionPlannerCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="b" * 64,
        git_commit="c" * 40,
    )
    assert len(result.registrations) == 4
    assert result.execution_artifact["historical_evidence"] == "INCONCLUSIVE"
    assert result.execution_artifact["plan_decision"] == "HOLD_BASELINE_ONLY"
    assert result.execution_artifact["database_queries_during_capability"] == 0
    assert result.execution_artifact["historical_rows_read"] == 0
    assert result.execution_artifact["formal_historical_folds_executed"] == 0
    assert result.execution_artifact["bootstrap_children_executed"] == 0
    assert result.execution_artifact["duplicate_validation"] is False
    assert result.execution_artifact["evidence_created"] is False
    assert result.execution_artifact["promotion_gate_opened"] is False
    assert result.completion_facts == (
        PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT,
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
        task_key=PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
        execution_id="b" * 64,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["historical_evidence"] == "INCONCLUSIVE"
    assert capability_replay["database_queries_during_replay"] == 0
    assert capability_replay["historical_rows_read"] == 0
    assert capability_replay["formal_historical_folds_replayed"] == 0
    assert capability_replay["bootstrap_children_replayed"] == 0
    assert capability_replay["duplicate_validation"] is False
    assert capability_replay["evidence_created"] is False


def test_artifact_index_and_supervisor_register_planner() -> None:
    source = load_prediction_v2_promotion_planner_source_contract(
        ROOT_DIR / PREDICTION_V2_PROMOTION_PLANNER_SOURCE_CONTRACT_PATH
    )
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    entry = index[source["artifact_digest"]]
    assert entry["path"] == str(
        PREDICTION_V2_PROMOTION_PLANNER_SOURCE_CONTRACT_PATH
    )
    assert entry["identity_field"] == "artifact_digest"
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert PREDICTION_V2_PROMOTION_PLANNER_CAPABILITY in supervisor.capabilities
