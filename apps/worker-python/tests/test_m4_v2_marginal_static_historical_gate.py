from __future__ import annotations

import copy
import json
import shutil
from dataclasses import asdict, replace

import pytest
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_historical_gate import (
    GATE_COMPILER_CONTRACT_DIGEST,
    HISTORICAL_EXECUTION_COMPLETION_FACT,
    HISTORICAL_EXECUTION_ID,
    HISTORICAL_EXECUTION_TASK_KEY,
    MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT,
    MARGINAL_STATIC_HISTORICAL_GATE_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
    PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
    MarginalStaticHistoricalGateError,
    build_marginal_static_historical_gate_artifacts,
    load_marginal_static_historical_gate_source_contract,
    verify_marginal_static_historical_gate_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    M4MarginalStaticHistoricalGateCapability,
    ResearchEvidenceSupervisor,
)

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"


def _artifact(*, domain: str, artifact_type: str, body: dict) -> dict:
    payload = {"artifact_type": artifact_type, "artifact_digest": "", **body}
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _parents(
    *,
    raw_p: float,
    lower: float,
    upper: float,
    equivalence_upper: float,
    mde: float | None,
    power_sufficient: bool,
    half_means: list[float],
) -> dict[str, dict]:
    endpoint = "1" * 64
    shards = [
        {
            "shard_index": index,
            "artifact_digest": f"{index + 2:064x}",
            "counts_after_digest": f"{index + 20:064x}",
        }
        for index in range(11)
    ]
    completion_index = _artifact(
        domain="dehps.m4.v2.marginal-static-historical-completion-index.v1",
        artifact_type="m4_v2_marginal_static_historical_completion_index",
        body={
            "status": "COMPLETE",
            "completed_shard_count": 11,
            "completed_fold_count": 2581,
            "canonical_score_sequence_digest": endpoint,
            "shards": shards,
            "evidence_created": False,
        },
    )
    adjusted = min(1.0, 3.0 * raw_p)
    interval = {
        "lower": lower,
        "upper": upper,
        "simultaneous_confidence_level": 0.95,
        "per_branch_total_alpha": 0.05 / 3,
        "quantile_method": "Hyndman-Fan type 7",
    }
    inference = _artifact(
        domain="dehps.m4.v2.marginal-static-historical-inference-aggregate.v1",
        artifact_type="m4_v2_marginal_static_historical_inference_aggregate",
        body={
            "status": "COMPLETE",
            "dataset_content_digest": "a" * 64,
            "score_sequence_digest": endpoint,
            "formal_historical_folds_executed": 2581,
            "bootstrap_children_executed": 16000,
            "complete_run": True,
            "partial_run_evidence": "forbidden",
            "evidence_created": False,
            "primary_raw_p_value": raw_p,
            "fixed_family_raw_p_values": {
                "MARGINAL_STATIC": raw_p,
                "TEMPORAL_MARGINAL_INCREMENT": 1.0,
                "JOINT_RESIDUAL_INCREMENT": 1.0,
            },
            "fixed_family_holm_adjusted_p_values": {
                "MARGINAL_STATIC": adjusted,
                "TEMPORAL_MARGINAL_INCREMENT": 1.0,
                "JOINT_RESIDUAL_INCREMENT": 1.0,
            },
            "holm_adjusted_p_value": adjusted,
            "simultaneous_effect_interval_bits_per_issue": interval,
            "equivalence_upper_bound_bits_per_issue": equivalence_upper,
            "mde_bits_per_issue": mde,
            "equivalence_power_sufficient": power_sufficient,
            "half_means_bits_per_issue": half_means,
            "third_means_bits_per_issue": [0.01, 0.02, 0.03],
        },
    )
    candidate = _artifact(
        domain="dehps.m4.v2.marginal-static-historical-branch-candidate.v1",
        artifact_type="m4_v2_marginal_static_historical_branch_candidate",
        body={
            "status": "READY_FOR_GATE_COMPILER_AFTER_REPLAY",
            "branch_id": "MARGINAL_STATIC",
            "gate_compiler_contract_digest": GATE_COMPILER_CONTRACT_DIGEST,
            "inference_aggregate_digest": inference["artifact_digest"],
            "endpoint_digest": endpoint,
            "candidate_estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "baseline_id": "LEGAL_UNIFORM_NUMBER_EVENT_BASELINE",
            "candidate_baseline_distinct": True,
            "measurement_health": "PASS",
            "historical_run_status": "COMPLETE",
            "primary_p_value": raw_p,
            "holm_adjusted_p_value": adjusted,
            "effect_interval_bits_per_issue": interval,
            "equivalence_upper_bound_bits_per_issue": equivalence_upper,
            "mde_bits_per_issue": mde,
            "equivalence_power_sufficient": power_sufficient,
            "half_means_bits_per_issue": half_means,
            "third_means_bits_per_issue": [0.01, 0.02, 0.03],
            "decision": None,
            "decision_compiled": False,
            "evidence_created": False,
            "accepted_model_artifact_digest": None,
            "promotion_gate_opened": False,
        },
    )
    completion = _artifact(
        domain="dehps.m4.v2.marginal-static-historical-execution-completion.v1",
        artifact_type="m4_v2_marginal_static_historical_execution_completion",
        body={
            "status": "COMPLETE",
            "execution_id": HISTORICAL_EXECUTION_ID,
            "completion_index_digest": completion_index["artifact_digest"],
            "inference_aggregate_digest": inference["artifact_digest"],
            "branch_candidate_digest": candidate["artifact_digest"],
            "completion_fact": HISTORICAL_EXECUTION_COMPLETION_FACT,
            "evidence_created": False,
        },
    )
    execution = _artifact(
        domain="dehps.research-os.mainline-execution.v1",
        artifact_type="research_os_mainline_execution",
        body={
            "task_key": HISTORICAL_EXECUTION_TASK_KEY,
            "execution_id": HISTORICAL_EXECUTION_ID,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "completion_fact": HISTORICAL_EXECUTION_COMPLETION_FACT,
            "historical_completion_index_digest": completion_index["artifact_digest"],
            "historical_inference_aggregate_digest": inference["artifact_digest"],
            "historical_branch_candidate_digest": candidate["artifact_digest"],
            "historical_execution_completion_digest": completion["artifact_digest"],
            "formal_historical_folds_executed": 2581,
            "bootstrap_children_executed": 16000,
            "duplicate_validation": False,
            "evidence_created": False,
            "production_action": "none",
        },
    )
    return {
        "historical_execution": execution,
        "completion_index": completion_index,
        "inference_aggregate": inference,
        "branch_candidate": candidate,
        "historical_execution_completion": completion,
    }


