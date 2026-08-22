from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from dehps.config import ROOT_DIR
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.measurement_system_v2 import (
    formal_p4_forward_prequential as formal_p4,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import (
    CompletionClassification,
    ControlPlaneManifest,
    MainlineArtifactRegistration,
    ResearchOSValidationError,
    TaskStatus,
    jsonable,
)
from dehps.research_os.repository import PostgresResearchOSRepository


def _load_script(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT_DIR / path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _builder():
    return _load_script(
        "formal_p4_builder_test",
        "apps/worker-python/scripts/build_m4_p4_forward_prequential_manifest.py",
    )


def _runner():
    return _load_script(
        "formal_p4_runner_test",
        "apps/worker-python/scripts/run_m4_p4_forward_prequential.py",
    )


def _minimal_live_manifest() -> dict:
    goal = {
        "goal_key": formal_p4.p3.GOAL_KEY,
        "semantic_version": "1.0.0",
        "objective_class": "prediction_quality",
        "status": "active",
        "success_evidence": ["registered successor evidence"],
        "owner_lane": "research",
    }
    integration = {
        "goal": formal_p4.p3.GOAL_KEY,
        "ready_condition": "old scope stub plus successor PASS",
        "runner": "unregistered dormant capability",
        "upstream_artifacts": ["P3"],
        "downstream_artifacts": ["P4"],
        "status_projection": "dependency_wait",
        "evidence_progress_rule": "none before PASS",
        "decision_consumer": "P4",
        "downstream_consumer": "P4",
    }
    p4_task = {
        "task_key": formal_p4.EXECUTION_TASK_KEY,
        "goal_key": formal_p4.p3.GOAL_KEY,
        "task_type": "formal_p4_negative_controls_and_robustness",
        "lane": "research",
        "priority": 208,
        "dependencies": [
            {
                "dependency_type": "artifact",
                "target_key": formal_p4.p3.P4_PREREGISTRATION_FACT,
                "required_status": "available",
            },
            {
                "dependency_type": "artifact",
                "target_key": formal_p4.p3.P3_COMPLETE_FACT,
                "required_status": "available",
            },
            {
                "dependency_type": "artifact",
                "target_key": formal_p4.p3.PASS_TO_P4_FACT,
                "required_status": "available",
            },
        ],
        "input_artifact_digests": [formal_p4.P3_SOURCE_DIGEST],
        "requested_capability": formal_p4.EXECUTION_CAPABILITY,
        "metric_contract": {
            "engineering_complete": True,
            "evidence_complete": False,
            "mainline_integration": integration,
        },
    }
    legacy_p5 = {
        "task_key": formal_p4.LEGACY_P5_TASK_KEY,
        "goal_key": formal_p4.p3.GOAL_KEY,
        "task_type": "forward_evidence",
        "lane": "research",
        "priority": 70,
    }
    return {
        "schema_version": "research-os-control-plane-v1",
        "goals": [goal],
        "tasks": [p4_task, legacy_p5],
        "facts": {
            "artifacts": [formal_p4.p3.P4_PREREGISTRATION_FACT],
            "external_events": [],
        },
    }


def _compact_complete_execution(monkeypatch):
    monkeypatch.setattr(formal_p4, "PRIMARY_REPLICATES", 4)
    monkeypatch.setattr(formal_p4, "SENSITIVITY_REPLICATES", 8)
    prereg = formal_p4.frozen_preregistration()
    n = 20
    targets = [
        [((index + offset) % 33) + 1 for offset in range(6)] for index in range(n)
    ]
    models = []
    settlements = []
    gains = []
    for index, target in enumerate(targets):
        q = [3.0 / 27.0] * 33
        for number in target:
            q[number - 1] = 0.5
        models.append(
            formal_p4.p3._artifact(
                artifact_type=formal_p4.p3.MODEL_ARTIFACT_TYPE,
                body={"probabilities_q_1_to_33": q},
                parent_digests=(f"{index + 1:064x}",),
            )
        )
        settlements.append(
            formal_p4.p3._artifact(
                artifact_type=formal_p4.p3.SETTLEMENT_ARTIFACT_TYPE,
                body={"actual_red_numbers": target},
                parent_digests=(f"{index + 101:064x}",),
            )
        )
        gains.append(formal_p4._gain(q, target))
    review_digest = "a" * 64
    replay_digests = [f"{index + 201:064x}" for index in range(n)]
    checkpoint_digests = [f"{index + 301:064x}" for index in range(n)]
    dataset_digests = [f"{index + 401:064x}" for index in range(n)]
    projection = {
        "schema_version": "dehps-m4-p4-successor-p3-input-identity-projection.v1",
        "source_digest": formal_p4.P3_SOURCE_DIGEST,
        "review_artifact_digest": review_digest,
        "review_look": n,
        "review_issues": [f"fixture-{index:02d}" for index in range(n)],
        "settlement_artifact_digests": [
            item["artifact_digest"] for item in settlements
        ],
        "settlement_replay_artifact_digests": replay_digests,
        "checkpoint_artifact_digests": checkpoint_digests,
        "model_artifact_digests": [item["artifact_digest"] for item in models],
        "dataset_artifact_digests": dataset_digests,
        "preregistration_artifact_digest": formal_p4.P3_PREREGISTRATION_DIGEST,
        "lineage_id_derived": formal_p4.p3.LINEAGE_ID,
        "configuration_status_derived": "NO_DRIFT",
    }
    body = {
        "contract_key": formal_p4.CONTRACT_KEY,
        "contract_digest": formal_p4.CONTRACT_DIGEST,
        **{key: value for key, value in projection.items() if key != "schema_version"},
        "derived_projection": projection,
        "derived_projection_digest": formal_p4.m4_v2_domain_digest(
            projection,
            domain="dehps.m4.p4.successor-p3-input-identity-projection.v1",
        ),
        "training_horizon": n,
        "observed_gains": gains,
        "observed_mean_gain_bits_per_issue": sum(gains) / n,
        "status": "VALIDATED_RESULT_INPUT_IDENTITY",
    }
    parents = [
        review_digest,
        *projection["settlement_artifact_digests"],
        *replay_digests,
        *checkpoint_digests,
        *projection["model_artifact_digests"],
        *dataset_digests,
        formal_p4.P3_PREREGISTRATION_DIGEST,
        formal_p4.P3_SOURCE_DIGEST,
    ]
    identity = formal_p4._artifact(
        artifact_type=formal_p4.INPUT_IDENTITY_ARTIFACT_TYPE,
        body=body,
        parent_digests=parents,
    )
    children, summary = formal_p4.execute_controls(
        bundle={"models": models, "settlements": settlements},
        input_identity=identity,
        preregistration=prereg,
    )
    execution = formal_p4.build_execution_artifact(
        preregistration=prereg,
        input_identity=identity,
        children=children,
        summary=summary,
    )
    return prereg, identity, children, summary, execution


def test_source_contract_binds_v3_governance_and_exact_source_bytes() -> None:
    source = formal_p4.load_source_contract()
    assert source["contract_key"] == formal_p4.CONTRACT_KEY
    assert source["contract_digest"] == formal_p4.CONTRACT_DIGEST
    assert source["governance_bindings"]["research_request_id"] == 646
    assert source["governance_bindings"]["research_approval_decision_id"] == 2718
    assert source["governance_bindings"]["engineering_request_id"] == 648
    assert source["governance_bindings"]["engineering_approval_decision_id"] == 2724
    assert source["governance_bindings"]["engineering_execution_id"] == 527
    assert source["governance_bindings"]["import_repair_request_id"] == 652
    assert source["governance_bindings"]["import_repair_approval_decision_id"] == 2743
    assert source["governance_bindings"]["import_repair_execution_id"] == 530
    assert source["governance_bindings"]["completion_repair_request_id"] == 655
    assert (
        source["governance_bindings"]["completion_repair_approval_decision_id"] == 2756
    )
    assert source["governance_bindings"]["completion_repair_execution_id"] == 532
    prereg = formal_p4.formal_preregistration(source)
    assert prereg["body"]["status"] == "FROZEN_NOT_EXECUTED"
    assert prereg["parent_digests"] == [
        formal_p4.P3_PREREGISTRATION_DIGEST,
        formal_p4.P3_SOURCE_DIGEST,
    ]


def test_p3_source_entries_remain_byte_identical() -> None:
    source = formal_p4.p3.load_source_contract()
    assert source["artifact_digest"] == formal_p4.P3_SOURCE_DIGEST
    for entry in source["source_entries"]:
        content = (ROOT_DIR / entry["path"]).read_bytes()
        if "bytes" in entry:
            assert len(content) == entry["bytes"]
        assert hashlib.sha256(content).hexdigest() == entry["sha256"]


@pytest.mark.parametrize(
    "expected",
    (
        "P4_PASS_TO_P5",
        "P4_FAIL_NEGATIVE_CONTROLS_OR_ROBUSTNESS",
        "P4_INVALID_EXECUTION",
    ),
)
def test_result_blind_fixture_compiles_exact_decision_and_typed_replay(
    expected: str,
) -> None:
    first = formal_p4.synthetic_decision_fixture(expected)
    second = formal_p4.synthetic_decision_fixture(expected)
    decision = first[-2]
    replay = first[-1]
    assert first == second
    assert decision["body"]["decision"] == expected
    assert replay["body"]["decision_artifact_digest"] == decision["artifact_digest"]
    assert replay["body"]["same_registered_content"] is True
    assert replay["body"]["workload_rerun"] is False


def test_holm_uses_canonical_order_to_break_exact_ties() -> None:
    order = ("A", "B", "C")
    result = formal_p4.holm({"C": 0.02, "B": 0.01, "A": 0.01}, order)
    assert result["ranked_order"] == ["A", "B", "C"]
    assert result["adjusted_p_values"] == {"A": 0.03, "B": 0.03, "C": 0.03}
    assert result["all_rejected"] is True


def test_additive_manifest_arms_p4_and_preserves_legacy_p5(tmp_path) -> None:
    builder = _builder()
    source = formal_p4.load_source_contract()
    live = _minimal_live_manifest()
    definition, definition_dry_run = builder.build_definition_manifest(
        live, source_digest=source["artifact_digest"]
    )
    assert formal_p4.CONTRACT_FREEZE_FACT not in definition["facts"]["artifacts"]
    assert definition_dry_run["formal_p4_contract"] == "REGISTRATION_PENDING"
    prereg = formal_p4.frozen_preregistration()
    execution_id = "c" * 64
    registration_digest = "b" * 64
    task = next(
        item
        for item in ControlPlaneManifest.from_dict(definition).tasks
        if item.task_key == formal_p4.EXECUTION_TASK_KEY
    )
    relative = "registered/preregistration.json"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(prereg), encoding="utf-8")
    registration = {
        "registration_digest": registration_digest,
        "execution_id": execution_id,
        "control_plane_key": formal_p4.CONTROL_PLANE_KEY,
        "task_key": formal_p4.EXECUTION_TASK_KEY,
        "task_digest": task.artifact_digest,
        "artifact_digest": prereg["artifact_digest"],
        "artifact_type": prereg["artifact_type"],
        "schema_version": prereg["schema_version"],
        "artifact_path": relative,
        "parent_digests": prereg["parent_digests"],
    }

    class Repository:
        def list_mainline_artifacts(self, **kwargs):
            assert kwargs == {
                "control_plane_key": formal_p4.CONTROL_PLANE_KEY,
                "execution_id": execution_id,
            }
            return (registration,)

    output, dry_run = builder.build_frozen_manifest(
        definition,
        source_digest=source["artifact_digest"],
        repository=Repository(),
        registration_execution_id=execution_id,
        registration_digest=registration_digest,
        root_dir=tmp_path,
    )
    manifest = ControlPlaneManifest.from_dict(output)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    statuses = {item.task_key: item.status.value for item in snapshot.resolutions}
    assert dry_run["formal_p4_status"] == "ARMED_DEPENDENCY_WAIT"
    assert dry_run["formal_p4_contract"] == "FROZEN"
    assert formal_p4.CONTRACT_FREEZE_FACT in manifest.facts.artifacts
    assert statuses[formal_p4.EXECUTION_TASK_KEY] == "dependency_wait"
    assert all(
        statuses[key] == "dependency_wait" for key in formal_p4.P4_TASK_KEY_ALLOWLIST
    )
    assert statuses[formal_p4.SUCCESSOR_P5_TASK_KEY] == "dependency_wait"
    tasks = {item.task_key: item.to_dict() for item in manifest.tasks}
    assert (
        tasks[formal_p4.LEGACY_P5_TASK_KEY]
        == ControlPlaneManifest.from_dict(live).tasks[1].to_dict()
    )
    p5_dependencies = tasks[formal_p4.SUCCESSOR_P5_TASK_KEY]["dependencies"]
    assert p5_dependencies == [
        {
            "dependency_type": "task",
            "target_key": formal_p4.EXECUTION_TASK_KEY,
            "required_status": "completed",
        },
        {
            "dependency_type": "artifact",
            "target_key": formal_p4.PASS_TO_P5_FACT,
            "required_status": "available",
        },
        {
            "dependency_type": "artifact",
            "target_key": formal_p4.REPLAY_VERIFIED_FACT,
            "required_status": "available",
        },
    ]


def test_ephemeral_pass_fixture_makes_only_execution_p4_ready_then_restores() -> None:
    builder = _builder()
    source = formal_p4.load_source_contract()
    result = builder.activation_simulation(
        _minimal_live_manifest(), source_digest=source["artifact_digest"]
    )
    assert result["fixture_ready_p4_tasks"] == [formal_p4.EXECUTION_TASK_KEY]
    assert result["unique_capability"] == formal_p4.EXECUTION_CAPABILITY
    assert result["dispatch_performed"] is False
    assert result["fixture_persistent"] is False
    assert result["production_restored_status"] == "ARMED_DEPENDENCY_WAIT"
    assert result["formal_p4_executed"] is False


def test_runner_has_only_explicit_allowlisted_dispatch() -> None:
    runner = _runner()
    source = inspect.getsource(runner.cycle)
    assert "run_once(task_key=key)" in source
    assert "run_once()" not in source
    assert tuple(formal_p4.P4_TASK_KEY_ALLOWLIST) == (
        "m4-p4-forward-prequential-confirmatory-negative-controls",
        "m4-p4-forward-prequential-formal-evidence-v3",
        "m4-p4-forward-prequential-formal-decision-v3",
        "m4-p4-forward-prequential-formal-decision-replay-v3",
    )
    supervisor = formal_p4.FormalP4ForwardPrequentialSupervisor(
        repository=object(), control_plane_key=formal_p4.CONTROL_PLANE_KEY
    )
    assert all(name in supervisor.capabilities for name in formal_p4.CAPABILITIES)


def test_complete_nonfixture_execution_and_corruptions_compile_invalid(
    monkeypatch,
) -> None:
    prereg, identity, children, summary, execution = _compact_complete_execution(
        monkeypatch
    )
    evidence = formal_p4.compile_evidence(
        execution=execution,
        input_identity=identity,
        preregistration=prereg,
        children=children,
    )
    assert evidence["body"]["execution_valid"] is True
    assert evidence["body"]["invalid_reasons"] == []
    nc6 = [
        item
        for item in children
        if item["body"].get("control_id") == formal_p4.CONTROL_ORDER[5]
    ]
    assert all(item["body"]["selected_look"] == 20 for item in nc6)
    assert all(
        item["body"]["selected_look_decision"]
        == ("PASS_TO_P4" if item["body"]["selected_look_pass"] else "NOT_PASS_TO_P4")
        for item in nc6
    )

    missing = formal_p4.compile_evidence(
        execution=execution,
        input_identity=identity,
        preregistration=prereg,
        children=children[:-1],
    )
    assert missing["body"]["execution_valid"] is False

    reordered = [children[1], children[0], *children[2:]]
    reordered_execution = formal_p4.build_execution_artifact(
        preregistration=prereg,
        input_identity=identity,
        children=reordered,
        summary=summary,
    )
    reordered_evidence = formal_p4.compile_evidence(
        execution=reordered_execution,
        input_identity=identity,
        preregistration=prereg,
        children=reordered,
    )
    assert "FROZEN_CHILD_ORDER" in reordered_evidence["body"]["invalid_reasons"]

    duplicated = [children[0], children[0], *children[2:]]
    duplicated_execution = formal_p4.build_execution_artifact(
        preregistration=prereg,
        input_identity=identity,
        children=duplicated,
        summary=summary,
    )
    duplicated_evidence = formal_p4.compile_evidence(
        execution=duplicated_execution,
        input_identity=identity,
        preregistration=prereg,
        children=duplicated,
    )
    assert duplicated_evidence["body"]["execution_valid"] is False

    bad_body = deepcopy(children[0]["body"])
    bad_body["seed_digest"] = "f" * 64
    bad_child = formal_p4._artifact(
        artifact_type=formal_p4.CONTROL_CHILD_ARTIFACT_TYPE,
        body=bad_body,
        parent_digests=children[0]["parent_digests"],
    )
    wrong_seed_children = [bad_child, *children[1:]]
    wrong_seed_execution = formal_p4.build_execution_artifact(
        preregistration=prereg,
        input_identity=identity,
        children=wrong_seed_children,
        summary=summary,
    )
    wrong_seed_evidence = formal_p4.compile_evidence(
        execution=wrong_seed_execution,
        input_identity=identity,
        preregistration=prereg,
        children=wrong_seed_children,
    )
    assert any(
        reason.endswith("_SEED_IDENTITY")
        for reason in wrong_seed_evidence["body"]["invalid_reasons"]
    )

    for control_id, field, value, expected_reason in (
        (
            formal_p4.CONTROL_ORDER[2],
            "rng",
            "CHANGED",
            "NC3_DETERMINISTIC_COMPLETENESS",
        ),
        (
            formal_p4.CONTROL_ORDER[3],
            "dtype",
            "changed",
            "NC4_SENTINEL_IDENTITY",
        ),
        (
            formal_p4.SENSITIVITY_ORDER[0],
            "centered_null",
            False,
            "SENSITIVITY_CENTERED_NULL_IDENTITY",
        ),
    ):
        position = next(
            index
            for index, child in enumerate(children)
            if child["body"].get("control_id") == control_id
        )
        changed = deepcopy(children[position]["body"])
        changed[field] = value
        corrupted = formal_p4._artifact(
            artifact_type=children[position]["artifact_type"],
            body=changed,
            parent_digests=children[position]["parent_digests"],
        )
        corrupted_children = [*children]
        corrupted_children[position] = corrupted
        corrupted_execution = formal_p4.build_execution_artifact(
            preregistration=prereg,
            input_identity=identity,
            children=corrupted_children,
            summary=summary,
        )
        corrupted_evidence = formal_p4.compile_evidence(
            execution=corrupted_execution,
            input_identity=identity,
            preregistration=prereg,
            children=corrupted_children,
        )
        assert expected_reason in corrupted_evidence["body"]["invalid_reasons"]

    decision = formal_p4.compile_decision(
        evidence=evidence, execution=execution, preregistration=prereg
    )
    binding_invalid = formal_p4.compile_decision(
        evidence=evidence,
        execution=execution,
        preregistration=prereg,
        integrity_reasons=("SOURCE_TASK_OR_GOVERNANCE_BINDING",),
    )
    assert binding_invalid["body"]["decision"] == "P4_INVALID_EXECUTION"
    assert binding_invalid["body"]["binding_invalid_reasons"] == [
        "SOURCE_TASK_OR_GOVERNANCE_BINDING"
    ]
    changed_body = deepcopy(decision["body"])
    changed_body["emitted_fact"] = formal_p4.INVALID_FACT
    changed_decision = formal_p4._artifact(
        artifact_type=formal_p4.DECISION_ARTIFACT_TYPE,
        body=changed_body,
        parent_digests=decision["parent_digests"],
    )
    with pytest.raises(
        formal_p4.FormalP4ForwardPrequentialError,
        match="typed_replay_mismatch",
    ):
        formal_p4.build_typed_replay(
            decision=changed_decision,
            evidence=evidence,
            execution=execution,
            input_identity=identity,
            preregistration=prereg,
            children=children,
        )


def test_registered_child_loader_preserves_order_and_reports_integrity(
    monkeypatch, tmp_path
) -> None:
    prereg, identity, children, _, execution = _compact_complete_execution(monkeypatch)
    del prereg, identity
    execution_record = {"execution_id": "d" * 64, "task_digest": "e" * 64}
    registrations = []
    for index, child in enumerate(children):
        relative = f"children/{index:03d}.json"
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(child), encoding="utf-8")
        registrations.append(
            {
                "execution_id": execution_record["execution_id"],
                "control_plane_key": formal_p4.CONTROL_PLANE_KEY,
                "task_key": formal_p4.EXECUTION_TASK_KEY,
                "task_digest": execution_record["task_digest"],
                "artifact_digest": child["artifact_digest"],
                "artifact_type": child["artifact_type"],
                "schema_version": child["schema_version"],
                "artifact_path": relative,
                "parent_digests": child["parent_digests"],
            }
        )

    class Repository:
        def list_mainline_artifacts(self, **kwargs):
            assert kwargs["execution_id"] == execution_record["execution_id"]
            return tuple(registrations)

    capability = formal_p4.FormalP4ForwardPrequentialCapability(
        repository=Repository(), root_dir=tmp_path
    )
    monkeypatch.setattr(
        capability,
        "_completed_artifact",
        lambda **kwargs: (execution_record, {}, execution),
    )
    loaded_execution, loaded, reasons = capability._registered_execution_children(
        control_plane_key=formal_p4.CONTROL_PLANE_KEY
    )
    assert loaded_execution == execution
    assert loaded == children
    assert reasons == []
    registrations.pop()
    _, loaded, reasons = capability._registered_execution_children(
        control_plane_key=formal_p4.CONTROL_PLANE_KEY
    )
    assert len(loaded) == len(children) - 1
    assert reasons == ["CHILD_REGISTRATION_SET"]
    bad = deepcopy(registrations[0])
    bad["schema_version"] = "changed"
    registrations[0] = bad
    _, loaded, reasons = capability._registered_execution_children(
        control_plane_key=formal_p4.CONTROL_PLANE_KEY
    )
    assert len(loaded) == len(children) - 2
    assert reasons == ["CHILD_REGISTRATION_OR_CONTENT", "CHILD_REGISTRATION_SET"]


