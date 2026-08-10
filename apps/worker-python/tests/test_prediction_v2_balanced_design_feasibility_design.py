from __future__ import annotations

import copy
import json

import pytest
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2 import (
    prediction_v2_balanced_design_feasibility_design as design_module,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_feasibility_design import (
    ARCHIVE_ROUTE_COMPLETION_DIGEST,
    BOUNDED_NEGATIVE_OUTCOME,
    FAILED_ERROR,
    FAILED_EXECUTION_ID,
    FAILED_SOURCE_CONTRACT_DIGEST,
    FAILED_TASK_DIGEST,
    INVALID_OUTCOME,
    POSITIVE_OUTCOME,
    PREDICTION_V2_APPROVED_RESULT_BLIND_RESEARCH_CONTRACT_EVENT,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_CAPABILITY,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_COMPLETION_FACT,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY,
    REPETITION_SCAN,
    PredictionV2BalancedDesignFeasibilityDesignError,
    PredictionV2BalancedDesignFeasibilityRecoveryError,
    build_prediction_v2_balanced_design_feasibility_artifacts,
    build_prediction_v2_balanced_design_feasibility_recovery_manifest,
    load_prediction_v2_balanced_design_feasibility_source_contract,
    replay_prediction_v2_balanced_design_feasibility,
    verify_prediction_v2_balanced_design_feasibility_source_bytes,
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
ROUTE_TASK_KEY = "prediction-v2-structural-baseline-comparison-route-decision"
ROUTE_COMPLETION_FACT = (
    "prediction-v2-structural-baseline-comparison-route-decision:COMPLETE"
)
ROUTE_DECISION = (
    "ARCHIVE_B176_FROM_ACTIVATION_AND_WAIT_FOR_NEW_RESULT_BLIND_RESEARCH_CONTRACT"
)
SOURCE_FACT_PREFIX = "prediction-v2-balanced-design-feasibility-source:"


def _artifact(body: dict, *, domain: str) -> dict:
    payload = {"artifact_digest": "", **body}
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _parents() -> dict[str, object]:
    route_digest = "a" * 64
    handoff = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-result-blind-research-intake-handoff.v1"
            ),
            "artifact_type": "prediction_v2_result_blind_research_intake_handoff",
            "status": "COMPLETE",
            "route_decision": ROUTE_DECISION,
            "structural_artifact_role": (
                "ARCHIVED_NON_PREDICTIVE_ENGINEERING_REFERENCE_ONLY"
            ),
            "prediction_research_disposition": "FROZEN_NO_ACCEPTED_CANDIDATE",
            "intake_task": PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY,
            "required_external_event": (
                PREDICTION_V2_APPROVED_RESULT_BLIND_RESEARCH_CONTRACT_EVENT
            ),
            "state_before_external_event": "EXTERNAL_WAIT",
            "result_blind_contract_required": True,
            "requested_capability_before_event": None,
            "automatic_hypothesis_generation": False,
            "automatic_threshold_relaxation": False,
            "automatic_seed_retry": False,
            "automatic_portfolio_mutation": False,
            "legacy_route_fallback": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "new_evidence_created": False,
            "new_model_created": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
            "repetition_scan": REPETITION_SCAN,
            "parent_digests": [],
        },
        domain="dehps.prediction-v2.result-blind-research-intake-handoff.v1",
    )
    completion = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-structural-baseline-comparison-"
                "route-decision-completion.v1"
            ),
            "artifact_type": (
                "prediction_v2_structural_baseline_comparison_route_decision_completion"
            ),
            "status": "COMPLETE",
            "completion_fact": ROUTE_COMPLETION_FACT,
            "route_decision_digest": route_digest,
            "research_intake_handoff_digest": handoff["artifact_digest"],
            "decision": ROUTE_DECISION,
            "next_external_event": (
                PREDICTION_V2_APPROVED_RESULT_BLIND_RESEARCH_CONTRACT_EVENT
            ),
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "portfolio_activation_authorized": False,
            "new_evidence_created": False,
            "new_model_created": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
            "repetition_scan": REPETITION_SCAN,
            "parent_digests": [route_digest, handoff["artifact_digest"]],
        },
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-"
            "route-decision-completion.v1"
        ),
    )
    return {
        "archive_route_decision_digest": route_digest,
        "research_intake_handoff": handoff,
        "archive_route_completion": completion,
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
    source = load_prediction_v2_balanced_design_feasibility_source_contract(
        ROOT_DIR / PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_balanced_design_feasibility_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    return source


def _historical_recovery_base() -> dict:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload.pop("manifest_digest")
    payload["goals"] = [
        item
        for item in payload["goals"]
        if item["goal_key"] != "M4_P3_RESULT_BLIND_STRUCTURAL_UTILITY"
    ]
    payload["tasks"] = [
        item
        for item in payload["tasks"]
        if item["task_key"]
        not in {
            "prediction-v2-balanced-design-feasibility-execution",
            "prediction-v2-balanced-design-feasibility-result-decision",
            "prediction-v2-balanced-design-structural-evaluation-design",
            "prediction-v2-balanced-design-structural-evaluation-preregistration",
            "prediction-v2-balanced-design-structural-evaluation-execution",
            "prediction-v2-balanced-design-structural-evaluation-result-decision",
            "prediction-v2-balanced-design-structural-utility-research-intake",
            "m4-p3-result-blind-structural-utility-preregistration",
            "m4-p3-result-blind-structural-utility-blind-generator-and-walk-forward",
            "m4-p3-result-blind-structural-utility-evidence-compiler",
            "m4-p2r-measurement-repair-validation",
        }
    ]
    payload["facts"]["artifacts"] = [
        fact
        for fact in payload["facts"]["artifacts"]
        if not fact.startswith(
            "m4-p3-result-blind-structural-utility-design-source:"
        )
        and not fact.startswith(
            "m4-p3-result-blind-structural-utility-preregistration-source:"
        )
        and not fact.startswith(
            "m4-p3-result-blind-structural-utility-execution-source:"
        )
    ]
    payload["facts"]["external_events"] = [
        event
        for event in payload["facts"]["external_events"]
        if event
        not in {
            "research-contract:prediction-v2-balanced-design-structural-utility:approved",
            "research-contract:m4-p3-result-blind-structural-utility-preregistration:approved",
            "research-contract:m4-p3-result-blind-structural-utility-blind-generator-and-walk-forward:approved",
        }
    ]
    assert len(payload["tasks"]) == 71
    return payload


def _failed_live_for_recovery() -> dict:
    payload = _historical_recovery_base()
    target = next(
        item
        for item in payload["tasks"]
        if item["task_key"] == PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY
    )
    target["input_artifact_digests"][0] = FAILED_SOURCE_CONTRACT_DIGEST
    target["input_artifact_digests"][3] = (
        design_module.TRUNCATED_ARCHIVE_ROUTE_COMPLETION_DIGEST
    )
    target["status"] = "failed"
    target["completion_classification"] = "INTEGRATED"
    corrected_source_fact = SOURCE_FACT_PREFIX + _source()["artifact_digest"]
    payload["facts"]["artifacts"] = [
        fact for fact in payload["facts"]["artifacts"] if fact != corrected_source_fact
    ]
    live = ControlPlaneManifest.from_dict(payload)
    live_target = next(
        task
        for task in live.tasks
        if task.task_key == PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY
    )
    assert live_target.artifact_digest == FAILED_TASK_DIGEST
    return live.to_dict(include_digest=True)


def _corrected_recovery_source() -> dict:
    payload = _historical_recovery_base()
    return ControlPlaneManifest.from_dict(payload).to_dict(include_digest=True)


def _failed_events() -> list[dict[str, object]]:
    return [
        {
            "task_digest": FAILED_TASK_DIGEST,
            "execution_id": FAILED_EXECUTION_ID,
            "event_type": "started",
            "event_digest": "1" * 64,
            "payload": [],
        },
        {
            "task_digest": FAILED_TASK_DIGEST,
            "execution_id": FAILED_EXECUTION_ID,
            "event_type": "failed",
            "event_digest": "2" * 64,
            "payload": [["error", FAILED_ERROR]],
        },
    ]


def test_design_freezes_exact_incidence_problem_without_duplicate_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source()
    parents = _parents()
    run = build_prediction_v2_balanced_design_feasibility_artifacts(
        source_contract=source,
        require_registered_identities=False,
        **parents,
    )
    specification = run.specification
    assert specification["incidence_identities"] == {
        "block_point_incidences": 1056,
        "point_replication_incidences": 1056,
        "block_pair_incidences": 2640,
        "pair_replication_incidences": 2640,
        "local_point_pair_incidences": 160,
        "local_pair_incidences": 160,
    }
    assert specification["existence_established"] is False
    assert specification["nonexistence_established"] is False
    assert specification["repetition_scan"] == REPETITION_SCAN
    assert run.preregistration_handoff["positive_outcome"] == POSITIVE_OUTCOME
    assert run.preregistration_handoff["bounded_negative_outcome"] == (
        BOUNDED_NEGATIVE_OUTCOME
    )
    assert run.preregistration_handoff["invalid_outcome"] == INVALID_OUTCOME
    assert not {
        "duplicate_validation",
        "duplicate_check",
        "uniqueness_validation",
        "duplicate_scan",
        "membership_scan",
        "membership_validation",
    }.intersection(_recursive_keys(run.artifacts))
    monkeypatch.setattr(
        design_module,
        "build_prediction_v2_balanced_design_feasibility_artifacts",
        lambda **_: run,
    )
    rebuilt, replay = replay_prediction_v2_balanced_design_feasibility(
        source_contract=source,
        **parents,
    )
    assert rebuilt.artifacts == run.artifacts
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["workload_rerun"] is False
    assert replay["candidate_blocks_regenerated"] == 0
    assert replay["repetition_scan"] == REPETITION_SCAN


def test_registered_parent_identity_is_full_digest() -> None:
    assert len(ARCHIVE_ROUTE_COMPLETION_DIGEST) == 64
    assert ARCHIVE_ROUTE_COMPLETION_DIGEST == (
        "147cd0819bca3da1a925812e4f1ac556eeefef79b1973b1027406b9d6a511887"
    )


def test_recovery_replaces_only_exact_zero_artifact_failed_definition() -> None:
    corrected = _corrected_recovery_source()
    before = _failed_live_for_recovery()
    recovered, report = (
        build_prediction_v2_balanced_design_feasibility_recovery_manifest(
            live_payload=before,
            corrected_source_payload=corrected,
            execution_events=_failed_events(),
            execution_artifacts=(),
            require_registered_failure=False,
        )
    )
    after = ControlPlaneManifest.from_dict(recovered)
    target = next(
        task
        for task in after.tasks
        if task.task_key == PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY
    )
    state = after.task_state_by_digest[target.artifact_digest]
    assert target.artifact_digest != FAILED_TASK_DIGEST
    assert target.input_artifact_digests[3] == ARCHIVE_ROUTE_COMPLETION_DIGEST
    assert state.declared_status is TaskStatus.DRAFT
    assert state.completion_classification.value == "INTEGRATION_PENDING"
    assert len(after.tasks) == 71
    assert report["status"] == "SAFE_TO_RECOVER"
    assert report["changed_task_count"] == 1
    assert report["added_source_fact_count"] == 1
    assert report["preexisting_execution_artifact_count"] == 0
    assert report["repetition_scan"] == REPETITION_SCAN

    before_tasks = {item["task_key"]: item for item in before["tasks"]}
    after_tasks = {item["task_key"]: item for item in recovered["tasks"]}
    for task_key, before_task in before_tasks.items():
        if task_key == PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY:
            continue
        assert after_tasks[task_key] == before_task
    old_source_fact = SOURCE_FACT_PREFIX + FAILED_SOURCE_CONTRACT_DIGEST
    new_source_fact = SOURCE_FACT_PREFIX + _source()["artifact_digest"]
    assert old_source_fact in recovered["facts"]["artifacts"]
    assert new_source_fact in recovered["facts"]["artifacts"]


@pytest.mark.parametrize("tamper", ["error", "extra_event", "artifact"])
def test_recovery_fails_closed_on_nonexact_failure_history(tamper: str) -> None:
    events = _failed_events()
    artifacts: tuple[dict[str, str], ...] = ()
    if tamper == "error":
        events[-1] = copy.deepcopy(events[-1])
        events[-1]["payload"] = [["error", "different"]]
    elif tamper == "extra_event":
        events.append(
            {
                **events[-1],
                "event_type": "completed",
                "event_digest": "3" * 64,
            }
        )
    else:
        artifacts = ({"artifact_digest": "4" * 64},)

    with pytest.raises(PredictionV2BalancedDesignFeasibilityRecoveryError):
        build_prediction_v2_balanced_design_feasibility_recovery_manifest(
            live_payload=_failed_live_for_recovery(),
            corrected_source_payload=_corrected_recovery_source(),
            execution_events=events,
            execution_artifacts=artifacts,
            require_registered_failure=False,
        )


def test_design_fails_closed_on_parent_route_drift() -> None:
    parents = _parents()
    changed = copy.deepcopy(parents["research_intake_handoff"])
    changed["automatic_seed_retry"] = True
    identity = {
        key: value for key, value in changed.items() if key != "artifact_digest"
    }
    changed["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.prediction-v2.result-blind-research-intake-handoff.v1",
    )
    parents["research_intake_handoff"] = changed
    with pytest.raises(
        PredictionV2BalancedDesignFeasibilityDesignError,
        match="parent_consistency_invalid",
    ):
        build_prediction_v2_balanced_design_feasibility_artifacts(
            source_contract=_source(),
            require_registered_identities=False,
            **parents,
        )


def test_additive_migration_revises_intake_and_adds_only_preregistration() -> None:
    source = load_m4_manifest(MANIFEST_PATH).to_dict(include_digest=False)
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"]
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY
    ]
    intake = next(
        item
        for item in live["tasks"]
        if item["task_key"] == PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY
    )
    intake["task_type"] = "prediction_v2_result_blind_research_intake"
    intake["requested_capability"] = None
    intake["input_artifact_digests"] = []
    intake["status"] = "draft"
    intake["completion_classification"] = None
    source_fact = SOURCE_FACT_PREFIX + _source()["artifact_digest"]
    live["facts"]["artifacts"] = [
        fact for fact in live["facts"]["artifacts"] if fact != source_fact
    ]
    live["facts"]["external_events"] = [
        event
        for event in live["facts"]["external_events"]
        if event != PREDICTION_V2_APPROVED_RESULT_BLIND_RESEARCH_CONTRACT_EVENT
    ]
    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(
            PREDICTION_V2_APPROVED_RESULT_BLIND_RESEARCH_CONTRACT_EVENT,
        ),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert len(migrated["tasks"]) == len(live["tasks"]) + 1


def test_status_projects_design_and_ready_preregistration() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    tasks = {item.task_key: item for item in manifest.tasks}
    for item in payload["tasks"]:
        if item["task_key"] == PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"] = list(
        dict.fromkeys(
            (
                *payload["facts"]["artifacts"],
                PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_COMPLETION_FACT,
                mainline_completion_fact(
                    task=tasks[PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY],
                    execution_id="c" * 64,
                ),
            )
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": (PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY),
            "design_status": "FROZEN_NOT_EXECUTED",
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == (
        "PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION"
    )
    assert projection["live_mainline_status"] == (
        "PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_DESIGN_VALIDATED_IN_MAINLINE"
    )
    design = projection["prediction_v2_balanced_design_feasibility_design"]
    assert design["completion_fact_available"] is True
    assert design["repetition_scan"] == REPETITION_SCAN
    preregistration = projection[
        "prediction_v2_balanced_design_feasibility_preregistration"
    ]
    assert preregistration["resolver_status"] == "ready"
    assert preregistration["requested_capability"] == (
        "prediction_v2_balanced_design_feasibility_preregistration"
    )


def test_manifest_index_and_supervisor_bind_the_singular_capability() -> None:
    source = _source()
    manifest = load_m4_manifest(MANIFEST_PATH)
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY
    )
    assert task.requested_capability == (
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_CAPABILITY
    )
    assert task.input_artifact_digests[0] == source["artifact_digest"]
    assert len(task.input_artifact_digests) == 4
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[source["artifact_digest"]]["path"] == str(
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_SOURCE_CONTRACT_PATH
    )
    assert index[manifest.artifact_digest]["identity_field"] == "manifest_digest"
    supervisor = ResearchEvidenceSupervisor(
        repository=object(), require_clean_tree=False
    )
    assert PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_CAPABILITY in (
        supervisor.capabilities
    )


def test_latest_summary_prefers_completed_balanced_design(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolutions = [
        type(
            "Resolution",
            (),
            {
                "task_key": PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY,
                "status": TaskStatus.COMPLETED,
            },
        )(),
        type(
            "Resolution",
            (),
            {"task_key": ROUTE_TASK_KEY, "status": TaskStatus.COMPLETED},
        )(),
    ]
    requested: list[str] = []

    def load_execution(**kwargs: object) -> tuple[dict, dict, tuple]:
        requested.append(str(kwargs["task_key"]))
        return (
            {"payload": [["registered_artifact_count", 4]]},
            {"artifact_digest": "1" * 64, "design_status": "FROZEN_NOT_EXECUTED"},
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
    assert requested == [PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY]
    assert summary["execution_task_key"] == (
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY
    )
    assert summary["registered_artifact_count"] == 4
