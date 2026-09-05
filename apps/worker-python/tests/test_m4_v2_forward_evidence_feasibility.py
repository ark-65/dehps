from __future__ import annotations

import importlib.util

import pytest
from dehps.config import ROOT_DIR
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.measurement_system_v2 import (
    forward_evidence_feasibility as forward,
)
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.repository import PostgresResearchOSRepository


@pytest.fixture
def frozen_source(tmp_path):
    from archival_source import original_source
    archive = original_source(tmp_path, contract_path=forward.SOURCE_CONTRACT_PATH,
                              commit="422a7acac32790829297becc737a66d1e057cc29")
    return forward.load_source_contract(root_dir=archive)


def _inputs() -> tuple[dict[str, str], ...]:
    return tuple({"artifact_digest": digest} for digest in forward.FROZEN_INPUT_DIGESTS)


def test_source_freezes_all_four_programs_and_one_reviewer_decision(frozen_source) -> None:
    source = frozen_source
    matrix = source["feasibility_analysis"]["decision_matrix"]
    assert matrix["program_weighted_totals"] == {
        "LONG_HORIZON_CONFIRMATORY_FORWARD": 57,
        "BOUNDED_OPERATIONAL_FORWARD_STUDY": 67,
        "REDESIGN_PROSPECTIVE_RESEARCH_QUESTION": 56,
        "TERMINATE_PREDICTIVE_ROUTE": 58,
    }
    assert source["reviewer_decision"]["decision"] == forward.SELECTED_DECISION
    assert source["reviewer_decision"]["target_issue_count"] == 120
    assert source["reviewer_decision"]["maximum_issue_count"] == 120
    assert source["reviewer_decision"]["data_reuse_policy"] == (
        "STAGED_INDEPENDENT_SAMPLES"
    )


def test_zero_compute_artifacts_preserve_closed_p3_and_formal_p4(frozen_source) -> None:
    source = frozen_source
    feasibility, decision, replay = forward.build_artifacts(
        source_contract=source, registered_inputs=_inputs()
    )
    assert feasibility["body"]["scientific_computation"] == 0
    assert feasibility["body"]["model_training"] == "NOT_STARTED"
    assert feasibility["body"]["historical_p3_folds"] == 0
    assert feasibility["body"]["forward_checkpoints"] == 0
    assert decision["body"]["p3_scientific_disposition"] == (
        "INCONCLUSIVE_DUE_TO_POWER"
    )
    assert decision["body"]["formal_p4"] == "DEPENDENCY_WAIT"
    assert decision["body"]["pass_to_p4"] == "NOT_EMITTED"
    assert decision["body"]["successor_execution_authorized"] is False
    assert replay["body"]["registered_replay_status"] == ("REGISTERED_REPLAY_VERIFIED")
    assert replay["body"]["workload_rerun"] is False


def test_replay_rebuilds_registered_content_without_workload(frozen_source) -> None:
    source = frozen_source
    artifacts = forward.build_artifacts(
        source_contract=source, registered_inputs=_inputs()
    )
    rebuilt, replay = forward.replay_registered_artifacts(
        source_contract=source,
        registered_inputs=_inputs(),
        stored_artifacts=artifacts,
    )
    assert rebuilt == artifacts
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["registered_replay_status"] == "REGISTERED_REPLAY_VERIFIED"
    assert replay["same_registered_content"] is True
    assert replay["workload_rerun"] is False
    changed = [dict(item) for item in artifacts]
    changed[1] = {
        **changed[1],
        "body": {**changed[1]["body"], "target_issue_count": 60},
    }
    with pytest.raises(forward.M4V2ForwardEvidenceFeasibilityError):
        forward.replay_registered_artifacts(
            source_contract=source,
            registered_inputs=_inputs(),
            stored_artifacts=changed,
        )


def test_manifest_adds_one_executable_decision_and_unimplemented_successor(frozen_source) -> None:
    path = (
        ROOT_DIR
        / "apps/worker-python/scripts/build_m4_v2_forward_evidence_feasibility_manifest.py"
    )
    spec = importlib.util.spec_from_file_location("forward_builder_test", path)
    assert spec is not None and spec.loader is not None
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    source = frozen_source
    from archival_manifest import archived_manifest
    baseline = archived_manifest(builder.BASELINE_MANIFEST_DIGEST)
    assert baseline.artifact_digest == builder.BASELINE_MANIFEST_DIGEST
    payload, dry_run = builder.build_manifest(
        baseline.to_dict(include_digest=True),
        source_contract_digest=source["artifact_digest"],
    )
    manifest = ControlPlaneManifest.from_dict(payload)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    tasks = {item.task_key: item for item in manifest.tasks}
    successor = tasks[forward.SUCCESSOR_TASK_KEY]
    assert tuple(item.task_key for item in snapshot.ready_queue) == (forward.TASK_KEY,)
    assert successor.requested_capability is None
    assert successor.to_dict()["metric_contract"]["execution_authorized"] is False
    assert dry_run["formal_p4_status"] == "dependency_wait"
    assert dry_run["model_training"] == "NOT_STARTED"


def test_frozen_calendar_cost_and_reuse_boundaries_are_explicit(frozen_source) -> None:
    source = frozen_source
    analysis = source["feasibility_analysis"]
    assert analysis["official_calendar_horizons"]["2095"]["completion_date"] == (
        "2040-01-12"
    )
    assert analysis["historical_actual_frequency"]["realistic_completion_date"] == (
        "2040-07-02"
    )
    assert analysis["resource_analysis"]["cpu_telemetry_available"] is False
    assert analysis["codex_cost"]["normal_issue_invocations"] == 0
    assert analysis["model_aging"]["risk_2095"] == "HIGH"
    decision = source["reviewer_decision"]
    assert "cannot enter" in decision["data_reuse_policy_detail"]
    assert "20 and 60" in decision["interim_review_policy"]
    assert decision["next_task_execution_authorized"] is False
