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
    PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_COMPLETION_FACT,
    PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY,
    build_prediction_v2_forward_or_pivot_artifacts,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_promotion_planner import (
    PREDICTION_V2_PROMOTION_PLANNER_COMPLETION_FACT,
    PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_structural_decision_support_design import (
    NULL_BASELINE,
    OPTIMIZATION_GEOMETRY,
    PENDING_PREREGISTRATION,
    PREDICTION_RESEARCH_DISPOSITION,
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_CAPABILITY,
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_COMPLETION_FACT,
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY,
    PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY,
    PredictionV2StructuralDesignError,
    build_prediction_v2_structural_design_artifacts,
    load_prediction_v2_structural_design_source_contract,
    verify_prediction_v2_structural_design_source_bytes,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    PredictionV2StructuralDecisionSupportDesignCapability,
    ResearchEvidenceSupervisor,
)
from test_prediction_v2_forward_evidence_or_pivot_planner import (
    _inputs as _forward_inputs,
)

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


def _contains_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list | tuple):
        return any(_contains_key(item, key) for item in value)
    return False


def _forward_summaries() -> tuple[dict, object]:
    forward = build_prediction_v2_forward_or_pivot_artifacts(
        **_forward_inputs(),
        require_registered_identities=False,
    )
    execution = _seal(
        {
            "artifact_type": "research_os_mainline_execution",
            "task_key": PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "registered_artifact_count": 4,
            "completion_fact": (
                PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_COMPLETION_FACT
            ),
            "prospective_evidence_feasibility_digest": forward.feasibility[
                "artifact_digest"
            ],
            "structural_decision_support_pivot_plan_digest": (
                forward.structural_pivot_plan["artifact_digest"]
            ),
            "forward_or_pivot_completion_digest": forward.completion["artifact_digest"],
            "historical_evidence": "INCONCLUSIVE",
            "selected_program": "STRUCTURAL_DECISION_SUPPORT_PIVOT",
            "prediction_research_disposition": PREDICTION_RESEARCH_DISPOSITION,
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "candidate_expert_authorized": False,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "formal_historical_folds_executed": 0,
            "bootstrap_children_executed": 0,
            "duplicate_validation": False,
            "evidence_created": False,
            "new_model_created": False,
            "structural_algorithm_implemented": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
        },
        domain="dehps.research-os.mainline-execution.v1",
    )
    return execution, forward


def _inputs() -> dict:
    execution, forward = _forward_summaries()
    return {
        "source_contract": load_prediction_v2_structural_design_source_contract(
            ROOT_DIR
            / PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_SOURCE_CONTRACT_PATH
        ),
        "forward_execution": execution,
        "feasibility": forward.feasibility,
        "structural_pivot_plan": forward.structural_pivot_plan,
        "forward_completion": forward.completion,
        "shadow_contract": load_shadow_contract(ROOT_DIR),
    }


def test_source_contract_uses_canonical_set_semantics_without_duplicate_validation() -> (
    None
):
    source = load_prediction_v2_structural_design_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_structural_design_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    frozen = source["frozen_contract"]
    assert not _contains_key(source, "duplicate_validation")
    assert frozen["legal_identity"]["legal_universe_cardinality"] == 1_107_568
    assert frozen["legal_identity"]["pair_universe_cardinality"] == 528
    decision = frozen["design_spec"]["decision_object"]
    assert decision["type"] == "unordered_fixed_budget_set_of_legal_combinations"
    assert decision["duplicate_handling"] == (
        "CANONICAL_SET_CONSTRUCTION_NO_VALIDATION_PASS"
    )


def test_builder_freezes_exact_pareto_geometry_and_no_duplicate_check() -> None:
    run = build_prediction_v2_structural_design_artifacts(
        **_inputs(),
        require_registered_identities=False,
    )
    assert len(run.artifacts) == 3
    assert not _contains_key(run.artifacts, "duplicate_validation")
    design = run.design_contract
    assert design["historical_evidence"] == "INCONCLUSIVE"
    assert design["legal_identity"]["legal_universe_formula"] == "C(33,6)"
    assert design["legal_identity"]["pair_universe_formula"] == "C(33,2)"
    spec = design["design_spec"]
    assert spec["optimization_geometry"]["type"] == OPTIMIZATION_GEOMETRY
    assert spec["optimization_geometry"]["weighted_score_allowed"] is False
    assert spec["null_baseline"]["type"] == NULL_BASELINE
    assert design["portfolio_budget_status"] == PENDING_PREREGISTRATION
    assert design["optimizer_status"] == PENDING_PREREGISTRATION
    assert all(item["candidate_portfolios_generated"] == 0 for item in run.artifacts)
    assert all(item["optimizers_executed"] == 0 for item in run.artifacts)


def test_builder_fails_closed_on_forward_execution_tamper() -> None:
    inputs = _inputs()
    execution = copy.deepcopy(inputs["forward_execution"])
    execution["selected_program"] = "FUTURE_EVIDENCE_PROGRAM"
    inputs["forward_execution"] = _seal(
        {key: value for key, value in execution.items() if key != "artifact_digest"},
        domain="dehps.research-os.mainline-execution.v1",
    )
    with pytest.raises(
        PredictionV2StructuralDesignError,
        match="parent_consistency_invalid",
    ):
        build_prediction_v2_structural_design_artifacts(
            **inputs,
            require_registered_identities=False,
        )


