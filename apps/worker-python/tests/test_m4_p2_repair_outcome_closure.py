from __future__ import annotations

import copy
import inspect
import json
import shutil
from types import SimpleNamespace

import pytest
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.measurement_system_v2 import (
    p2_repair_outcome_closure as closure,
)
from dehps.research_os.information_theory.measurement_system_v2.p2_repair_outcome_closure import (
    P2_CLOSURE_CAPABILITY,
    P2_CLOSURE_COMPLETION_FACT,
    P2_CLOSURE_SOURCE_CONTRACT_PATH,
    P2_CLOSURE_TASK_KEY,
    P2R_EXECUTION_APPROVED_EVENT,
    P2R_TASK_KEY,
    P2RepairOutcomeClosureError,
    build_p2_repair_outcome_closure,
    load_p2_repair_outcome_closure_source_contract,
    replay_p2_repair_outcome_closure,
    verify_p2_repair_outcome_closure_source_bytes,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.models import ControlPlaneManifest, Task, TaskStatus
from dehps.research_os.supervisor import (
    M4P2RepairOutcomeClosureCapability,
    ResearchEvidenceSupervisor,
)
from scripts.build_m4_p2_repair_outcome_closure_manifest import (
    P2_CLOSURE_APPROVED_EVENT,
    build_live_migration,
    build_source_payload,
)

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)


def _source() -> dict:
    source = load_p2_repair_outcome_closure_source_contract(
        ROOT_DIR / P2_CLOSURE_SOURCE_CONTRACT_PATH
    )
    verify_p2_repair_outcome_closure_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    return source