def _gate_contract() -> dict:
    measurement = json.loads(
        (ROOT_DIR / "configs/research-os/m4-measurement-contract-v2.json").read_text()
    )
    return {
        "artifact_type": "measurement_v2_gate_compiler_contract",
        "artifact_digest": GATE_COMPILER_CONTRACT_DIGEST,
        "gate_compiler_contract": measurement["gate_compiler_contract"],
    }


def _run(**kwargs):
    source = load_marginal_static_historical_gate_source_contract(
        ROOT_DIR / MARGINAL_STATIC_HISTORICAL_GATE_SOURCE_CONTRACT_PATH
    )
    return build_marginal_static_historical_gate_artifacts(
        source_contract=source,
        gate_compiler_contract=_gate_contract(),
        require_registered_identities=False,
        **_parents(**kwargs),
    )


def test_source_contract_is_content_addressed() -> None:
    source = load_marginal_static_historical_gate_source_contract(
        ROOT_DIR / MARGINAL_STATIC_HISTORICAL_GATE_SOURCE_CONTRACT_PATH
    )
    verify_marginal_static_historical_gate_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )


@pytest.mark.parametrize(
    ("kwargs", "expected", "eligible"),
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
            "POSITIVE",
            True,
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
            "NEGATIVE",
            False,
        ),
        (
            {
                "raw_p": 0.001,
                "lower": 0.02,
                "upper": 0.04,
                "equivalence_upper": 0.03,
                "mde": 0.005,
                "power_sufficient": True,
                "half_means": [0.02, -0.001],
            },
            "INCONCLUSIVE",
            False,
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
            "INCONCLUSIVE",
            False,
        ),
    ],
)
def test_fixed_gate_routes_without_direct_promotion(
    kwargs: dict, expected: str, eligible: bool
) -> None:
    run = _run(**kwargs)
    assert run.historical_evidence == expected
    assert run.eligibility["eligible_for_prediction_v2_promotion_planning"] is eligible
    assert run.candidate_model["accepted_for_downstream_baseline"] is eligible
    assert run.gate_output["branch_outputs"][0]["accepted_model_artifact_digest"] == (
        run.candidate_model["artifact_digest"] if eligible else None
    )
    assert run.gate_output["promotion_gate_opened"] is False
    assert run.completion["completion_fact"] == (
        MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT
    )
    assert len(run.artifacts) == 6


