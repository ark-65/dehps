from __future__ import annotations

import copy
import json

import pytest
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.structural_utility import (
    m4_p3_result_blind_preregistration as prereg,
)
from dehps.research_os.structural_utility.m4_p3_result_blind_preregistration import (
    M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
    M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_CAPABILITY,
    M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_SOURCE_CONTRACT_PATH,
    M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
    PARENT_CAPABILITY,
    PARENT_COMPLETED_EVENT_DIGEST,
    PARENT_EXECUTION_ID,
    PARENT_MANIFEST_DIGEST,
    PARENT_REGISTRATIONS,
    PARENT_TASK_DIGEST,
    PARENT_TASK_KEY,
    RESEARCH_CONTEXT_FINGERPRINT,
    RESEARCH_CONTRACT_DOMAIN,
    RESEARCH_EXECUTION_ID,
    RESEARCH_PARENT_REQUEST_ID,
    RESEARCH_REQUEST_ID,
    RESEARCH_REQUEST_KEY,
    M4P3ResultBlindStructuralUtilityPreregistrationError,
    build_m4_p3_result_blind_structural_utility_preregistration_artifacts,
    load_m4_p3_result_blind_structural_utility_preregistration_source_contract,
    replay_m4_p3_result_blind_structural_utility_preregistration,
    verify_m4_p3_result_blind_structural_utility_preregistration_source_bytes,
)
from dehps.research_os.structural_utility.m4_p3_result_blind_preregistration_recovery import (
    FAILED_ERROR,
    FAILED_EVENT_DIGEST,
    FAILED_EXECUTION_ID,
    FAILED_REGISTRATIONS,
    FAILED_STARTED_EVENT_DIGEST,
    FAILED_TASK_DIGEST,
    M4P3ResultBlindPreregistrationRecoveryError,
    build_m4_p3_result_blind_preregistration_recovery_manifest,
)
from dehps.research_os.supervisor import (
    MainlineSupervisorError,
    ResearchEvidenceSupervisor,
    _mainline_actual_fold_count,
)
from scripts.build_m4_p3_result_blind_structural_utility_preregistration_manifest import (
    _execution_task,
    _source_payload,
)

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)