def _research_inputs() -> tuple[dict, dict]:
    preregistration = {
        "node_key": P2R_TASK_KEY,
        "phase": "M4-P2R",
        "status": "PENDING_VALIDATION",
        "core_question": "independent repaired-instrument validation",
        "invariants": ["P2 immutable", "P3 non-blocking"],
        "null_hypothesis": "one obligation fails",
        "smallest_non_null_alternative": "all obligations pass",
        "seed_contract": {
            "seed_domain": "DEHPS|M4-P2R|measurement-repair-validation|v1|2026-08-10",
            "seed_root_sha256": closure.RESEARCH_CONTEXT_FINGERPRINT,
            "seed_root_uint64": 17620030220225523377,
            "derivation": "SHA256 domain-separated counters",
        },
        "validation_protocol": {"stage_0": "freeze before samples"},
        "allowed_prior_information": ["contract identities"],
        "forbidden_prior_information_for_tuning": ["failed samples"],
        "failure_condition": "fail closed",
        "execution_authorized": False,
        "evidence_created": False,
        "promotion_gate_opened": False,
        "production_action": "none",
    }
    request = {
        "id": closure.RESEARCH_REQUEST_ID,
        "request_key": closure.RESEARCH_REQUEST_KEY,
        "request_type": "research_scheduler_request",
        "status": "completed",
        "parent_request_id": 361,
        "payload": {
            "context_fingerprint": closure.RESEARCH_CONTEXT_FINGERPRINT,
            "closure_contract": {
                "p2_objective": "validate the frozen synthetic measurement system",
                "legal_flow_completed": True,
                "final_decision": "REPAIR_MEASUREMENT_SYSTEM",
                "terminal_status": "COMPLETE_WITH_REPAIR_OUTCOME",
                "p2_6_1_status": "FROZEN_INCOMPLETE",
                "p2_6_3_status": "SUPERSEDING_COMPLETE",
                "manual_override": False,
                "threshold_change": False,
                "rerun_authorized": False,
            },
            "preregistration_snapshot": preregistration,
        },
        "metadata": {},
    }
    execution = {
        "id": closure.RESEARCH_EXECUTION_ID,
        "request_id": closure.RESEARCH_REQUEST_ID,
        "status": "completed",
        "result": {
            "research_contract_fingerprint": closure.RESEARCH_CONTEXT_FINGERPRINT,
            "closure_outcome": "COMPLETE_WITH_REPAIR_OUTCOME",
            "immutable_p2_decision": "REPAIR_MEASUREMENT_SYSTEM",
            "p2r_status": "PENDING_VALIDATION",
            "validation_execution_authorized": False,
            "failed_samples_available_for_tuning": False,
            "m4_p3_blocked": False,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
    }
    return request, execution


def _registered_gate_pair(monkeypatch: pytest.MonkeyPatch) -> tuple[dict, dict]:
    gate = {
        "schema_version": "dehps-m4-p2-automatic-measurement-gate.v1",
        "artifact_type": "automatic_measurement_gate",
        "artifact_digest": "",
        "decision": "REPAIR_MEASUREMENT_SYSTEM",
        "decision_fact": closure.P27_DECISION_FACT,
        "failed_requirements": [
            "all_practical_strength_cell_power_gates_pass",
            "all_strong_signal_cell_power_gates_pass",
            "all_primary_PE2_absolute_bias_cell_gates_pass",
            "all_primary_PE2_coverage_cell_gates_pass",
        ],
        "manual_override_used": False,
        "P3_reachable": False,
        "repair_reachable": True,
        "parent_digests": ["a" * 64],
    }
    gate["artifact_digest"] = canonical_digest(
        {key: value for key, value in gate.items() if key != "artifact_digest"},
        domain="dehps.m4-p2.automatic-measurement-gate.v1",
    )
    monkeypatch.setattr(closure, "P27_GATE_DIGEST", gate["artifact_digest"])
    execution_digest = "b" * 64
    monkeypatch.setattr(closure, "P27_EXECUTION_DIGEST", execution_digest)
    gate_replay = {
        "schema_version": "dehps-m4-p2-7-gate-replay.v1",
        "artifact_type": "P27MeasurementGateReplayArtifact",
        "artifact_digest": "",
        "status": "REPLAY_VERIFIED",
        "task_key": closure.P27_TASK_KEY,
        "task_digest": closure.P27_TASK_DIGEST,
        "execution_id": closure.P27_EXECUTION_ID,
        "execution_artifact_digest": execution_digest,
        "automatic_gate_digest": gate["artifact_digest"],
        "decision": "REPAIR_MEASUREMENT_SYSTEM",
        "decision_fact": closure.P27_DECISION_FACT,
        "same_execution_identity": True,
        "same_artifact_identity": True,
        "manual_input_assembly": False,
        "parent_digests": [execution_digest, gate["artifact_digest"]],
    }
    gate_replay["artifact_digest"] = canonical_digest(
        {key: value for key, value in gate_replay.items() if key != "artifact_digest"},
        domain="dehps.m4.p27-measurement-gate-replay-artifact.v1",
    )
    monkeypatch.setattr(closure, "P27_REPLAY_DIGEST", gate_replay["artifact_digest"])
    return gate, gate_replay


def test_closure_is_deterministic_zero_work_and_input_immutable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source()
    request, execution = _research_inputs()
    gate, gate_replay = _registered_gate_pair(monkeypatch)
    before = copy.deepcopy((request, execution, gate, gate_replay))
    artifact = build_p2_repair_outcome_closure(
        source_contract=source,
        research_request=request,
        research_execution=execution,
        gate=gate,
        gate_replay=gate_replay,
    )
    replay = replay_p2_repair_outcome_closure(
        closure_artifact=artifact,
        source_contract=source,
        research_request=request,
        research_execution=execution,
        gate=gate,
        gate_replay=gate_replay,
    )
    assert (request, execution, gate, gate_replay) == before
    assert artifact["status"] == "COMPLETE_WITH_REPAIR_OUTCOME"
    assert artifact["final_decision"] == "REPAIR_MEASUREMENT_SYSTEM"
    assert artifact["preserved_subphase_status"] == {
        "M4-P2.6.1": "FROZEN_INCOMPLETE",
        "M4-P2.6.3": "SUPERSEDING_COMPLETE",
    }
    assert artifact["formal_replicates_executed"] == 0
    assert artifact["historical_database_reads"] == 0
    assert artifact["historical_predictions_read"] == 0
    assert artifact["historical_results_read"] == 0
    assert artifact["historical_folds_read"] == 0
    assert artifact["artifacts_mutated"] == 0
    assert artifact["evidence_created"] is False
    assert artifact["promotion_gate_opened"] is False
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["compute_executed"] is False


def test_closure_rejects_decision_or_replay_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source()
    request, execution = _research_inputs()
    gate, gate_replay = _registered_gate_pair(monkeypatch)
    gate = copy.deepcopy(gate)
    gate["decision"] = "PASS_TO_P3"
    with pytest.raises(P2RepairOutcomeClosureError, match="gate_identity_changed"):
        build_p2_repair_outcome_closure(
            source_contract=source,
            research_request=request,
            research_execution=execution,
            gate=gate,
            gate_replay=gate_replay,
        )


def test_manifest_projects_repair_closure_and_nonblocking_p2r() -> None:
    source = _source()
    manifest = load_m4_manifest(MANIFEST_PATH)
    tasks = {task.task_key: task for task in manifest.tasks}
    closure_task = tasks[P2_CLOSURE_TASK_KEY]
    p2r_task = tasks[P2R_TASK_KEY]
    assert closure_task.requested_capability == P2_CLOSURE_CAPABILITY
    assert closure_task.input_artifact_digests[0] == source["artifact_digest"]
    assert p2r_task.requested_capability is None
    assert json.loads(p2r_task.metric_contract)["status"] == "PENDING_VALIDATION"
    assert P2R_EXECUTION_APPROVED_EVENT not in manifest.facts.external_events
    snapshot = ResearchOSControlPlane().resolve(manifest)
    resolutions = {item.task_key: item for item in snapshot.resolutions}
    assert resolutions[P2_CLOSURE_TASK_KEY].status is TaskStatus.DEPENDENCY_WAIT
    assert resolutions[P2R_TASK_KEY].status is TaskStatus.EXTERNAL_WAIT
    status = build_m4_status(manifest, snapshot=snapshot)
    assert status["p2_closure"]["status"] == "INTEGRATION_PENDING"
    assert status["p2_closure"]["final_decision"] == "REPAIR_MEASUREMENT_SYSTEM"
    assert status["p2r"]["status"] == "PENDING_VALIDATION"
    assert status["p2r"]["failed_p2_samples_available_for_tuning"] is False
    assert status["p2r"]["m4_p3_dependency"] is False
    assert status["m4_p3_status"] == "ACTIVE"
    for task in manifest.tasks:
        if task.task_key.startswith("m4-p3"):
            assert all(
                dependency.target_key != P2R_TASK_KEY
                for dependency in task.dependencies
            )


def test_completed_closure_moves_phase_forward_but_leaves_p2r_pending() -> None:
    original = load_m4_manifest(MANIFEST_PATH)
    original_tasks = {item.task_key: item for item in original.tasks}
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload.pop("manifest_digest")
    task = next(
        item for item in payload["tasks"] if item["task_key"] == P2_CLOSURE_TASK_KEY
    )
    task["status"] = "completed"
    task["completion_classification"] = "COMPLETE"
    replay_task = next(
        item
        for item in payload["tasks"]
        if item["task_key"] == "m4-v2-p2-7-measurement-gate-replay"
    )
    replay_task["status"] = "completed"
    replay_task["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        [
            P2_CLOSURE_COMPLETION_FACT,
            "m4-p2-7-measurement-gate-replay:VERIFIED",
            (
                "mainline-execution:m4-v2-p2-7-measurement-gate-replay:"
                f"{original_tasks['m4-v2-p2-7-measurement-gate-replay'].artifact_digest}:"
                f"{'b' * 64}:completed"
            ),
            (
                f"mainline-execution:{P2_CLOSURE_TASK_KEY}:"
                f"{original_tasks[P2_CLOSURE_TASK_KEY].artifact_digest}:"
                f"{'c' * 64}:completed"
            ),
        ]
    )
    manifest = ControlPlaneManifest.from_dict(payload)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    resolutions = {item.task_key: item for item in snapshot.resolutions}
    assert resolutions[P2R_TASK_KEY].status is TaskStatus.EXTERNAL_WAIT
    status = build_m4_status(manifest, snapshot=snapshot)
    assert status["p2_closure"]["status"] == "COMPLETE_WITH_REPAIR_OUTCOME"
    assert status["p2_closure"]["p2_6_1_status"] == "FROZEN_INCOMPLETE"
    assert status["p2_closure"]["p2_6_3_status"] == "SUPERSEDING_COMPLETE"
    assert status["current_phase"] == "M4-P3"
    assert status["m4_p3_status"] == "ACTIVE"
    assert status["p2r"]["resolver_status"] == "external_wait"


