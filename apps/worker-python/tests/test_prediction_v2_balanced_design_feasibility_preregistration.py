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
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_feasibility_preregistration import (
    BOUNDED_NEGATIVE_OUTCOME,
    CONSTRUCTOR_FAMILY,
    FEASIBILITY_COMPLETION_DIGEST,
    FEASIBILITY_MAINLINE_EXECUTION_DIGEST,
    FEASIBILITY_PREREGISTRATION_HANDOFF_DIGEST,
    FEASIBILITY_SPECIFICATION_DIGEST,
    INVALID_OUTCOME,
    POSITIVE_OUTCOME,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_APPROVED_EVENT,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_CAPABILITY,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_COMPLETION_FACT,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY,
    REPETITION_SCAN,
    PredictionV2BalancedDesignFeasibilityPreregistrationError,
    build_prediction_v2_balanced_design_feasibility_preregistration_artifacts,
    load_prediction_v2_balanced_design_feasibility_preregistration_source_contract,
    verify_prediction_v2_balanced_design_feasibility_preregistration_source_bytes,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest, TaskStatus
from dehps.research_os.supervisor import (
    PredictionV2BalancedDesignFeasibilityPreregistrationCapability,
    ResearchEvidenceSupervisor,
)

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)
DESIGN_TASK_KEY = "prediction-v2-next-result-blind-research-intake"
DESIGN_COMPLETION_FACT = "prediction-v2-balanced-design-feasibility-design:COMPLETE"
SOURCE_FACT_PREFIX = "prediction-v2-balanced-design-feasibility-preregistration-source:"


def _artifact(body: dict, *, domain: str) -> dict:
    payload = {"artifact_digest": "", **body}
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _source() -> dict:
    source = load_prediction_v2_balanced_design_feasibility_preregistration_source_contract(
        ROOT_DIR
        / PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_balanced_design_feasibility_preregistration_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    return source


def _design_parents() -> dict[str, dict]:
    specification = _artifact(
        {
            "schema_version": "dehps-prediction-v2-balanced-design-feasibility.v1",
            "artifact_type": (
                "prediction_v2_balanced_design_feasibility_specification"
            ),
            "status": "COMPLETE",
            "design_status": "FROZEN_NOT_EXECUTED",
            "parameters": {"legal_block_count": 1_107_568},
            "existence_established": False,
            "nonexistence_established": False,
            "result_blind": True,
            "repetition_scan": REPETITION_SCAN,
            "parent_digests": [],
        },
        domain="dehps.prediction-v2.balanced-design-feasibility.v1",
    )
    handoff = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-balanced-design-feasibility-"
                "preregistration-handoff.v1"
            ),
            "artifact_type": (
                "prediction_v2_balanced_design_feasibility_preregistration_handoff"
            ),
            "status": "COMPLETE",
            "feasibility_specification_digest": specification["artifact_digest"],
            "result_blind": True,
            "repetition_scan": REPETITION_SCAN,
            "parent_digests": [specification["artifact_digest"]],
        },
        domain=(
            "dehps.prediction-v2.balanced-design-feasibility-preregistration-handoff.v1"
        ),
    )
    completion = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-balanced-design-feasibility-completion.v1"
            ),
            "artifact_type": "prediction_v2_balanced_design_feasibility_completion",
            "status": "COMPLETE",
            "completion_fact": DESIGN_COMPLETION_FACT,
            "feasibility_specification_digest": specification["artifact_digest"],
            "preregistration_handoff_digest": handoff["artifact_digest"],
            "solver_nodes_executed": 0,
            "candidate_blocks_generated": 0,
            "repetition_scan": REPETITION_SCAN,
            "parent_digests": [
                specification["artifact_digest"],
                handoff["artifact_digest"],
            ],
        },
        domain="dehps.prediction-v2.balanced-design-feasibility-completion.v1",
    )
    execution = _artifact(
        {
            "schema_version": "dehps-research-os-mainline-execution.v1",
            "artifact_type": "research_os_mainline_execution",
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "task_key": DESIGN_TASK_KEY,
            "capability": "prediction_v2_balanced_design_feasibility_design",
            "feasibility_specification_digest": specification["artifact_digest"],
            "preregistration_handoff_digest": handoff["artifact_digest"],
            "feasibility_completion_digest": completion["artifact_digest"],
            "solver_nodes_executed": 0,
            "candidate_blocks_generated": 0,
            "repetition_scan": REPETITION_SCAN,
            "evidence_created": False,
            "new_model_created": False,
            "production_action": "none",
            "parent_digests": [
                specification["artifact_digest"],
                handoff["artifact_digest"],
                completion["artifact_digest"],
            ],
        },
        domain="dehps.research-os.mainline-execution.v1",
    )
    return {
        "feasibility_specification": specification,
        "feasibility_preregistration_handoff": handoff,
        "feasibility_completion": completion,
        "feasibility_mainline_execution": execution,
    }