def test_top_level_registration_failure_builds_fail_closed_chain(monkeypatch) -> None:
    class Repository:
        pass

    capability = formal_p4.FormalP4ForwardPrequentialCapability(
        repository=Repository(), root_dir=ROOT_DIR
    )

    def missing(**kwargs):
        raise formal_p4.MainlineSupervisorError("missing")

    monkeypatch.setattr(capability, "_completed_artifact", missing)
    prereg, identity, execution, children, reasons = (
        capability._execution_chain_fail_closed(
            control_plane_key=formal_p4.CONTROL_PLANE_KEY
        )
    )
    assert prereg == formal_p4.frozen_preregistration()
    assert identity["body"]["status"] == "INVALID_INPUT_IDENTITY"
    assert execution["body"]["formal_p4_execution"] == "INVALID_BEFORE_WORKLOAD"
    assert children == []
    assert reasons == [
        "TOP_LEVEL_EXECUTION_REGISTRATION",
        "TOP_LEVEL_INPUT_IDENTITY_REGISTRATION",
        "TOP_LEVEL_PREREGISTRATION_REGISTRATION",
    ]


def test_outcome_activation_requires_generic_and_registered_typed_replay(
    monkeypatch,
) -> None:
    runner = _runner()
    builder = _builder()
    prereg, identity, execution, evidence, decision, replay = (
        formal_p4.synthetic_decision_fixture("P4_PASS_TO_P5")
    )
    definition, _ = builder.build_manifest(
        _minimal_live_manifest(), source_digest="a" * 64
    )

    class Repository(runner.FormalP4ForwardPrequentialRepository):
        def __init__(self):
            self.imported = []
            self._outcome_gate = None

        def export_manifest(self, **kwargs):
            return definition

        def _import_authoritative_outcome(self, **kwargs):
            self.imported.append(kwargs["payload"])
            return "fixture-import"

    repository = Repository()

    class Capability:
        def __init__(self, **kwargs):
            pass

        def _execution_chain_fail_closed(self, **kwargs):
            return prereg, identity, execution, [], []

        def _completed_artifact(self, **kwargs):
            artifact_type = kwargs["artifact_type"]
            values = {
                formal_p4.EVIDENCE_ARTIFACT_TYPE: evidence,
                formal_p4.DECISION_ARTIFACT_TYPE: decision,
                formal_p4.REPLAY_ARTIFACT_TYPE: replay,
            }
            artifact = values[artifact_type]
            registration = {
                "artifact_digest": artifact["artifact_digest"],
                "registration_digest": "f" * 64,
            }
            return {}, registration, artifact

    monkeypatch.setattr(
        runner.formal_p4, "FormalP4ForwardPrequentialCapability", Capability
    )
    generic = {
        "status": "REPLAY_VERIFIED",
        "task_key": formal_p4.REPLAY_TASK_KEY,
        "execution_id": "e" * 64,
        "same_execution_identity": True,
        "same_artifact_identity": True,
        "manual_input_assembly": False,
        "dispatch_performed": False,
    }
    activated = runner._activate_after_generic_replay(
        repository=repository,
        supervisor=object(),
        generic_replay=generic,
    )
    assert activated["typed_replay_verified"] is True
    assert activated["outcome_fact"] == formal_p4.PASS_TO_P5_FACT
    imported_facts = repository.imported[0]["facts"]["artifacts"]
    assert formal_p4.PASS_TO_P5_FACT in imported_facts
    assert formal_p4.REPLAY_VERIFIED_FACT in imported_facts

    repository.imported.clear()
    generic["same_artifact_identity"] = False
    with pytest.raises(RuntimeError, match="generic replay"):
        runner._activate_after_generic_replay(
            repository=repository,
            supervisor=object(),
            generic_replay=generic,
        )
    assert repository.imported == []