def test_gate_rejects_tampered_holm_identity() -> None:
    parents = _parents(
        raw_p=0.001,
        lower=0.02,
        upper=0.04,
        equivalence_upper=0.03,
        mde=0.005,
        power_sufficient=True,
        half_means=[0.02, 0.03],
    )
    tampered = copy.deepcopy(parents["inference_aggregate"])
    tampered["holm_adjusted_p_value"] = 0.001
    identity = dict(tampered)
    identity.pop("artifact_digest")
    tampered["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.v2.marginal-static-historical-inference-aggregate.v1",
    )
    parents["inference_aggregate"] = tampered
    source = load_marginal_static_historical_gate_source_contract(
        ROOT_DIR / MARGINAL_STATIC_HISTORICAL_GATE_SOURCE_CONTRACT_PATH
    )
    with pytest.raises(
        MarginalStaticHistoricalGateError,
        match="holm_identity_changed|parent_lineage_invalid",
    ):
        build_marginal_static_historical_gate_artifacts(
            source_contract=source,
            gate_compiler_contract=_gate_contract(),
            require_registered_identities=False,
            **parents,
        )


def test_additive_migration_revises_gate_and_adds_planner() -> None:
    source_payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source_payload.pop("manifest_digest")
    source = ControlPlaneManifest.from_dict(source_payload).to_dict(
        include_digest=False
    )
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY
    ]
    live_gate = next(
        item
        for item in live["tasks"]
        if item["task_key"] == MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY
    )
    live_gate["requested_capability"] = None
    live_gate["input_artifact_digests"] = []
    live_gate["metric_contract"]["engineering_complete"] = False
    live_gate["metric_contract"]["engineering_increment_percent"] = 0
    live_gate["metric_contract"]["evidence_complete"] = False
    live_gate["metric_contract"]["evidence_increment_percent"] = 0
    live_gate["metric_contract"]["evidence_created"] = False
    source_contract = load_marginal_static_historical_gate_source_contract(
        ROOT_DIR / MARGINAL_STATIC_HISTORICAL_GATE_SOURCE_CONTRACT_PATH
    )
    source_fact = (
        "m4-v2-marginal-static-historical-gate-source:"
        f"{source_contract['artifact_digest']}"
    )
    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,),
        allowlisted_revised_task_keys=(MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY]
    assert dry_run["revised_task_keys"] == [MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_status_projects_completed_gate_to_promotion_planner() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY
    )
    for item in payload["tasks"]:
        if item["task_key"] == MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT,
            "m4-v2-marginal-static-historical-evidence:POSITIVE",
            mainline_completion_fact(task=task, execution_id="f" * 64),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
            "marginal_static_historical_gate_source_contract_digest": "1" * 64,
            "hierarchical_gate_output_digest": "2" * 64,
            "historical_evidence_artifact_digest": "3" * 64,
            "promotion_planning_eligibility_digest": "4" * 64,
            "historical_evidence": "POSITIVE",
            "evidence_fact": ("m4-v2-marginal-static-historical-evidence:POSITIVE"),
            "evidence_created": True,
            "prediction_v2_planning_eligible": True,
            "registered_artifact_count": 7,
            "database_queries_during_capability": 0,
            "promotion_gate_opened": False,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "PREDICTION_V2_PROMOTION_PLANNER"
    assert projection["next_consumer"] == PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY
    assert projection["live_mainline_status"] == (
        "MARGINAL_STATIC_HISTORICAL_GATE_VALIDATED_IN_MAINLINE"
    )
    gate = projection["marginal_static_historical_measurement_gate_compiler"]
    assert gate["completed"] is True
    assert gate["historical_evidence"] == "POSITIVE"
    assert gate["prediction_v2_planning_eligible"] is True
    assert gate["registered_artifact_count"] == 7
    planner = projection["prediction_v2_promotion_planner"]
    assert planner["resolver_status"] == "ready"
    assert planner["gate_evidence_ready"] is True
    assert planner["planning_eligible"] is True