def _source() -> dict:
    source = load_m4_p3_result_blind_structural_utility_preregistration_source_contract(
        ROOT_DIR / M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    verify_m4_p3_result_blind_structural_utility_preregistration_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    return source


def _frozen() -> dict:
    return {
        "schema_version": (
            "dehps-m4-p3-result-blind-structural-utility-preregistration.v1"
        ),
        "status": "FROZEN_BEFORE_GENERATION",
        "fold_manifest": {
            "fold_count": 90,
            "fold_manifest_digest": "a" * 64,
        },
        "arms": [
            {
                "arm": "uniform_random_without_replacement",
                "seed_root": "b" * 64,
            },
            {"arm": "legacy_structural_top100"},
            {"arm": "prediction_v2_structural_selection_100"},
        ],
        "constructive_invariants": {"portfolio_size": 100},
        "confirmatory_coordinates": [
            {"metric": key}
            for key in (
                "pair_coverage_ratio",
                "triple_coverage_ratio",
                "high_overlap_ticket_pair_rate",
                "normalized_pair_usage_entropy",
                "largest_similarity_cluster_fraction",
                "family_concentration_hhi",
            )
        ],
        "paired_inference": {"bootstrap_seed_root": "c" * 64},
        "claim_and_route_boundary": {
            "historical_prediction_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "old_training_lines": "FROZEN",
            "promotion_gate_opened": False,
            "predictive_p3_authorized": False,
            "production_action": "none",
        },
    }


def _research_inputs(frozen: dict) -> tuple[dict, dict]:
    return (
        {
            "id": RESEARCH_REQUEST_ID,
            "request_key": RESEARCH_REQUEST_KEY,
            "request_type": "research_scheduler_request",
            "status": "completed",
            "parent_request_id": RESEARCH_PARENT_REQUEST_ID,
            "payload": {
                "context_fingerprint": RESEARCH_CONTEXT_FINGERPRINT,
                "preregistration": frozen,
            },
            "metadata": {
                "result_blind": True,
                "result_aware": False,
                "incidental_prior_structural_values_observed_during_repository_discovery": True,
                "previous_structural_result_values_used_to_select_any_choice": False,
            },
        },
        {
            "id": RESEARCH_EXECUTION_ID,
            "request_id": RESEARCH_REQUEST_ID,
            "status": "completed",
            "result": {
                "contract_status": "FROZEN_BEFORE_GENERATION",
                "fold_count": 90,
                "portfolios_generated": 0,
                "folds_executed": 0,
                "metric_results_read": 0,
                "target_draw_rows_read": 0,
                "previous_structural_result_values_used_to_select_any_choice": 0,
                "mainline_execution_authorized": False,
            },
        },
    )


def _completed_event() -> dict:
    return {
        "event_digest": PARENT_COMPLETED_EVENT_DIGEST,
        "execution_id": PARENT_EXECUTION_ID,
        "control_plane_key": "m4-information-theory-mainline",
        "manifest_digest": PARENT_MANIFEST_DIGEST,
        "task_digest": PARENT_TASK_DIGEST,
        "task_key": PARENT_TASK_KEY,
        "capability": PARENT_CAPABILITY,
        "event_type": "completed",
        "sequence": 1,
    }


def _parent_registrations() -> tuple[dict, ...]:
    return tuple(
        {
            "registration_digest": identity[0],
            "artifact_digest": identity[1],
            "schema_version": identity[2],
            "artifact_type": artifact_type,
            "execution_id": PARENT_EXECUTION_ID,
            "control_plane_key": "m4-information-theory-mainline",
            "task_digest": PARENT_TASK_DIGEST,
            "task_key": PARENT_TASK_KEY,
        }
        for artifact_type, identity in PARENT_REGISTRATIONS.items()
    )


def test_preregistration_compiles_frozen_contract_with_zero_work(monkeypatch) -> None:
    source = _source()
    frozen = _frozen()
    frozen_digest = canonical_digest(frozen, domain=RESEARCH_CONTRACT_DOMAIN)
    monkeypatch.setattr(prereg, "RESEARCH_PREREGISTRATION_DIGEST", frozen_digest)
    request, execution = _research_inputs(frozen)
    run = build_m4_p3_result_blind_structural_utility_preregistration_artifacts(
        source_contract=source,
        research_request=request,
        research_execution=execution,
        completed_event=_completed_event(),
        parent_registrations=_parent_registrations(),
    )
    assert run.preregistration["frozen_contract"] == frozen
    assert run.execution_handoff["fold_count"] == 90
    assert run.execution_handoff["portfolio_budget"] == 100
    assert run.execution_handoff["execution_authorized"] is False
    for artifact in run.artifacts:
        assert artifact["result_blind"] is True
        assert artifact["portfolios_generated"] == 0
        assert artifact["folds_executed"] == 0
        assert artifact["metric_results_read"] == 0
        assert artifact["target_draw_rows_read"] == 0
        assert artifact["bootstrap_resamples_executed"] == 0
        assert artifact["prediction_v2_mode"] == "SHADOW_ONLY"
        assert artifact["old_training_lines"] == "FROZEN"
        assert artifact["production_action"] == "none"
    rebuilt, replay = replay_m4_p3_result_blind_structural_utility_preregistration(
        source_contract=source,
        research_request=request,
        research_execution=execution,
        completed_event=_completed_event(),
        parent_registrations=_parent_registrations(),
    )
    assert rebuilt.artifacts == run.artifacts
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["workload_rerun"] is False


def test_preregistration_rejects_result_selected_choices(monkeypatch) -> None:
    source = _source()
    frozen = _frozen()
    monkeypatch.setattr(
        prereg,
        "RESEARCH_PREREGISTRATION_DIGEST",
        canonical_digest(frozen, domain=RESEARCH_CONTRACT_DOMAIN),
    )
    request, execution = _research_inputs(frozen)
    request = copy.deepcopy(request)
    request["metadata"][
        "previous_structural_result_values_used_to_select_any_choice"
    ] = True
    with pytest.raises(
        M4P3ResultBlindStructuralUtilityPreregistrationError,
        match="research_preregistration_identity_changed",
    ):
        build_m4_p3_result_blind_structural_utility_preregistration_artifacts(
            source_contract=source,
            research_request=request,
            research_execution=execution,
            completed_event=_completed_event(),
            parent_registrations=_parent_registrations(),
        )


def test_manifest_status_index_and_supervisor_bind_preregistration() -> None:
    source = _source()
    manifest = load_m4_manifest(MANIFEST_PATH)
    tasks = {item.task_key: item for item in manifest.tasks}
    task = tasks[M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY]
    assert (
        task.requested_capability == M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_CAPABILITY
    )
    assert task.input_artifact_digests[0] == source["artifact_digest"]
    assert len(task.input_artifact_digests) == 6
    execution = tasks[M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY]
    assert execution.requested_capability == (
        "m4_p3_result_blind_structural_utility_blind_generator_and_walk_forward"
    )
    resolutions = {
        item.task_key: item.status.value
        for item in ResearchOSControlPlane().resolve(manifest).resolutions
    }
    assert resolutions[M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY] == (
        "dependency_wait"
    )
    assert resolutions[M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY] == (
        "dependency_wait"
    )
    projection = build_m4_status(manifest)["structural_utility"]
    assert projection["m4_p3_result_blind_preregistration"]["fold_count"] == 90
    assert (
        projection["m4_p3_result_blind_preregistration"]["integration_answer"]
        == "NO — INTEGRATION_PENDING"
    )
    assert projection["m4_p3_result_blind_execution"]["execution_authorized"] is True
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[source["artifact_digest"]]["path"] == (
        M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_SOURCE_CONTRACT_PATH.as_posix()
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=object(), require_clean_tree=False
    )
    assert M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_CAPABILITY in (
        supervisor.capabilities
    )


def test_migration_builder_reuses_exact_migrated_source() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert _source_payload(source, _source()["artifact_digest"]) == source


def _failed_recovery_inputs() -> tuple[dict, tuple[dict, ...], tuple[dict, ...]]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload.pop("manifest_digest")
    payload["tasks"] = [
        _execution_task()
        if item["task_key"] == M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY
        else item
        for item in payload["tasks"]
        if item["task_key"]
        not in {
            "m4-p3-result-blind-structural-utility-evidence-compiler",
            "m4-p2r-measurement-repair-validation",
            "m4-p3-predictive-route-reconciliation",
        }
    ]
    payload["facts"]["artifacts"] = [
        item
        for item in payload["facts"]["artifacts"]
        if not item.startswith(
            "m4-p3-result-blind-structural-utility-execution-source:"
        )
        and not item.startswith(
            "m4-p3-predictive-route-reconciliation-source:"
        )
    ]
    payload["facts"]["external_events"] = [
        item
        for item in payload["facts"]["external_events"]
        if item
        not in {
            "research-contract:m4-p3-result-blind-structural-utility-"
            "blind-generator-and-walk-forward:approved",
            "research-contract:m4-p3-predictive-route-reconciliation:approved",
            "research-contract:m4-p2r-to-p6-dependency-policy:approved",
            "engineering-contract:m4-p3-predictive-route-reconciliation:approved",
        }
    ]
    task = next(
        item
        for item in payload["tasks"]
        if item["task_key"] == M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY
    )
    task["status"] = "failed"
    task["completion_classification"] = "INTEGRATED"
    events = (
        {
            "event_digest": FAILED_STARTED_EVENT_DIGEST,
            "execution_id": FAILED_EXECUTION_ID,
            "task_digest": FAILED_TASK_DIGEST,
            "event_type": "started",
            "payload": [["git_commit", "613f585"]],
        },
        {
            "event_digest": FAILED_EVENT_DIGEST,
            "execution_id": FAILED_EXECUTION_ID,
            "task_digest": FAILED_TASK_DIGEST,
            "event_type": "failed",
            "payload": [["error", FAILED_ERROR]],
        },
    )
    registrations = tuple(
        {
            "artifact_type": artifact_type,
            "registration_digest": identity[0],
            "artifact_digest": identity[1],
            "execution_id": FAILED_EXECUTION_ID,
            "task_key": M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
            "task_digest": FAILED_TASK_DIGEST,
            "control_plane_key": "m4-information-theory-mainline",
        }
        for artifact_type, identity in FAILED_REGISTRATIONS.items()
    )
    return payload, events, registrations


def test_zero_work_preregistration_projects_actual_fold_count() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY
    )
    zero_work = {
        "portfolios_generated": 0,
        "folds_executed": 0,
        "random_replicates_executed": 0,
        "metric_results_read": 0,
        "target_draw_rows_read": 0,
        "bootstrap_resamples_executed": 0,
    }
    assert (
        _mainline_actual_fold_count(
            task_key=task.task_key,
            requested_capability=task.requested_capability,
            execution_artifact=zero_work,
        )
        == 0
    )
    with pytest.raises(MainlineSupervisorError, match="actual_fold_count is missing"):
        _mainline_actual_fold_count(
            task_key=task.task_key,
            requested_capability="another_capability",
            execution_artifact=zero_work,
        )
    with pytest.raises(MainlineSupervisorError, match="actual_fold_count is missing"):
        _mainline_actual_fold_count(
            task_key="another-task",
            requested_capability=task.requested_capability,
            execution_artifact=zero_work,
        )
    with pytest.raises(MainlineSupervisorError, match="actual_fold_count is missing"):
        _mainline_actual_fold_count(
            task_key=task.task_key,
            requested_capability=task.requested_capability,
            execution_artifact={**zero_work, "folds_executed": 1},
        )
    with pytest.raises(MainlineSupervisorError, match="actual_fold_count is missing"):
        _mainline_actual_fold_count(
            task_key=task.task_key,
            requested_capability=task.requested_capability,
            execution_artifact={},
        )