def test_cycle_resumes_crash_after_replay_complete_before_outcome(monkeypatch) -> None:
    runner = _runner()

    class Repository:
        def ensure_schema(self):
            return None

    repository = Repository()
    manifest = SimpleNamespace(
        facts=SimpleNamespace(
            to_dict=lambda: {"artifacts": [f"{formal_p4.REPLAY_TASK_KEY}:COMPLETE"]}
        )
    )
    resolutions = [
        SimpleNamespace(
            task_key=key,
            status=SimpleNamespace(
                value="completed"
                if key == formal_p4.REPLAY_TASK_KEY
                else "dependency_wait"
            ),
        )
        for key in formal_p4.P4_TASK_KEY_ALLOWLIST
    ]
    snapshot = SimpleNamespace(resolutions=resolutions)
    generic = {
        "status": "REPLAY_VERIFIED",
        "task_key": formal_p4.REPLAY_TASK_KEY,
        "execution_id": "e" * 64,
        "same_execution_identity": True,
        "same_artifact_identity": True,
        "manual_input_assembly": False,
        "dispatch_performed": False,
    }

    class Supervisor:
        def __init__(self, **kwargs):
            pass

        def replay(self, *, task_key):
            assert task_key == formal_p4.REPLAY_TASK_KEY
            return generic

    monkeypatch.setattr(runner.formal_p4, "load_source_contract", lambda **kwargs: {})
    monkeypatch.setattr(runner.formal_p4, "verify_governance", lambda repository: None)
    monkeypatch.setattr(runner, "AgentRequestRepository", lambda: object())
    monkeypatch.setattr(runner, "_snapshot", lambda repository: (manifest, snapshot))
    monkeypatch.setattr(
        runner.formal_p4, "FormalP4ForwardPrequentialSupervisor", Supervisor
    )
    monkeypatch.setattr(
        runner,
        "_activate_after_generic_replay",
        lambda **kwargs: {"status": "ACTIVATED"},
    )
    result = runner.cycle(apply=True, repository=repository)
    assert result["status"] == "RESUMED_POST_REPLAY_OUTCOME_ACTIVATION"
    assert result["dispatch_performed"] is False
    assert result["workload_rerun"] is False
    assert result["outcome_activation"] == {"status": "ACTIVATED"}