def test_supervisor_executes_and_replays_gate_without_recomputing_history(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_contract = load_marginal_static_historical_gate_source_contract(
        ROOT_DIR / MARGINAL_STATIC_HISTORICAL_GATE_SOURCE_CONTRACT_PATH
    )
    for entry in source_contract["source_entries"]:
        relative = entry["path"]
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / relative, destination)
    target_contract = tmp_path / MARGINAL_STATIC_HISTORICAL_GATE_SOURCE_CONTRACT_PATH
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT_DIR / MARGINAL_STATIC_HISTORICAL_GATE_SOURCE_CONTRACT_PATH,
        target_contract,
    )
    parents = _parents(
        raw_p=0.001,
        lower=0.02,
        upper=0.04,
        equivalence_upper=0.03,
        mde=0.005,
        power_sufficient=True,
        half_means=[0.02, 0.03],
    )
    gate_contract = _gate_contract()
    artifact_by_type = {
        "m4_v2_marginal_static_historical_completion_index": parents[
            "completion_index"
        ],
        "m4_v2_marginal_static_historical_inference_aggregate": parents[
            "inference_aggregate"
        ],
        "m4_v2_marginal_static_historical_branch_candidate": parents[
            "branch_candidate"
        ],
        "m4_v2_marginal_static_historical_execution_completion": parents[
            "historical_execution_completion"
        ],
        "measurement_v2_gate_compiler_contract": gate_contract,
    }

    loaded_task_keys: list[str] = []

    def fake_completed_execution(*, task_key: str, **_: object):
        loaded_task_keys.append(task_key)
        if task_key == HISTORICAL_EXECUTION_TASK_KEY:
            return ({}, parents["historical_execution"], [])
        return ({}, {}, [])

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        fake_completed_execution,
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda *, artifact_type, **_: artifact_by_type[artifact_type],
    )
    original_build = build_marginal_static_historical_gate_artifacts
    monkeypatch.setattr(
        supervisor_module,
        "build_marginal_static_historical_gate_artifacts",
        lambda **kwargs: original_build(
            **kwargs,
            require_registered_identities=False,
        ),
    )
    task = next(
        item
        for item in load_m4_manifest(MANIFEST_PATH).tasks
        if item.task_key == MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY
    )
    expected_inputs = (
        source_contract["artifact_digest"],
        gate_contract["artifact_digest"],
        parents["historical_execution"]["artifact_digest"],
        parents["completion_index"]["artifact_digest"],
        parents["inference_aggregate"]["artifact_digest"],
        parents["branch_candidate"]["artifact_digest"],
        parents["historical_execution_completion"]["artifact_digest"],
    )
    task = replace(task, input_artifact_digests=expected_inputs)
    result = M4MarginalStaticHistoricalGateCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="b" * 64,
        git_commit="c" * 40,
    )
    assert len(result.registrations) == 7
    assert result.execution_artifact["actual_fold_count"] == 0
    assert result.execution_artifact["formal_historical_folds_executed"] == 0
    assert result.execution_artifact["bootstrap_children_executed"] == 0
    assert result.execution_artifact["database_queries_during_capability"] == 0
    assert result.execution_artifact["historical_evidence"] == "POSITIVE"
    assert (
        result.execution_artifact["evaluated_model_artifact_digest"]
        == (result.execution_artifact["accepted_model_artifact_digest"])
    )
    assert result.execution_artifact["duplicate_validation"] is False
    assert loaded_task_keys.count("m4-v2-measurement-contract-design") == 1
    assert "m4-v2-marginal-static-historical-measurement-design" not in (
        loaded_task_keys
    )
    assert result.completion_facts == (
        MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT,
        "m4-v2-marginal-static-historical-evidence:POSITIVE",
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
                        ["registered_artifact_count", 7],
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
        task_key=MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
        execution_id="b" * 64,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["historical_evidence"] == "POSITIVE"
    assert capability_replay["database_queries_during_replay"] == 0
    assert capability_replay["formal_historical_folds_replayed"] == 0
    assert capability_replay["bootstrap_children_replayed"] == 0
    assert capability_replay["duplicate_validation"] is False
    assert loaded_task_keys.count("m4-v2-measurement-contract-design") == 2