def test_source_builder_is_idempotent_and_live_migration_is_additive() -> None:
    source_contract = _source()
    migrated = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert (
        build_source_payload(
            migrated,
            source_digest=source_contract["artifact_digest"],
        )
        == migrated
    )
    live = copy.deepcopy(migrated)
    live.pop("manifest_digest")
    live["tasks"] = [item for item in live["tasks"] if item["task_key"] != P2R_TASK_KEY]
    old_closure = next(
        item for item in live["tasks"] if item["task_key"] == P2_CLOSURE_TASK_KEY
    )
    old_closure.clear()
    old_closure.update(
        {
            "task_key": P2_CLOSURE_TASK_KEY,
            "goal_key": "M4_INFORMATION_THEORY_EVIDENCE",
            "task_type": "synthetic_validation",
            "lane": "research",
            "priority": 100,
            "dependencies": [
                {
                    "dependency_type": "task",
                    "target_key": "m4-p2-automatic-gate-and-report",
                    "required_status": "completed",
                },
                {
                    "dependency_type": "artifact",
                    "target_key": "m4-p2-measurement-decision:PASS_TO_P3",
                    "required_status": "available",
                },
            ],
            "metric_contract": {
                "phase": "M4-P2",
                "engineering_complete": False,
                "evidence_complete": False,
            },
            "status": "draft",
            "completion_classification": "INTEGRATION_PENDING",
        }
    )
    live["facts"]["artifacts"] = [
        item
        for item in live["facts"]["artifacts"]
        if not item.startswith("m4-p2-repair-outcome-closure-source:")
    ]
    live["facts"]["external_events"] = [
        item
        for item in live["facts"]["external_events"]
        if item != P2_CLOSURE_APPROVED_EVENT
    ]
    output, dry_run = build_live_migration(
        live_payload=live,
        source_payload=migrated,
        source_digest=source_contract["artifact_digest"],
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [P2R_TASK_KEY]
    assert dry_run["revised_task_keys"] == [P2_CLOSURE_TASK_KEY]
    assert dry_run["existing_state_regressions"] == 0
    assert len(output["tasks"]) == len(live["tasks"]) + 1


def test_source_index_supervisor_and_forbidden_read_boundaries() -> None:
    source = _source()
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[source["artifact_digest"]]["path"] == (
        P2_CLOSURE_SOURCE_CONTRACT_PATH.as_posix()
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert P2_CLOSURE_CAPABILITY in supervisor.capabilities
    capability_source = inspect.getsource(M4P2RepairOutcomeClosureCapability)
    for forbidden in (
        "load_history",
        "load_history_until_with_dates",
        "evaluate_automatic_gate",
        "execute_health_program",
        "run_replicate",
        "add_evidence",
        "promote",
    ):
        assert forbidden not in capability_source


def test_capability_executes_only_zero_work_closure_in_isolated_root(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, research_execution = _research_inputs()
    gate, gate_replay = _registered_gate_pair(monkeypatch)
    monkeypatch.setattr(
        supervisor_module, "P2_CLOSURE_GATE_DIGEST", gate["artifact_digest"]
    )
    monkeypatch.setattr(
        supervisor_module,
        "P2_CLOSURE_GATE_REPLAY_DIGEST",
        gate_replay["artifact_digest"],
    )
    monkeypatch.setattr(
        supervisor_module,
        "P2_CLOSURE_P27_EXECUTION_ID",
        "1" * 64,
    )
    monkeypatch.setattr(
        supervisor_module,
        "P2_CLOSURE_GATE_REPLAY_EXECUTION_ID",
        "2" * 64,
    )

    module_target = tmp_path / closure._SOURCE_MODULE_PATH
    module_target.parent.mkdir(parents=True)
    shutil.copy2(ROOT_DIR / closure._SOURCE_MODULE_PATH, module_target)
    contract_target = tmp_path / P2_CLOSURE_SOURCE_CONTRACT_PATH
    contract_target.parent.mkdir(parents=True)
    shutil.copy2(ROOT_DIR / P2_CLOSURE_SOURCE_CONTRACT_PATH, contract_target)
    gate_path = tmp_path / "registered/gate.json"
    replay_path = tmp_path / "registered/replay.json"
    gate_path.parent.mkdir(parents=True)
    gate_path.write_text(json.dumps(gate), encoding="utf-8")
    replay_path.write_text(json.dumps(gate_replay), encoding="utf-8")

    class FakeResearchOSRepository:
        def list_mainline_artifacts(self, *, control_plane_key, execution_id):
            assert control_plane_key == "m4-information-theory-mainline"
            if execution_id == "1" * 64:
                return [
                    {
                        "artifact_digest": gate["artifact_digest"],
                        "artifact_type": "automatic_measurement_gate",
                        "artifact_path": str(gate_path.relative_to(tmp_path)),
                    }
                ]
            if execution_id == "2" * 64:
                return [
                    {
                        "artifact_digest": gate_replay["artifact_digest"],
                        "artifact_type": "P27MeasurementGateReplayArtifact",
                        "artifact_path": str(replay_path.relative_to(tmp_path)),
                    }
                ]
            raise AssertionError("unexpected execution lookup")

    class FakeAgentRepository:
        def get_request(self, request_key):
            assert request_key == closure.RESEARCH_REQUEST_KEY
            return SimpleNamespace(
                id=request["id"],
                request_key=request["request_key"],
                request_type=SimpleNamespace(value=request["request_type"]),
                status=SimpleNamespace(value=request["status"]),
                parent_request_id=request["parent_request_id"],
                payload=request["payload"],
                metadata=request["metadata"],
            )

        def list_executions(self, request_key):
            assert request_key == closure.RESEARCH_REQUEST_KEY
            return [
                SimpleNamespace(
                    id=research_execution["id"],
                    request_id=research_execution["request_id"],
                    status=SimpleNamespace(value=research_execution["status"]),
                    result=research_execution["result"],
                )
            ]

    task_payload = next(
        item
        for item in json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["tasks"]
        if item["task_key"] == P2_CLOSURE_TASK_KEY
    )
    task_payload = copy.deepcopy(task_payload)
    task_payload["input_artifact_digests"][-2:] = [
        gate["artifact_digest"],
        gate_replay["artifact_digest"],
    ]
    task = Task.from_dict(task_payload)
    capability = M4P2RepairOutcomeClosureCapability(
        repository=FakeResearchOSRepository(),
        agent_repository=FakeAgentRepository(),
        root_dir=tmp_path,
    )
    result = capability.execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="3" * 64,
        git_commit="4" * 40,
    )
    execution = result.execution_artifact
    assert execution["p2_status"] == "COMPLETE_WITH_REPAIR_OUTCOME"
    assert execution["decision"] == "REPAIR_MEASUREMENT_SYSTEM"
    assert execution["replay_status"] == "REPLAY_VERIFIED"
    assert execution["actual_fold_count"] == 0
    assert execution["formal_replicates_executed"] == 0
    assert execution["historical_database_reads"] == 0
    assert execution["artifacts_mutated"] == 0
    assert execution["evidence_created"] is False
    assert execution["promotion_gate_opened"] is False
    assert execution["m4_p3_blocked_by_p2r"] is False
    assert result.completion_facts == (P2_CLOSURE_COMPLETION_FACT,)
    assert len(result.registrations) == 2