class _Rows:
    def __init__(self, *, one=None, many=()):
        self.one = one
        self.many = many

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class _P4ImportCursor:
    def __init__(
        self,
        current: ControlPlaneManifest,
        *,
        registrations=(),
        completed_event: bool = True,
        registered_artifact: bool = True,
    ):
        self.current = current
        self.registrations = tuple(registrations)
        self.completed_event = completed_event
        self.registered_artifact = registered_artifact

    def execute(self, statement, parameters=()):
        query = " ".join(str(statement).split())
        assert query.startswith("SELECT")
        if "FROM research_os_control_planes" in query:
            return _Rows(one={"current_manifest_digest": self.current.artifact_digest})
        if "FROM research_os_manifests" in query:
            assert parameters == (self.current.artifact_digest,)
            return _Rows(
                one={"manifest_json": self.current.to_dict(include_digest=True)}
            )
        if "FROM research_os_mainline_execution_events" in query:
            return _Rows(one={"exists": 1} if self.completed_event else None)
        if (
            query.startswith("SELECT 1")
            and "FROM research_os_mainline_artifacts" in query
        ):
            return _Rows(one={"exists": 1} if self.registered_artifact else None)
        if "FROM research_os_mainline_artifacts" in query:
            return _Rows(many=self.registrations)
        raise AssertionError(query)