def _recursive_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(
            *(_recursive_keys(item) for item in value.values()), set()
        )
    if isinstance(value, (list, tuple)):
        return set().union(*(_recursive_keys(item) for item in value), set())
    return set()


def test_preregistration_freezes_complete_cyclic_scope_without_repetition_scan() -> (
    None
):
    source = _source()
    parents = _design_parents()
    run = build_prediction_v2_balanced_design_feasibility_preregistration_artifacts(
        source_contract=source,
        require_registered_identities=False,
        **parents,
    )
    artifact = run.preregistration
    assert artifact["constructor_family"] == CONSTRUCTOR_FAMILY
    assert artifact["orbit_inventory"] == {
        "legal_block_count": 1_107_568,
        "short_orbit_count": 5,
        "blocks_per_short_orbit": 11,
        "full_orbit_count": 33_561,
        "blocks_per_full_orbit": 33,
        "inventory_identity": "55 + 33561*33 = 1107568",
    }
    representation = artifact["representation_scope_and_symmetry_breaks"]
    assert representation["allowed_orbit_count_profiles"] == [
        {"full_orbits": 5, "short_orbits": 1},
        {"full_orbits": 4, "short_orbits": 4},
    ]
    assert representation["other_automorphism_restrictions"] == "NONE"
    assert artifact["canonical_variable_and_branch_order"]["selection_order"] == (
        "STRICTLY_INCREASING_ORBIT_REPRESENTATIVE_ID"
    )
    certificate = artifact["positive_certificate_format"]
    assert certificate["strict_order_is_unrepresentable_to_violate"] is True
    verifier = artifact["independent_exact_integer_verifier"]
    assert verifier["separate_duplicate_membership_or_uniqueness_scan"] is False
    assert verifier["floating_point_operations"] == 0
    assert artifact["repetition_scan"] == REPETITION_SCAN
    assert artifact["legal_block_ids_visited"] == 0
    assert artifact["orbit_candidates_enumerated"] == 0
    assert artifact["solver_nodes_executed"] == 0
    assert artifact["certificate_blocks_generated"] == 0
    assert not {
        "duplicate_validation",
        "duplicate_check",
        "uniqueness_validation",
        "duplicate_scan",
        "membership_scan",
        "membership_validation",
    }.intersection(_recursive_keys(run.artifacts))
    assert run.execution_handoff["positive_outcome"] == POSITIVE_OUTCOME
    assert run.execution_handoff["bounded_negative_outcome"] == BOUNDED_NEGATIVE_OUTCOME
    assert run.execution_handoff["invalid_outcome"] == INVALID_OUTCOME


def test_preregistration_fails_closed_on_parent_or_source_drift() -> None:
    parents = _design_parents()
    changed = copy.deepcopy(parents["feasibility_mainline_execution"])
    changed["new_model_created"] = True
    identity = {
        key: value for key, value in changed.items() if key != "artifact_digest"
    }
    changed["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.research-os.mainline-execution.v1",
    )
    parents["feasibility_mainline_execution"] = changed
    with pytest.raises(
        PredictionV2BalancedDesignFeasibilityPreregistrationError,
        match="parent_consistency_invalid",
    ):
        build_prediction_v2_balanced_design_feasibility_preregistration_artifacts(
            source_contract=_source(),
            require_registered_identities=False,
            **parents,
        )