def test_additive_migration_revises_design_and_adds_only_preregistration() -> None:
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
        != PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
    ]
    design = next(
        item
        for item in live["tasks"]
        if item["task_key"] == PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY
    )
    design["requested_capability"] = None
    design["input_artifact_digests"] = []
    design["metric_contract"]["engineering_complete"] = False
    design["metric_contract"]["engineering_increment_percent"] = 0
    source_contract = load_prediction_v2_structural_design_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_SOURCE_CONTRACT_PATH
    )
    source_fact = (
        f"prediction-v2-structural-design-source:{source_contract['artifact_digest']}"
    )
    live["facts"]["artifacts"] = [
        fact for fact in live["facts"]["artifacts"] if fact != source_fact
    ]
    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert len(migrated["tasks"]) == len(live["tasks"]) + 1
    assert source_fact in migrated["facts"]["artifacts"]


def test_status_routes_completed_design_to_preregistration_without_duplicate_field() -> (
    None
):
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    task_keys = (
        MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
        PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
        PREDICTION_V2_FORWARD_EVIDENCE_OR_PIVOT_PLANNER_TASK_KEY,
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY,
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
            *(
                mainline_completion_fact(task=tasks[key], execution_id=char * 64)
                for key, char in zip(task_keys, "efdc", strict=True)
            ),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": (
                PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY
            ),
            "historical_evidence": "INCONCLUSIVE",
            "selected_program": "STRUCTURAL_DECISION_SUPPORT_PIVOT",
            "prediction_research_disposition": PREDICTION_RESEARCH_DISPOSITION,
            "legal_universe_cardinality": 1_107_568,
            "pair_universe_cardinality": 528,
            "optimization_geometry": OPTIMIZATION_GEOMETRY,
            "null_baseline": NULL_BASELINE,
            "portfolio_budget_status": PENDING_PREREGISTRATION,
            "optimizer_status": PENDING_PREREGISTRATION,
            "registered_artifact_count": 4,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == (
        "PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION"
    )
    assert projection["live_mainline_status"] == (
        "PREDICTION_V2_STRUCTURAL_DESIGN_VALIDATED_IN_MAINLINE"
    )
    assert projection["next_consumer"] == (
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
    )
    design = projection["prediction_v2_structural_decision_support_design"]
    assert design["resolver_status"] == "completed"
    assert design["next_consumer_resolver_status"] == "ready"
    assert "duplicate_validation" not in design


def test_supervisor_executes_and_replays_without_duplicate_validation(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = load_prediction_v2_structural_design_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_SOURCE_CONTRACT_PATH
    )
    for entry in source["source_entries"]:
        destination = tmp_path / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / entry["path"], destination)
    for relative in (
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_SOURCE_CONTRACT_PATH,
        CONTRACT_PATH,
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / relative, destination)

    forward_execution, forward = _forward_summaries()
    artifact_by_type = {item["artifact_type"]: item for item in forward.artifacts}
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, forward_execution, []),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda *, artifact_type, **_: artifact_by_type[artifact_type],
    )
    original_build = build_prediction_v2_structural_design_artifacts
    monkeypatch.setattr(
        supervisor_module,
        "build_prediction_v2_structural_design_artifacts",
        lambda **kwargs: original_build(
            **kwargs,
            require_registered_identities=False,
        ),
    )
    task = next(
        item
        for item in load_m4_manifest(MANIFEST_PATH).tasks
        if item.task_key == PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY
    )
    task = replace(
        task,
        input_artifact_digests=(
            source["artifact_digest"],
            forward_execution["artifact_digest"],
            *(str(item["artifact_digest"]) for item in forward.artifacts),
        ),
    )
    result = PredictionV2StructuralDecisionSupportDesignCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="b" * 64,
        git_commit="c" * 40,
    )
    assert len(result.registrations) == 4
    assert not _contains_key(result.execution_artifact, "duplicate_validation")
    assert all(
        not _contains_key(item, "duplicate_validation") for item in result.registrations
    )
    assert result.completion_facts == (
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_COMPLETION_FACT,
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
        task_key=PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_TASK_KEY,
        execution_id="b" * 64,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["same_registered_content"] is True
    assert not _contains_key(capability_replay, "duplicate_validation")
    assert capability_replay["next_consumer"] == (
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_PREREGISTRATION_TASK_KEY
    )


def test_artifact_index_and_supervisor_register_structural_design() -> None:
    source = load_prediction_v2_structural_design_source_contract(
        ROOT_DIR / PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_SOURCE_CONTRACT_PATH
    )
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    entry = index[source["artifact_digest"]]
    assert entry["path"] == str(
        PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_SOURCE_CONTRACT_PATH
    )
    assert entry["identity_field"] == "artifact_digest"
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert PREDICTION_V2_STRUCTURAL_DECISION_SUPPORT_DESIGN_CAPABILITY in (
        supervisor.capabilities
    )