def _p4_definition_and_freeze(base: ControlPlaneManifest | None = None):
    builder = _builder()
    source = formal_p4.load_source_contract()
    definition_payload, _ = builder.build_definition_manifest(
        (
            _minimal_live_manifest()
            if base is None
            else base.to_dict(include_digest=True)
        ),
        source_digest=str(source["artifact_digest"]),
    )
    definition = ControlPlaneManifest.from_dict(definition_payload)
    frozen_payload, _ = builder._build_manifest(
        definition.to_dict(include_digest=True),
        source_digest=str(source["artifact_digest"]),
        include_freeze_fact=True,
    )
    return definition, ControlPlaneManifest.from_dict(frozen_payload)


def _arming_registration_row(runner, root, manifest):
    task = next(
        item for item in manifest.tasks if item.task_key == formal_p4.EXECUTION_TASK_KEY
    )
    prereg = formal_p4.frozen_preregistration()
    relative = (
        "runtime/research-os/mainline/tasks/"
        f"{task.task_key}/{runner.ARMING_EXECUTION_ID}/artifacts/"
        f"formal-p4-v3-preregistration/{prereg['artifact_digest']}/"
        "preregistration.json"
    )
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            prereg,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    registration = MainlineArtifactRegistration(
        execution_id=runner.ARMING_EXECUTION_ID,
        control_plane_key=formal_p4.CONTROL_PLANE_KEY,
        task_key=task.task_key,
        task_digest=task.artifact_digest,
        artifact_digest=str(prereg["artifact_digest"]),
        artifact_type=str(prereg["artifact_type"]),
        schema_version=str(prereg["schema_version"]),
        artifact_path=relative,
        parent_digests=tuple(str(item) for item in prereg["parent_digests"]),
        git_commit="a" * 40,
    )
    return {
        "registration_digest": registration.registration_digest,
        "execution_id": registration.execution_id,
        "control_plane_key": registration.control_plane_key,
        "task_digest": registration.task_digest,
        "task_key": registration.task_key,
        "artifact_digest": registration.artifact_digest,
        "artifact_type": registration.artifact_type,
        "schema_version": registration.schema_version,
        "artifact_path": registration.artifact_path,
        "parent_digests_json": list(registration.parent_digests),
        "git_commit": registration.git_commit,
        "registration_json": jsonable(registration),
    }


def _p4_repository(runner):
    repository = object.__new__(runner.FormalP4ForwardPrequentialRepository)
    repository._outcome_gate = None
    return repository


def _task_state(
    manifest: ControlPlaneManifest,
    *,
    task_key: str,
    status: str,
    classification: str,
    facts=(),
) -> ControlPlaneManifest:
    payload = manifest.to_dict(include_digest=False)
    task = next(item for item in payload["tasks"] if item["task_key"] == task_key)
    task["status"] = status
    task["completion_classification"] = classification
    payload["facts"]["artifacts"] = sorted({*payload["facts"]["artifacts"], *facts})
    return ControlPlaneManifest.from_dict(payload)