def test_recovery_preserves_failed_events_and_four_registrations() -> None:
    live, events, registrations = _failed_recovery_inputs()
    recovered, report = build_m4_p3_result_blind_preregistration_recovery_manifest(
        live_payload=live,
        execution_events=events,
        execution_artifacts=registrations,
        require_registered_failure=False,
    )
    task = next(
        item
        for item in recovered["tasks"]
        if item["task_key"] == M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY
    )
    assert task["status"] == "draft"
    assert task["completion_classification"] == "INTEGRATION_PENDING"
    assert report["changed_task_count"] == 1
    assert report["preserved_registration_count"] == 4
    assert report["deleted_event_count"] == 0
    assert report["deleted_registration_count"] == 0
    assert report["workload_rerun"] is False


def test_recovery_rejects_registration_drift() -> None:
    live, events, registrations = _failed_recovery_inputs()
    changed = list(copy.deepcopy(registrations))
    changed[0]["artifact_digest"] = "0" * 64
    with pytest.raises(
        M4P3ResultBlindPreregistrationRecoveryError,
        match="registration_identity_changed",
    ):
        build_m4_p3_result_blind_preregistration_recovery_manifest(
            live_payload=live,
            execution_events=events,
            execution_artifacts=changed,
            require_registered_failure=False,
        )
