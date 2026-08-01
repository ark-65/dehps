from __future__ import annotations

import copy
import json
import shutil
from dataclasses import asdict
from pathlib import Path

import pytest
from dehps.research_os.information_theory.measurement_system_v2 import (
    NO_DETECTABLE_INFORMATION,
    bind_p261_marginal_acceptance,
    build_branch_decision_replay_artifact,
    compile_m4_v2_routing_decision,
    load_gate_replay_fixture,
    load_measurement_contract_v2,
    load_p261_marginal_binding_contract,
)
from dehps.research_os.information_theory.measurement_system_v2.execution import (
    build_design_artifacts,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.replay import (
    build_design_replay_artifacts,
)
from dehps.research_os.information_theory.measurement_system_v2.runtime_audit import (
    UNAVAILABLE,
    AuditedEvaluator,
    RuntimeAuditError,
    RuntimeAuditObserver,
    _io_deltas,
    build_equivalence_attestation,
    load_runtime_audit_plan,
)
from dehps.research_os.information_theory.measurement_system_v2.terminal_guard import (
    EXPECTED_P261_EXECUTION_ID,
    EXPECTED_P261_TASK_DIGEST,
    LEGACY_P3_TASK_KEY,
    P27_TASK_KEY,
    P261_TASK_KEY,
    evaluate_post_stop_boundary,
    evaluate_terminal_boundary,
)
from dehps.research_os.information_theory.progress import load_m4_manifest
from dehps.research_os.supervisor import (
    M4MeasurementContractV2DesignCapability,
    M4MeasurementContractV2DesignReplayCapability,
    MainlineSupervisorError,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = ROOT / "configs/research-os/m4-measurement-contract-v2.json"
BINDING_PATH = (
    ROOT / "configs/research-os/m4-p2-6-1-marginal-binding-contract-v1.json"
)
FIXTURE_PATH = (
    ROOT
    / "configs/research-os/m4-measurement-contract-v2-replay-fixture-v1.json"
)
AUDIT_PATH = (
    ROOT / "configs/research-os/m4-p2-9-measurement-runtime-audit-plan-v1.json"
)
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"


def _raw_replay() -> dict:
    return {
        "schema_version": "dehps-m4-p2-6-1-raw-execution-replay.v1",
        "status": "REPLAY_VERIFIED",
        "task_key": P261_TASK_KEY,
        "task_digest": EXPECTED_P261_TASK_DIGEST,
        "execution_id": EXPECTED_P261_EXECUTION_ID,
        "execution_artifact_digest": "1" * 64,
        "measurement_validation_manifest_digest": (
            "a4e46a434a4b2ef9fe56ed0390d58ca5a45bbad21685b81cb983f7261b3abf58"
        ),
        "completion_artifact_digest": "2" * 64,
        "completion_event_digest": "3" * 64,
        "registered_artifact_count": 31034,
        "same_execution_identity": True,
        "same_artifact_identity": True,
        "manual_input_assembly": False,
    }


def _gate_replay(decision: str = "PASS_TO_P3") -> dict:
    return {
        "schema_version": "dehps-m4-p2-7-gate-replay.v1",
        "status": "REPLAY_VERIFIED",
        "task_key": P27_TASK_KEY,
        "task_digest": "4" * 64,
        "execution_id": "5" * 64,
        "execution_artifact_digest": "6" * 64,
        "parent_p2_6_1_execution_id": EXPECTED_P261_EXECUTION_ID,
        "parent_p2_6_1_execution_artifact_digest": "1" * 64,
        "automatic_gate_digest": "7" * 64,
        "decision": decision,
        "decision_fact": f"m4-p2-measurement-decision:{decision}",
        "same_execution_identity": True,
        "same_artifact_identity": True,
        "manual_input_assembly": False,
    }


@pytest.mark.parametrize(
    ("gate_decision", "health", "eligible"),
    [
        ("PASS_TO_P3", "PASS", True),
        ("REPAIR_MEASUREMENT_SYSTEM", "REPAIR", False),
    ],
)
def test_marginal_binding_maps_only_synthetic_health(
    gate_decision: str,
    health: str,
    eligible: bool,
) -> None:
    contract = load_p261_marginal_binding_contract(BINDING_PATH)
    decision = bind_p261_marginal_acceptance(
        contract,
        raw_replay=_raw_replay(),
        gate_replay=_gate_replay(gate_decision),
    )
    assert decision["measurement_health"] == health
    assert decision["eligible_for_formal_branch_program"] is eligible
    assert decision["historical_evidence"] == "NOT_RUN"
    assert decision["historical_run_status"] == "NOT_RUN"
    assert decision["evidence_progress_increment"] == 0
    assert decision["promotion_gate_opened"] is False


@pytest.mark.parametrize(
    ("raw_mutation", "gate_mutation", "reason"),
    [
        (None, None, "missing_or_nonterminal_raw_execution"),
        (
            {"measurement_validation_manifest_digest": "9" * 64},
            {},
            "task_execution_or_manifest_identity_drift",
        ),
        ({"status": "REPLAY_FAILED"}, {}, "raw_execution_replay_not_verified"),
        (
            {},
            {"parent_p2_6_1_execution_artifact_digest": "8" * 64},
            "wrong_p2_6_1_parent",
        ),
        ({"partial_statistics": {"power": 0.9}}, {}, "input_contains_non_allowlisted_fields"),
    ],
)
def test_marginal_binding_fails_closed(
    raw_mutation: dict | None,
    gate_mutation: dict | None,
    reason: str,
) -> None:
    contract = load_p261_marginal_binding_contract(BINDING_PATH)
    raw = None if raw_mutation is None else {**_raw_replay(), **raw_mutation}
    gate = {**_gate_replay(), **(gate_mutation or {})}
    decision = bind_p261_marginal_acceptance(
        contract,
        raw_replay=raw,
        gate_replay=gate,
    )
    assert decision["measurement_health"] == "INCONCLUSIVE"
    assert reason in decision["failure_reasons"]
    assert decision["historical_evidence"] == "NOT_RUN"


def test_marginal_decision_replay_is_content_exact() -> None:
    contract = load_p261_marginal_binding_contract(BINDING_PATH)
    decision = bind_p261_marginal_acceptance(
        contract,
        raw_replay=_raw_replay(),
        gate_replay=_gate_replay(),
    )
    replay = build_branch_decision_replay_artifact(
        decision=decision,
        reconstructed_decision=copy.deepcopy(decision),
    )
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["historical_evidence"] == "NOT_RUN"
    with pytest.raises(Exception, match="decision content changed"):
        build_branch_decision_replay_artifact(
            decision=decision,
            reconstructed_decision={**decision, "measurement_health": "REPAIR"},
        )


def _routing_gate(
    *,
    coverage: str,
    health: tuple[str, str, str],
    evidence: tuple[str, str, str],
    global_evidence: str = "INCONCLUSIVE",
) -> dict:
    branches = (
        "MARGINAL_STATIC",
        "TEMPORAL_MARGINAL_INCREMENT",
        "JOINT_RESIDUAL_INCREMENT",
    )
    return {
        "schema_version": "dehps-m4-measurement-gate-compiler-output.v2",
        "artifact_type": "hierarchical_measurement_gate_output",
        "artifact_digest": "a" * 64,
        "contract_digest": "b" * 64,
        "global_coverage": coverage,
        "global_evidence": global_evidence,
        "branch_outputs": [
            {
                "branch_id": branch,
                "measurement_health": branch_health,
                "historical_evidence": branch_evidence,
            }
            for branch, branch_health, branch_evidence in zip(
                branches, health, evidence, strict=True
            )
        ],
        "promotion_gate_opened": False,
        "production_action": "none",
    }


@pytest.mark.parametrize(
    ("gate", "route", "router"),
    [
        (
            _routing_gate(
                coverage="FULL",
                health=("PASS", "PASS", "PASS"),
                evidence=("POSITIVE", "NEGATIVE", "NEGATIVE"),
                global_evidence="CANDIDATE_INFORMATION_FOUND",
            ),
            "ADAPTIVE_RESEARCH_ELIGIBLE",
            True,
        ),
        (
            _routing_gate(
                coverage="PARTIAL",
                health=("PASS", "INCONCLUSIVE", "INCONCLUSIVE"),
                evidence=("POSITIVE", "INCONCLUSIVE", "NOT_RUN"),
                global_evidence="CANDIDATE_INFORMATION_FOUND",
            ),
            "DEEPER_VALIDATION_REQUIRED",
            False,
        ),
        (
            _routing_gate(
                coverage="FULL",
                health=("PASS", "PASS", "PASS"),
                evidence=("NEGATIVE", "NEGATIVE", "NEGATIVE"),
                global_evidence="NO_DETECTABLE_INFORMATION",
            ),
            NO_DETECTABLE_INFORMATION,
            False,
        ),
        (
            _routing_gate(
                coverage="PARTIAL",
                health=("REPAIR", "INCONCLUSIVE", "INCONCLUSIVE"),
                evidence=("NOT_RUN", "NOT_RUN", "NOT_RUN"),
            ),
            "MEASUREMENT_REPAIR_REQUIRED",
            False,
        ),
        (
            _routing_gate(
                coverage="PARTIAL",
                health=("PASS", "PASS", "INCONCLUSIVE"),
                evidence=("NEGATIVE", "INCONCLUSIVE", "NOT_RUN"),
            ),
            "DEEPER_VALIDATION_REQUIRED",
            False,
        ),
    ],
)
def test_global_routing_requires_full_coverage(
    gate: dict,
    route: str,
    router: bool,
) -> None:
    decision = compile_m4_v2_routing_decision(gate)
    assert decision["route"] == route
    assert decision["expert_router_research_enabled"] is router
    assert decision["promotion_gate_opened"] is False


def _event(event_type: str, *, task_key: str = P261_TASK_KEY) -> dict:
    return {
        "event_digest": ({"started": "1", "completed": "2", "failed": "3"}.get(event_type, "4") * 64),
        "execution_id": EXPECTED_P261_EXECUTION_ID,
        "manifest_digest": "5" * 64,
        "task_digest": EXPECTED_P261_TASK_DIGEST,
        "task_key": task_key,
        "capability": "m4_p2_6_1_false_positive_and_power",
        "event_type": event_type,
    }


def test_completion_guard_stops_before_release_and_verifies_post_stop(
    tmp_path: Path,
) -> None:
    completion_path = tmp_path / "runtime/completion.json"
    completion_path.parent.mkdir(parents=True)
    completion_path.write_text("opaque-final-artifact\n", encoding="utf-8")
    events = (_event("started"), _event("completed"))
    registration = {
        "task_key": P261_TASK_KEY,
        "task_digest": EXPECTED_P261_TASK_DIGEST,
        "execution_id": EXPECTED_P261_EXECUTION_ID,
        "artifact_type": "measurement_validation_completion",
        "artifact_digest": "6" * 64,
        "artifact_path": "runtime/completion.json",
    }
    decision = evaluate_terminal_boundary(
        p261_events=events,
        all_events=events,
        registrations=(registration,),
        root_dir=tmp_path,
    )
    assert decision.state == "STOP_REQUIRED"
    assert decision.stop_service is True
    assert decision.publish_slot_event is False
    post = evaluate_post_stop_boundary(
        service_active_state="inactive",
        worker_cgroup_empty=True,
        downstream_started_events=(),
        completion_artifact_digest="6" * 64,
    )
    assert post.state == "SAFE_TO_RELEASE_SLOT"
    assert post.publish_slot_event is True


@pytest.mark.parametrize(
    ("events", "reason"),
    [
        ((_event("started"), _event("failed")), "P261_FAILED"),
        (
            (
                _event("started"),
                _event("completed"),
                {**_event("started", task_key=P27_TASK_KEY), "execution_id": "7" * 64},
            ),
            "DOWNSTREAM_DISPATCH_RACE",
        ),
        (
            (
                _event("started"),
                _event("completed"),
                {**_event("started", task_key=LEGACY_P3_TASK_KEY), "execution_id": "8" * 64},
            ),
            "DOWNSTREAM_DISPATCH_RACE",
        ),
    ],
)
def test_completion_guard_incidents_never_release(
    events: tuple[dict, ...],
    reason: str,
    tmp_path: Path,
) -> None:
    decision = evaluate_terminal_boundary(
        p261_events=tuple(item for item in events if item["task_key"] == P261_TASK_KEY),
        all_events=events,
        registrations=(),
        root_dir=tmp_path,
    )
    assert decision.state == "GOVERNANCE_INCIDENT"
    assert decision.reason == reason
    assert decision.stop_service is True
    assert decision.publish_slot_event is False


def test_design_replay_fixture_is_frozen_and_tamper_fails() -> None:
    contract = load_measurement_contract_v2(CONTRACT_PATH)
    fixture = load_gate_replay_fixture(FIXTURE_PATH)
    design = build_design_artifacts(
        contract,
        execution_id="1" * 64,
        git_commit="2" * 40,
    )
    execution = {
        "artifact_type": "research_os_mainline_execution",
        "execution_id": "1" * 64,
        "artifact_digest": "3" * 64,
        "measurement_contract_v2_digest": contract.artifact_digest,
        "estimand_contract_digest": design.estimand_contract["artifact_digest"],
        "mechanism_role_contract_digest": design.mechanism_role_contract["artifact_digest"],
        "gate_compiler_contract_digest": design.gate_compiler_contract["artifact_digest"],
        "completion_artifact_digest": design.completion["artifact_digest"],
    }
    registrations = [
        {
            "artifact_digest": item["artifact_digest"],
            "artifact_type": item["artifact_type"],
            "artifact_path": f"runtime/{index}.json",
            "execution_id": "1" * 64,
        }
        for index, item in enumerate((*design.artifacts, execution))
    ]
    replay = build_design_replay_artifacts(
        contract,
        fixture=fixture,
        design_execution=execution,
        design_child_digests=[item["artifact_digest"] for item in design.artifacts],
        registration_payloads=registrations,
    )
    assert replay.measurement_contract_replay["status"] == "REPLAY_VERIFIED"
    assert replay.gate_compiler_replay["status"] == "REPLAY_VERIFIED"
    tampered = copy.deepcopy(dict(fixture.payload))
    tampered["expected_output_digest"] = "9" * 64
    with pytest.raises(Exception, match="fixture changed"):
        build_design_replay_artifacts(
            contract,
            fixture=type(fixture)(payload=tampered, artifact_digest=fixture.artifact_digest),
            design_execution=execution,
            design_child_digests=[item["artifact_digest"] for item in design.artifacts],
            registration_payloads=registrations,
        )


class _DesignReplayRepository:
    def __init__(self, event: dict, registrations: list[dict]) -> None:
        self.event = event
        self.registrations = registrations

    def list_mainline_execution_events(
        self,
        *,
        control_plane_key: str,
        task_key: str | None = None,
        execution_id: str | None = None,
    ) -> tuple[dict, ...]:
        if task_key is not None and task_key != self.event["task_key"]:
            return ()
        if execution_id is not None and execution_id != self.event["execution_id"]:
            return ()
        return (self.event,)

    def list_mainline_artifacts(
        self,
        *,
        control_plane_key: str,
        execution_id: str,
    ) -> tuple[dict, ...]:
        assert execution_id == self.event["execution_id"]
        return tuple(self.registrations)


def test_design_replay_is_a_formal_capability_with_immutable_artifacts(
    tmp_path: Path,
) -> None:
    for relative in (
        "configs/research-os/m4-measurement-contract-v2.json",
        "configs/research-os/m4-measurement-contract-v2-replay-fixture-v1.json",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    manifest = load_m4_manifest(MANIFEST_PATH)
    tasks = {item.task_key: item for item in manifest.tasks}
    design_task = tasks["m4-v2-measurement-contract-design"]
    replay_task = tasks["m4-v2-measurement-contract-design-replay"]
    design_id = "a" * 64
    design = M4MeasurementContractV2DesignCapability(root_dir=tmp_path).execute(
        control_plane_key="test-mainline",
        task=design_task,
        execution_id=design_id,
        git_commit="b" * 40,
    )
    registrations = [asdict(item) for item in design.registrations]
    event = {
        "event_type": "completed",
        "task_key": design_task.task_key,
        "task_digest": design_task.artifact_digest,
        "execution_id": design_id,
        "payload": {
            "execution_artifact_path": str(
                design.execution_artifact_path.relative_to(tmp_path)
            ),
            "registered_artifact_count": len(registrations),
        },
    }
    repository = _DesignReplayRepository(event, registrations)
    result = M4MeasurementContractV2DesignReplayCapability(
        repository=repository,
        root_dir=tmp_path,
    ).execute(
        control_plane_key="test-mainline",
        task=replay_task,
        execution_id="c" * 64,
        git_commit="d" * 40,
    )
    assert result.completion_facts == (
        "m4-measurement-contract-v2-design-replay:VERIFIED",
    )
    assert result.execution_artifact["registered_artifact_count"] == 3
    assert {
        item.artifact_type for item in result.registrations
    } == {
        "MeasurementContractV2ReplayArtifact",
        "GateCompilerReplayArtifact",
        "research_os_mainline_execution",
    }

    gate_registration = next(
        item
        for item in registrations
        if item["artifact_type"] == "measurement_v2_gate_compiler_contract"
    )
    gate_path = tmp_path / gate_registration["artifact_path"]
    tampered = json.loads(gate_path.read_text(encoding="utf-8"))
    tampered["tampered"] = True
    gate_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(MainlineSupervisorError, match="registered artifact content changed"):
        M4MeasurementContractV2DesignReplayCapability(
            repository=repository,
            root_dir=tmp_path,
        ).execute(
            control_plane_key="test-mainline",
            task=replay_task,
            execution_id="e" * 64,
            git_commit="d" * 40,
        )


def test_additive_manifest_migration_preserves_live_truth() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest")
    new_tasks = {
        "m4-v2-measurement-contract-design",
        "m4-v2-measurement-contract-design-replay",
        "m4-v2-branch-identifiability-preflight-design",
        "m4-v2-p2-6-1-raw-execution-replay",
        "m4-v2-p2-7-measurement-gate-replay",
        "m4-v2-p2-6-1-marginal-binding",
        "m4-v2-p2-6-1-marginal-decision-replay",
        "m4-p2-9-measurement-runtime-audit",
        "m4-v2-global-routing",
    }
    live = copy.deepcopy(source)
    live["goals"] = [
        item
        for item in live["goals"]
        if item["goal_key"] != "M4_MEASUREMENT_RUNTIME_AUDIT"
    ]
    live["tasks"] = [
        item for item in live["tasks"] if item["task_key"] not in new_tasks
    ]
    p3_source = next(
        item for item in source["tasks"] if item["task_key"] == LEGACY_P3_TASK_KEY
    )
    p3_live = next(
        item for item in live["tasks"] if item["task_key"] == LEGACY_P3_TASK_KEY
    )
    p3_live["dependencies"] = [
        {
            "dependency_type": "task",
            "target_key": "m4-p2-synthetic-measurement-validation",
            "required_status": "completed",
        },
        {
            "dependency_type": "artifact",
            "target_key": "m4-p2-measurement-decision:PASS_TO_P3",
            "required_status": "available",
        },
    ]
    assert p3_live["dependencies"] != p3_source["dependencies"]
    additions = {
        item
        for item in source["facts"]["artifacts"]
        if item.startswith(
            (
                "m4-measurement-contract-v2",
                "m4-p2-6-1-marginal-binding-contract",
                "m4-p2-9-runtime-audit-plan",
            )
        )
    }
    live["facts"]["artifacts"] = [
        item for item in live["facts"]["artifacts"] if item not in additions
    ]
    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=("M4_MEASUREMENT_RUNTIME_AUDIT",),
        allowlisted_new_task_keys=new_tasks,
        allowlisted_revised_task_keys=(LEGACY_P3_TASK_KEY,),
        add_artifact_facts=additions,
        add_external_events=("m4-runtime-slot:p2-6-1-released",),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["existing_task_deletions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert set(live["facts"]["artifacts"]).issubset(migrated["facts"]["artifacts"])
    migrated_p3 = next(
        item for item in migrated["tasks"] if item["task_key"] == LEGACY_P3_TASK_KEY
    )
    assert migrated_p3["dependencies"] == p3_source["dependencies"]


def test_runtime_audit_equivalence_and_unavailable_metrics() -> None:
    plan = load_runtime_audit_plan(AUDIT_PATH)
    observer = RuntimeAuditObserver(enabled=False)
    assert observer.folds == 0
    payload = {"status": "COMPLETE", "value": [1, 2, 3]}
    children = [{"artifact_type": "child", "artifact_digest": "1" * 64}]
    attestation = build_equivalence_attestation(
        plan_digest=plan["artifact_digest"],
        reference_payload=payload,
        audited_payload=copy.deepcopy(payload),
        reference_child_artifacts=children,
        audited_child_artifacts=copy.deepcopy(children),
    )
    assert attestation["status"] == "EXACT_OUTPUT_EQUIVALENCE_VERIFIED"
    with pytest.raises(RuntimeAuditError, match="replicate payload changed"):
        build_equivalence_attestation(
            plan_digest=plan["artifact_digest"],
            reference_payload=payload,
            audited_payload={**payload, "value": [3, 2, 1]},
            reference_child_artifacts=children,
            audited_child_artifacts=children,
        )
    assert _io_deltas(None, None) == (UNAVAILABLE, UNAVAILABLE)


def test_runtime_observer_enabled_does_not_change_evaluator_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dehps.research_os.information_theory.measurement_system_v2 import (
        runtime_audit,
    )

    class _Evaluator:
        def evaluate(self, replicate: object) -> dict:
            return {"status": "COMPLETE", "payload": [1, 2, 3]}

    disabled = RuntimeAuditObserver(enabled=False)
    enabled = RuntimeAuditObserver(enabled=True)
    assert AuditedEvaluator(_Evaluator(), disabled).evaluate(object()) == (
        AuditedEvaluator(_Evaluator(), enabled).evaluate(object())
    )
    monkeypatch.setattr(runtime_audit, "_read_process_io", lambda: None)
    monkeypatch.setattr(runtime_audit, "_read_host_iowait_ticks", lambda: None)
    missing = RuntimeAuditObserver(enabled=True)
    with missing.phase("checkpoint_artifact_persistence"):
        pass
    observation = missing.observation(
        plan_digest="1" * 64,
        execution_id="2" * 64,
        git_commit="3" * 40,
    )
    assert observation["process_io_read_bytes"] == UNAVAILABLE
    assert observation["process_io_write_bytes"] == UNAVAILABLE
    assert observation["host_iowait_ticks_unattributed"] == UNAVAILABLE
    assert isinstance(observation["artifact_write_latency_ms_p50"], float)


def test_manifest_wires_replay_before_preflight_and_disconnects_legacy_p3() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    tasks = {item.task_key: item for item in manifest.tasks}
    preflight = tasks["m4-v2-branch-identifiability-preflight-design"]
    dependencies = {(item.dependency_type.value, item.target_key) for item in preflight.dependencies}
    assert ("task", "m4-v2-measurement-contract-design-replay") in dependencies
    assert ("artifact", "m4-measurement-contract-v2-design-replay:VERIFIED") in dependencies
    p3 = tasks[LEGACY_P3_TASK_KEY]
    p3_dependencies = {item.target_key for item in p3.dependencies}
    assert "m4-p2-measurement-decision:PASS_TO_P3" not in p3_dependencies
    assert "m4-v2-routing:ADAPTIVE_RESEARCH_ELIGIBLE" in p3_dependencies
    runtime = tasks["m4-p2-9-measurement-runtime-audit"]
    assert runtime.lane.value == "maintenance"
    assert "m4-runtime-slot:p2-6-1-released" in {
        item.target_key for item in runtime.dependencies
    }