def _historical_recovery_base(
    *, completion_probe: bool = False
) -> ControlPlaneManifest:
    payload = _minimal_live_manifest()
    payload["tasks"].append(
        {
            "task_key": "m4-v2-global-routing-recovery-v3",
            "goal_key": formal_p4.p3.GOAL_KEY,
            "task_type": "historical_recovery_fixture",
            "lane": "research",
            "priority": 10,
            "status": TaskStatus.COMPLETED.value,
            "completion_classification": CompletionClassification.COMPLETE.value,
        }
    )
    if completion_probe:
        payload["tasks"].append(
            {
                "task_key": "p4-completion-verifier-generic-probe",
                "goal_key": formal_p4.p3.GOAL_KEY,
                "task_type": "generic_completion_probe",
                "lane": "research",
                "priority": 1,
                "requested_capability": "generic_completion_probe",
                "status": TaskStatus.COMPLETED.value,
                "completion_classification": CompletionClassification.COMPLETE.value,
            }
        )
    manifest = ControlPlaneManifest.from_dict(payload)
    if not completion_probe:
        return manifest
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == "p4-completion-verifier-generic-probe"
    )
    payload = manifest.to_dict(include_digest=False)
    payload["facts"]["artifacts"] = sorted(
        {
            *payload["facts"]["artifacts"],
            mainline_completion_fact(task=task, execution_id="d" * 64),
        }
    )
    return ControlPlaneManifest.from_dict(payload)


def test_p4_only_repository_accepts_exact_definition_and_attested_freeze(
    tmp_path,
) -> None:
    runner = _runner()
    repository = _p4_repository(runner)
    base = ControlPlaneManifest.from_dict(_minimal_live_manifest())
    definition, frozen = _p4_definition_and_freeze()
    assert (
        repository._verify_formal_p4_v3_import(
            _P4ImportCursor(base),
            control_plane_key=formal_p4.CONTROL_PLANE_KEY,
            manifest=definition,
        )
        is True
    )
    assert (
        repository._verify_formal_p4_v3_import(
            _P4ImportCursor(definition),
            control_plane_key=formal_p4.CONTROL_PLANE_KEY,
            manifest=definition,
        )
        is True
    )
    with pytest.raises(
        ResearchOSValidationError,
        match="formal_p4_v3_arming_registration_changed",
    ):
        repository._verify_formal_p4_v3_import(
            _P4ImportCursor(definition),
            control_plane_key=formal_p4.CONTROL_PLANE_KEY,
            manifest=frozen,
            artifact_root=tmp_path,
        )
    row = _arming_registration_row(runner, tmp_path, frozen)
    assert (
        repository._verify_formal_p4_v3_import(
            _P4ImportCursor(definition, registrations=[row]),
            control_plane_key=formal_p4.CONTROL_PLANE_KEY,
            manifest=frozen,
            artifact_root=tmp_path,
        )
        is True
    )


def test_p4_only_repository_routes_exact_v3_before_legacy_and_delegates_after(
    monkeypatch,
) -> None:
    runner = _runner()
    repository = _p4_repository(runner)
    base = ControlPlaneManifest.from_dict(_minimal_live_manifest())
    definition, frozen = _p4_definition_and_freeze()
    delegated: list[str] = []

    def legacy(self, cursor, *, control_plane_key, manifest):
        del self, cursor, manifest
        delegated.append(control_plane_key)

    monkeypatch.setattr(
        PostgresResearchOSRepository,
        "_verify_m4_v2_failed_global_routing_recovery_v3_import",
        legacy,
    )
    repository._verify_m4_v2_failed_global_routing_recovery_v3_import(
        _P4ImportCursor(base),
        control_plane_key=formal_p4.CONTROL_PLANE_KEY,
        manifest=base,
    )
    assert delegated == [formal_p4.CONTROL_PLANE_KEY]
    repository._verify_m4_v2_failed_global_routing_recovery_v3_import(
        _P4ImportCursor(base),
        control_plane_key=formal_p4.CONTROL_PLANE_KEY,
        manifest=definition,
    )
    assert delegated == [formal_p4.CONTROL_PLANE_KEY]
    repository._verify_m4_v2_failed_global_routing_recovery_v3_import(
        _P4ImportCursor(frozen),
        control_plane_key=formal_p4.CONTROL_PLANE_KEY,
        manifest=frozen,
    )
    assert delegated == [
        formal_p4.CONTROL_PLANE_KEY,
        formal_p4.CONTROL_PLANE_KEY,
    ]


def test_p4_only_completion_verifier_uses_state_only_historical_projection() -> None:
    runner = _runner()
    repository = _p4_repository(runner)
    base = _historical_recovery_base()
    definition, _ = _p4_definition_and_freeze(base)
    original = definition.to_dict(include_digest=True)
    projection = repository._completion_verification_projection(definition)
    expected = definition.to_dict(include_digest=False)
    recovery = next(
        item
        for item in expected["tasks"]
        if item["task_key"] == runner.HISTORICAL_RECOVERY_V3_TASK_KEY
    )
    recovery["status"] = TaskStatus.RUNNING.value
    recovery["completion_classification"] = CompletionClassification.INTEGRATED.value
    assert projection.to_dict(include_digest=False) == expected
    assert definition.to_dict(include_digest=True) == original
    assert definition.artifact_digest == original["manifest_digest"]
    repository._verify_mainline_completion_records(
        _P4ImportCursor(base),
        control_plane_key=formal_p4.CONTROL_PLANE_KEY,
        manifest=definition,
        m4_v2_lifecycle_verified=True,
    )
    assert definition.to_dict(include_digest=True) == original


@pytest.mark.parametrize(
    ("completed_event", "registered_artifact", "error"),
    (
        (
            False,
            True,
            "completion fact has no immutable completed mainline execution event",
        ),
        (True, False, "completion fact has no registered mainline artifact"),
        (True, True, None),
    ),
)
def test_p4_only_completion_verifier_preserves_generic_integrity_checks(
    completed_event: bool,
    registered_artifact: bool,
    error: str | None,
) -> None:
    runner = _runner()
    repository = _p4_repository(runner)
    base = _historical_recovery_base(completion_probe=True)
    definition, _ = _p4_definition_and_freeze(base)
    cursor = _P4ImportCursor(
        base,
        completed_event=completed_event,
        registered_artifact=registered_artifact,
    )
    if error is not None:
        with pytest.raises(ResearchOSValidationError, match=error):
            repository._verify_mainline_completion_records(
                cursor,
                control_plane_key=formal_p4.CONTROL_PLANE_KEY,
                manifest=definition,
                m4_v2_lifecycle_verified=True,
            )
        return
    repository._verify_mainline_completion_records(
        cursor,
        control_plane_key=formal_p4.CONTROL_PLANE_KEY,
        manifest=definition,
        m4_v2_lifecycle_verified=True,
    )