def test_additive_migration_revises_preregistration_and_adds_only_execution() -> None:
    source = load_m4_manifest(MANIFEST_PATH).to_dict(include_digest=False)
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"]
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY
    ]
    current = next(
        item
        for item in live["tasks"]
        if item["task_key"]
        == PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY
    )
    current["requested_capability"] = None
    current["input_artifact_digests"] = []
    current["dependencies"] = [
        item
        for item in current["dependencies"]
        if item["dependency_type"] != "external_event"
    ]
    current["status"] = "draft"
    current["completion_classification"] = "INTEGRATION_PENDING"
    source_fact = SOURCE_FACT_PREFIX + _source()["artifact_digest"]
    live["facts"]["artifacts"] = [
        fact for fact in live["facts"]["artifacts"] if fact != source_fact
    ]
    live["facts"]["external_events"] = [
        event
        for event in live["facts"]["external_events"]
        if event
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_APPROVED_EVENT
    ]
    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_APPROVED_EVENT,
        ),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert len(migrated["tasks"]) == len(live["tasks"]) + 1


def test_manifest_status_and_index_bind_preregistration_then_stop_at_execution() -> (
    None
):
    source = _source()
    manifest = load_m4_manifest(MANIFEST_PATH)
    tasks = {item.task_key: item for item in manifest.tasks}
    task = tasks[PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY]
    assert task.requested_capability == (
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_CAPABILITY
    )
    assert task.input_artifact_digests == (
        source["artifact_digest"],
        FEASIBILITY_SPECIFICATION_DIGEST,
        FEASIBILITY_PREREGISTRATION_HANDOFF_DIGEST,
        FEASIBILITY_COMPLETION_DIGEST,
        FEASIBILITY_MAINLINE_EXECUTION_DIGEST,
    )
    next_task = tasks[PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY]
    assert next_task.requested_capability == (
        "prediction_v2_balanced_design_feasibility_execution"
    )
    assert len(next_task.input_artifact_digests) == 5
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[source["artifact_digest"]]["path"] == str(
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    assert index[manifest.artifact_digest]["identity_field"] == "manifest_digest"

    payload = manifest.to_dict(include_digest=False)
    for item in payload["tasks"]:
        if item["task_key"] in {DESIGN_TASK_KEY, task.task_key}:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            DESIGN_COMPLETION_FACT,
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_COMPLETION_FACT,
            mainline_completion_fact(
                task=tasks[DESIGN_TASK_KEY], execution_id="b" * 64
            ),
            mainline_completion_fact(task=task, execution_id="a" * 64),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": task.task_key,
            "preregistration_status": "FROZEN_NOT_EXECUTED",
        },
    )["measurement_system_v2"]
    assert status["phase"] == "PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION"
    assert status["live_mainline_status"] == (
        "PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_"
        "VALIDATED_IN_MAINLINE"
    )
    assert status["next_consumer"] == (
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY
    )
    assert (
        status["prediction_v2_balanced_design_feasibility_execution"]["resolver_status"]
        == "ready"
    )
    assert (
        status["prediction_v2_balanced_design_feasibility_execution"][
            "requested_capability"
        ]
        == "prediction_v2_balanced_design_feasibility_execution"
    )