def test_p4_only_completion_verifier_delegates_pure_non_v3_manifest(
    monkeypatch,
) -> None:
    runner = _runner()
    repository = _p4_repository(runner)
    base = ControlPlaneManifest.from_dict(_minimal_live_manifest())
    observed = []

    def generic(cursor, *, control_plane_key, manifest, m4_v2_lifecycle_verified):
        observed.append((cursor, control_plane_key, manifest, m4_v2_lifecycle_verified))

    monkeypatch.setattr(
        PostgresResearchOSRepository,
        "_verify_mainline_completion_records",
        staticmethod(generic),
    )
    cursor = object()
    repository._verify_mainline_completion_records(
        cursor,
        control_plane_key=formal_p4.CONTROL_PLANE_KEY,
        manifest=base,
        m4_v2_lifecycle_verified=False,
    )
    assert observed == [(cursor, formal_p4.CONTROL_PLANE_KEY, base, False)]


@pytest.mark.parametrize(
    "marker",
    (
        formal_p4.EVIDENCE_TASK_KEY,
        formal_p4.DECISION_TASK_KEY,
        formal_p4.REPLAY_TASK_KEY,
        formal_p4.SUCCESSOR_P5_TASK_KEY,
    ),
)
def test_p4_only_repository_rejects_every_partial_v3_marker(marker: str) -> None:
    runner = _runner()
    repository = _p4_repository(runner)
    base = ControlPlaneManifest.from_dict(_minimal_live_manifest())
    definition, _ = _p4_definition_and_freeze()
    payload = base.to_dict(include_digest=False)
    source_task = next(
        item
        for item in definition.to_dict(include_digest=False)["tasks"]
        if item["task_key"] == marker
    )
    payload["tasks"].append(source_task)
    partial = ControlPlaneManifest.from_dict(payload)
    with pytest.raises(
        ResearchOSValidationError,
        match="formal_p4_v3_repository_import_changed",
    ):
        repository._verify_m4_v2_failed_global_routing_recovery_v3_import(
            _P4ImportCursor(base),
            control_plane_key=formal_p4.CONTROL_PLANE_KEY,
            manifest=partial,
        )


@pytest.mark.parametrize(
    "fact",
    (
        formal_p4.CONTRACT_FREEZE_FACT,
        formal_p4.EXECUTION_COMPLETE_FACT,
        formal_p4.EVIDENCE_COMPILED_FACT,
        f"{formal_p4.DECISION_TASK_KEY}:COMPLETE",
        formal_p4.PASS_TO_P5_FACT,
        formal_p4.FAIL_FACT,
        formal_p4.INVALID_FACT,
        f"{formal_p4.REPLAY_TASK_KEY}:COMPLETE",
        formal_p4.REPLAY_VERIFIED_FACT,
        f"{formal_p4.SUCCESSOR_P5_TASK_KEY}:COMPLETE",
    ),
)
def test_p4_only_repository_rejects_every_standalone_v3_fact(fact: str) -> None:
    runner = _runner()
    repository = _p4_repository(runner)
    base = ControlPlaneManifest.from_dict(_minimal_live_manifest())
    payload = base.to_dict(include_digest=False)
    payload["facts"]["artifacts"] = sorted({*payload["facts"]["artifacts"], fact})
    partial = ControlPlaneManifest.from_dict(payload)
    with pytest.raises(
        ResearchOSValidationError,
        match="formal_p4_v3_repository_import_changed",
    ):
        repository._verify_m4_v2_failed_global_routing_recovery_v3_import(
            _P4ImportCursor(base),
            control_plane_key=formal_p4.CONTROL_PLANE_KEY,
            manifest=partial,
        )


@pytest.mark.parametrize(
    "corruption",
    ("duplicate", "execution", "path", "parents", "git_column", "content"),
)
def test_p4_only_repository_rejects_registration_drift(
    tmp_path,
    corruption: str,
) -> None:
    runner = _runner()
    repository = _p4_repository(runner)
    definition, frozen = _p4_definition_and_freeze()
    row = _arming_registration_row(runner, tmp_path, frozen)
    rows = [row]
    if corruption == "duplicate":
        rows.append(deepcopy(row))
    elif corruption == "content":
        (tmp_path / row["artifact_path"]).write_text("{}\n", encoding="utf-8")
    elif corruption == "parents":
        row["parent_digests_json"] = ["0" * 64]
    elif corruption == "git_column":
        row["git_commit"] = "b" * 40
    else:
        field = "execution_id" if corruption == "execution" else "artifact_path"
        row[field] = f"changed-{row[field]}"
    with pytest.raises(
        ResearchOSValidationError,
        match="formal_p4_v3_arming_registration_changed",
    ):
        repository._verify_formal_p4_v3_import(
            _P4ImportCursor(definition, registrations=rows),
            control_plane_key=formal_p4.CONTROL_PLANE_KEY,
            manifest=frozen,
            artifact_root=tmp_path,
        )


def test_p4_only_repository_accepts_exact_running_and_completed_transitions() -> None:
    runner = _runner()
    repository = _p4_repository(runner)
    _, frozen = _p4_definition_and_freeze()
    running = _task_state(
        frozen,
        task_key=formal_p4.EXECUTION_TASK_KEY,
        status=TaskStatus.RUNNING.value,
        classification=CompletionClassification.INTEGRATED.value,
    )
    repository._verify_post_freeze_transition(current=frozen, incoming=running)
    task = next(
        item for item in running.tasks if item.task_key == formal_p4.EXECUTION_TASK_KEY
    )
    completed = _task_state(
        running,
        task_key=formal_p4.EXECUTION_TASK_KEY,
        status=TaskStatus.COMPLETED.value,
        classification=CompletionClassification.COMPLETE.value,
        facts=(
            formal_p4.EXECUTION_COMPLETE_FACT,
            mainline_completion_fact(task=task, execution_id="b" * 64),
        ),
    )
    repository._verify_post_freeze_transition(current=running, incoming=completed)


@pytest.mark.parametrize(
    "fact",
    (
        formal_p4.p3.PASS_TO_P4_FACT,
        formal_p4.PASS_TO_P5_FACT,
        formal_p4.FAIL_FACT,
        formal_p4.INVALID_FACT,
        "promotion:TRIGGERED",
        "unapproved:FACT",
    ),
)
def test_p4_only_repository_rejects_direct_or_arbitrary_facts(fact: str) -> None:
    runner = _runner()
    repository = _p4_repository(runner)
    _, frozen = _p4_definition_and_freeze()
    payload = frozen.to_dict(include_digest=False)
    payload["facts"]["artifacts"] = sorted({*payload["facts"]["artifacts"], fact})
    changed = ControlPlaneManifest.from_dict(payload)
    with pytest.raises(
        ResearchOSValidationError,
        match="formal_p4_v3_post_freeze_transition_changed",
    ):
        repository._verify_post_freeze_transition(current=frozen, incoming=changed)


def _completed_replay_manifest() -> ControlPlaneManifest:
    _, frozen = _p4_definition_and_freeze()
    payload = frozen.to_dict(include_digest=False)
    for task in payload["tasks"]:
        if task["task_key"] in formal_p4.P4_TASK_KEY_ALLOWLIST:
            task["status"] = TaskStatus.COMPLETED.value
            task["completion_classification"] = CompletionClassification.COMPLETE.value
    replay = next(
        item
        for item in ControlPlaneManifest.from_dict(payload).tasks
        if item.task_key == formal_p4.REPLAY_TASK_KEY
    )
    payload["facts"]["artifacts"] = sorted(
        {
            *payload["facts"]["artifacts"],
            f"{formal_p4.REPLAY_TASK_KEY}:COMPLETE",
            mainline_completion_fact(task=replay, execution_id="c" * 64),
        }
    )
    return ControlPlaneManifest.from_dict(payload)


@pytest.mark.parametrize(
    ("outcome", "typed_replay_verified", "accepted"),
    (
        (formal_p4.PASS_TO_P5_FACT, True, True),
        (formal_p4.FAIL_FACT, True, True),
        (formal_p4.INVALID_FACT, True, True),
        (formal_p4.INVALID_FACT, False, True),
        (formal_p4.PASS_TO_P5_FACT, False, False),
        (formal_p4.FAIL_FACT, False, False),
    ),
)
def test_p4_only_outcome_gate_full_router_then_completion_is_single_use(
    monkeypatch,
    outcome: str,
    typed_replay_verified: bool,
    accepted: bool,
) -> None:
    runner = _runner()
    repository = _p4_repository(runner)
    current = _completed_replay_manifest()
    payload = current.to_dict(include_digest=False)
    added = frozenset(
        ({formal_p4.REPLAY_VERIFIED_FACT, outcome})
        if typed_replay_verified
        else {outcome}
    )
    payload["facts"]["artifacts"] = sorted({*payload["facts"]["artifacts"], *added})
    incoming = ControlPlaneManifest.from_dict(payload)
    cursor = _P4ImportCursor(current)

    with pytest.raises(ResearchOSValidationError):
        repository._verify_post_freeze_transition(
            current=current,
            incoming=incoming,
        )

    def import_fixture(self, **kwargs):
        assert kwargs["source"] == ("m4-p4-v3-outcome-after-generic-and-typed-replay")
        candidate = ControlPlaneManifest.from_dict(kwargs["payload"])
        self._verify_m4_v2_failed_global_routing_recovery_v3_import(
            cursor,
            control_plane_key=formal_p4.CONTROL_PLANE_KEY,
            manifest=candidate,
        )
        assert self._outcome_gate is not None
        assert self._outcome_gate["consumed"] is True
        self._verify_mainline_completion_records(
            cursor,
            control_plane_key=formal_p4.CONTROL_PLANE_KEY,
            manifest=candidate,
            m4_v2_lifecycle_verified=True,
        )
        return "outcome-imported"

    monkeypatch.setattr(
        PostgresResearchOSRepository,
        "_verify_m4_v2_failed_global_routing_recovery_v3_import",
        lambda self, cursor, *, control_plane_key, manifest: None,
    )
    monkeypatch.setattr(
        PostgresResearchOSRepository,
        "import_manifest",
        import_fixture,
    )
    if accepted:
        result = repository._import_authoritative_outcome(
            payload=incoming.to_dict(include_digest=True),
            outcome_fact=outcome,
            typed_replay_verified=typed_replay_verified,
        )
        assert result == "outcome-imported"
    else:
        with pytest.raises(
            ResearchOSValidationError,
            match="formal_p4_v3_outcome_gate_changed",
        ):
            repository._import_authoritative_outcome(
                payload=incoming.to_dict(include_digest=True),
                outcome_fact=outcome,
                typed_replay_verified=typed_replay_verified,
            )
    assert repository._outcome_gate is None
    repository._outcome_gate = {"already": "open"}
    with pytest.raises(
        ResearchOSValidationError,
        match="formal_p4_v3_outcome_gate_reentrant",
    ):
        repository._import_authoritative_outcome(
            payload=incoming.to_dict(include_digest=True),
            outcome_fact=outcome,
            typed_replay_verified=typed_replay_verified,
        )
    repository._outcome_gate = None


@pytest.mark.parametrize("corruption", ("digest", "facts", "not_consumed"))
def test_p4_only_completion_verifier_rejects_unattested_outcome_gate(
    corruption: str,
) -> None:
    runner = _runner()
    repository = _p4_repository(runner)
    current = _completed_replay_manifest()
    payload = current.to_dict(include_digest=False)
    added = frozenset({formal_p4.REPLAY_VERIFIED_FACT, formal_p4.PASS_TO_P5_FACT})
    payload["facts"]["artifacts"] = sorted({*payload["facts"]["artifacts"], *added})
    incoming = ControlPlaneManifest.from_dict(payload)
    repository._outcome_gate = {
        "manifest_digest": (
            "0" * 64 if corruption == "digest" else incoming.artifact_digest
        ),
        "added_facts": (
            frozenset({"unapproved:FACT"}) if corruption == "facts" else added
        ),
        "consumed": corruption != "not_consumed",
    }
    with pytest.raises(
        ResearchOSValidationError,
        match="formal_p4_v3_completion_outcome_attestation_changed",
    ):
        repository._verify_mainline_completion_records(
            _P4ImportCursor(current),
            control_plane_key=formal_p4.CONTROL_PLANE_KEY,
            manifest=incoming,
            m4_v2_lifecycle_verified=True,
        )
    repository._outcome_gate = None


def test_p4_only_repository_rejects_freeze_removal_and_definition_change() -> None:
    runner = _runner()
    repository = _p4_repository(runner)
    definition, frozen = _p4_definition_and_freeze()
    with pytest.raises(
        ResearchOSValidationError,
        match="formal_p4_v3_repository_import_changed",
    ):
        repository._verify_formal_p4_v3_import(
            _P4ImportCursor(frozen),
            control_plane_key=formal_p4.CONTROL_PLANE_KEY,
            manifest=definition,
        )
    payload = frozen.to_dict(include_digest=False)
    task = next(
        item
        for item in payload["tasks"]
        if item["task_key"] == formal_p4.EVIDENCE_TASK_KEY
    )
    task["priority"] += 1
    changed = ControlPlaneManifest.from_dict(payload)
    with pytest.raises(
        ResearchOSValidationError,
        match="formal_p4_v3_post_freeze_transition_changed",
    ):
        repository._verify_post_freeze_transition(current=frozen, incoming=changed)