def test_supervisor_executes_and_replays_zero_work_preregistration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source()
    for entry in source["source_entries"]:
        destination = tmp_path / str(entry["path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / str(entry["path"]), destination)
    contract_destination = (
        tmp_path
        / PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    contract_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT_DIR
        / PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_SOURCE_CONTRACT_PATH,
        contract_destination,
    )
    parents = _design_parents()
    synthetic = (
        build_prediction_v2_balanced_design_feasibility_preregistration_artifacts(
            source_contract=source,
            require_registered_identities=False,
            **parents,
        )
    )
    for key, digest in zip(
        (
            "feasibility_specification",
            "feasibility_preregistration_handoff",
            "feasibility_completion",
            "feasibility_mainline_execution",
        ),
        (
            FEASIBILITY_SPECIFICATION_DIGEST,
            FEASIBILITY_PREREGISTRATION_HANDOFF_DIGEST,
            FEASIBILITY_COMPLETION_DIGEST,
            FEASIBILITY_MAINLINE_EXECUTION_DIGEST,
        ),
        strict=True,
    ):
        parents[key]["artifact_digest"] = digest
    parent_by_type = {
        "prediction_v2_balanced_design_feasibility_specification": parents[
            "feasibility_specification"
        ],
        "prediction_v2_balanced_design_feasibility_preregistration_handoff": parents[
            "feasibility_preregistration_handoff"
        ],
        "prediction_v2_balanced_design_feasibility_completion": parents[
            "feasibility_completion"
        ],
    }
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, parents["feasibility_mainline_execution"], []),
    )
    original_load_type = supervisor_module._load_registered_type

    def load_type(*, artifact_type: str, **kwargs: object) -> dict:
        if artifact_type in parent_by_type:
            return parent_by_type[artifact_type]
        return original_load_type(artifact_type=artifact_type, **kwargs)

    monkeypatch.setattr(supervisor_module, "_load_registered_type", load_type)
    monkeypatch.setattr(
        supervisor_module,
        "build_prediction_v2_balanced_design_feasibility_preregistration_artifacts",
        lambda **_: synthetic,
    )
    task = next(
        item
        for item in load_m4_manifest(MANIFEST_PATH).tasks
        if item.task_key
        == PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY
    )
    result = PredictionV2BalancedDesignFeasibilityPreregistrationCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="c" * 64,
        git_commit="d" * 40,
    )
    assert len(result.registrations) == 4
    assert result.execution_artifact["legal_block_ids_visited"] == 0
    assert result.execution_artifact["orbit_candidates_enumerated"] == 0
    assert result.execution_artifact["solver_nodes_executed"] == 0
    assert result.execution_artifact["repetition_scan"] == REPETITION_SCAN

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
        "replay_prediction_v2_balanced_design_feasibility_preregistration",
        lambda **_: (
            synthetic,
            {
                "status": "REPLAY_VERIFIED",
                "same_registered_content": True,
                "workload_rerun": False,
                "orbit_candidates_replayed": 0,
                "solver_nodes_replayed": 0,
            },
        ),
    )
    replay = ResearchEvidenceSupervisor(
        repository=ReplayRepository(),
        root_dir=tmp_path,
        require_clean_tree=False,
    ).replay(task_key=task.task_key, execution_id="c" * 64)
    assert replay["capability_replay"]["status"] == "REPLAY_VERIFIED"
    assert replay["capability_replay"]["workload_rerun"] is False
    assert replay["capability_replay"]["orbit_candidates_replayed"] == 0


def test_latest_summary_prefers_completed_preregistration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolutions = [
        type(
            "Resolution",
            (),
            {
                "task_key": (
                    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY
                ),
                "status": TaskStatus.COMPLETED,
            },
        )(),
        type(
            "Resolution",
            (),
            {"task_key": DESIGN_TASK_KEY, "status": TaskStatus.COMPLETED},
        )(),
    ]
    requested: list[str] = []

    def load_execution(**kwargs: object) -> tuple[dict, dict, tuple]:
        requested.append(str(kwargs["task_key"]))
        return (
            {"payload": [["registered_artifact_count", 4]]},
            {"artifact_digest": "1" * 64},
            (),
        )

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        load_execution,
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=object(), require_clean_tree=False
    )
    assert (
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_CAPABILITY
        in supervisor.capabilities
    )
    summary = supervisor._latest_completed_v2_summary(
        type("Snapshot", (), {"resolutions": resolutions})()
    )
    assert summary is not None
    assert requested == [
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY
    ]
    assert summary["execution_task_key"] == (
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_PREREGISTRATION_TASK_KEY
    )
