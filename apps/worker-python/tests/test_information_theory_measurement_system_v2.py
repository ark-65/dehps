from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.measurement_system_v2 import (
    COMPATIBILITY_COMPLETION_FACT,
    MEASUREMENT_CONTRACT_V2_DIGEST,
    MeasurementContractV2Error,
    build_design_artifacts,
    compile_hierarchical_gate,
    load_measurement_contract_v2,
    validate_measurement_contract_v2,
)
from dehps.research_os.information_theory.measurement_system_v2.contracts import (
    BRANCH_IDS,
)
from dehps.research_os.information_theory.progress import build_m4_status
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest, TaskStatus
from dehps.research_os.supervisor import (
    M4_P263_COMPATIBILITY_CAPABILITY,
    M4_P263_COMPATIBILITY_TASK_KEY,
    M4_V2_DESIGN_CAPABILITY,
    M4_V2_DESIGN_TASK_KEY,
    M4MeasurementContractV2DesignCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = ROOT / "configs/research-os/m4-measurement-contract-v2.json"
CONTROL_PLANE_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"


@pytest.fixture(scope="module")
def contract():
    return load_measurement_contract_v2(CONTRACT_PATH)


def test_v2_contract_freezes_two_axes_three_incremental_estimands_and_lineage(
    contract,
) -> None:
    assert contract.artifact_digest == MEASUREMENT_CONTRACT_V2_DIGEST
    assert tuple(item["branch_id"] for item in contract.branches) == BRANCH_IDS
    assert [item["target_geometry"] for item in contract.branches] == [
        "NUMBER_EVENT_MARGINAL",
        "NUMBER_EVENT_MARGINAL",
        "LEGAL_FIXED_CARDINALITY_JOINT",
    ]
    assert [item["conditioning_set"] for item in contract.branches] == [
        "STATIONARY_NO_HISTORY",
        "STRICT_PRIOR_HISTORY_H_LT",
        "STRICT_PRIOR_HISTORY_H_LT",
    ]
    temporal_baseline = contract.branches[1]["baseline"]
    joint_baseline = contract.branches[2]["baseline"]
    assert temporal_baseline["source_branch_id"] == BRANCH_IDS[0]
    assert temporal_baseline["fallback"] == "FORBIDDEN"
    assert joint_baseline["source_branch_id"] == BRANCH_IDS[1]
    assert joint_baseline["independent_bernoulli_product"] == "FORBIDDEN"
    assert joint_baseline["uniform_fallback"] == "FORBIDDEN"
    assert (
        contract.payload["p2_6_1_lineage_boundary"]["semantic_purpose"]
        == "MARGINAL_OUTPUT_MEASUREMENT_ACCEPTANCE_BASELINE"
    )
    assert (
        contract.payload["p2_6_1_lineage_boundary"][
            "v2_historical_branch_evidence_credit"
        ]
        == "NONE"
    )


def test_v2_contract_mutation_fails_even_with_recomputed_self_digest(
    contract,
) -> None:
    payload = copy.deepcopy(dict(contract.payload))
    payload["gate_compiler_contract"]["practical_threshold_bits_per_issue"] = 0.02
    payload["artifact_digest"] = config_digest(payload)
    with pytest.raises(MeasurementContractV2Error) as caught:
        validate_measurement_contract_v2(payload)
    assert caught.value.code == "measurement_v2_digest_mismatch"


def test_role_matrix_is_estimand_relative_complete_and_result_ineligible(
    contract,
) -> None:
    rows = {row["mechanism_id"]: row for row in contract.mechanism_rows}
    assert len(rows) == 8
    for row in rows.values():
        assert tuple(row["roles"]) == BRANCH_IDS
        assert all(
            cell["historical_evidence_eligible"] is False
            and cell["decision_credit"] is False
            for cell in row["roles"].values()
        )
    assert [
        rows["IS4_MARGINAL_PRESERVING_CONDITIONAL"]["roles"][branch]["role"]
        for branch in BRANCH_IDS
    ] == ["NEGATIVE_CONTROL", "NEGATIVE_CONTROL", "POSITIVE_CONTROL"]
    assert (
        rows["IS3_PAIR_CONDITIONAL"]["roles"]["TEMPORAL_MARGINAL_INCREMENT"]["role"]
        == "LEAKAGE_SENTINEL"
    )
    assert (
        rows["IS3_PAIR_CONDITIONAL"]["roles"]["JOINT_RESIDUAL_INCREMENT"]["role"]
        == "UNRESOLVED_PENDING_PREFLIGHT"
    )


def test_design_artifacts_are_deterministic_and_create_no_evidence(
    contract,
) -> None:
    first = build_design_artifacts(
        contract,
        execution_id="1" * 64,
        git_commit="2" * 40,
    )
    second = build_design_artifacts(
        contract,
        execution_id="1" * 64,
        git_commit="2" * 40,
    )
    assert first == second
    assert len({item["artifact_digest"] for item in first.artifacts}) == 4
    assert first.completion["actual_fold_count"] == 0
    assert first.completion["formal_branch_runs_executed"] == 0
    assert first.completion["historical_outcomes_read"] is False
    assert first.completion["p2_6_1_partial_statistical_results_read"] is False
    assert first.completion["evidence_created"] is False


def _branch_report(
    contract,
    branch_id: str,
    *,
    accepted_digest: str | None,
    baseline_digest: str | None,
    baseline_source_digest: str | None = None,
    accepted_for_downstream_baseline: bool = True,
    preflight_status: str = "PASS",
    preflight_digest: str | None = "e" * 64,
    endpoint_digest: str | None = None,
    measurement_run_status: str = "COMPLETE",
    historical_run_status: str = "NOT_RUN",
    failed_check: str | None = None,
    not_evaluated_check: str | None = None,
    primary_p_value: float | None = None,
    lower: float | None = None,
    upper: float | None = None,
    mde: float | None = None,
    equivalence_power_sufficient: bool | None = None,
    equivalence_upper: float | None = None,
) -> dict:
    gate = contract.payload["gate_compiler_contract"]
    checks = {
        key: "PASS"
        for key in (
            *gate["validity_checks"],
            *gate["measurement_acceptance_checks"],
        )
    }
    if failed_check is not None:
        checks[failed_check] = "FAIL"
    if not_evaluated_check is not None:
        checks[not_evaluated_check] = "NOT_EVALUATED"
    resolved_equivalence_upper = (
        upper
        if equivalence_power_sufficient is True and equivalence_upper is None
        else equivalence_upper
    )
    return {
        "branch_id": branch_id,
        "estimand_digest": contract.estimand_digest(branch_id),
        "measurement_run_status": measurement_run_status,
        "measurement_checks": checks,
        "historical_run_status": historical_run_status,
        "identifiability_preflight_status": preflight_status,
        "identifiability_preflight_artifact_digest": preflight_digest,
        "primary_p_value": primary_p_value,
        "statistical_input_contract_digest": (contract.statistical_input_digest()),
        "effect_interval_bits_per_issue": (
            None
            if lower is None or upper is None
            else {
                "lower": lower,
                "upper": upper,
                "simultaneous_confidence_level": 0.95,
            }
        ),
        "interval_provenance_artifact_digest": (
            None if lower is None or upper is None else "d" * 64
        ),
        "interval_source_endpoint_digest": (
            None if lower is None or upper is None else endpoint_digest
        ),
        "mde_bits_per_issue": mde,
        "mde_provenance_artifact_digest": (None if mde is None else "b" * 64),
        "equivalence_power_sufficient": equivalence_power_sufficient,
        "equivalence_power_artifact_digest": (
            None if equivalence_power_sufficient is None else "c" * 64
        ),
        "equivalence_upper_bound_bits_per_issue": (resolved_equivalence_upper),
        "equivalence_upper_bound_provenance_artifact_digest": (
            None if resolved_equivalence_upper is None else "8" * 64
        ),
        "equivalence_source_endpoint_digest": (
            None if resolved_equivalence_upper is None else endpoint_digest
        ),
        "endpoint_digest": endpoint_digest,
        "accepted_model_artifact_digest": accepted_digest,
        "accepted_for_downstream_baseline": (accepted_for_downstream_baseline),
        "baseline_artifact_digest": baseline_digest,
        "baseline_source_model_artifact_digest": baseline_source_digest,
    }


def _not_run_reports(contract) -> list[dict]:
    return [
        _branch_report(
            contract,
            BRANCH_IDS[0],
            accepted_digest="1" * 64,
            baseline_digest="0" * 64,
        ),
        _branch_report(
            contract,
            BRANCH_IDS[1],
            accepted_digest="2" * 64,
            baseline_digest="1" * 64,
            baseline_source_digest="1" * 64,
        ),
        _branch_report(
            contract,
            BRANCH_IDS[2],
            accepted_digest="3" * 64,
            baseline_digest="9" * 64,
            baseline_source_digest="2" * 64,
        ),
    ]


def test_gate_separates_candidate_evidence_from_damaged_branch(
    contract,
) -> None:
    reports = _not_run_reports(contract)
    reports[0] = _branch_report(
        contract,
        BRANCH_IDS[0],
        accepted_digest="1" * 64,
        baseline_digest="0" * 64,
        endpoint_digest="a" * 64,
        historical_run_status="COMPLETE",
        primary_p_value=0.001,
        lower=0.02,
        upper=0.04,
        mde=0.005,
        equivalence_power_sufficient=True,
    )
    reports[1] = _branch_report(
        contract,
        BRANCH_IDS[1],
        accepted_digest="2" * 64,
        baseline_digest="1" * 64,
        baseline_source_digest="1" * 64,
        failed_check="legal_sample_space",
    )
    output = compile_hierarchical_gate(contract, branch_reports=reports)
    assert output["global_evidence"] == "CANDIDATE_INFORMATION_FOUND"
    assert output["global_coverage"] == "PARTIAL"
    assert output["candidate_branches"] == [BRANCH_IDS[0]]
    assert output["repair_branches"] == [BRANCH_IDS[1]]


def test_gate_positive_does_not_require_mde(contract) -> None:
    reports = _not_run_reports(contract)
    reports[0] = _branch_report(
        contract,
        BRANCH_IDS[0],
        accepted_digest="1" * 64,
        baseline_digest="0" * 64,
        endpoint_digest="a" * 64,
        historical_run_status="COMPLETE",
        primary_p_value=0.001,
        lower=0.02,
        upper=0.04,
    )
    output = compile_hierarchical_gate(contract, branch_reports=reports)
    assert output["branch_outputs"][0]["historical_evidence"] == "POSITIVE"
    assert output["global_evidence"] == "CANDIDATE_INFORMATION_FOUND"


def test_gate_missing_primary_endpoint_cannot_create_positive(contract) -> None:
    reports = _not_run_reports(contract)
    reports[0] = _branch_report(
        contract,
        BRANCH_IDS[0],
        accepted_digest="1" * 64,
        baseline_digest="0" * 64,
        historical_run_status="COMPLETE",
        primary_p_value=0.001,
        lower=0.02,
        upper=0.04,
    )
    output = compile_hierarchical_gate(contract, branch_reports=reports)
    assert output["branch_outputs"][0]["historical_evidence"] == ("INCONCLUSIVE")
    assert output["branch_outputs"][0]["holm_adjusted_p_value"] == 1.0
    assert output["global_evidence"] == "INCONCLUSIVE"


def test_gate_missing_or_baseline_identical_candidate_cannot_create_evidence(
    contract,
) -> None:
    for accepted_digest in (None, "0" * 64):
        reports = _not_run_reports(contract)
        reports[0] = _branch_report(
            contract,
            BRANCH_IDS[0],
            accepted_digest=accepted_digest,
            baseline_digest="0" * 64,
            endpoint_digest="a" * 64,
            historical_run_status="COMPLETE",
            primary_p_value=0.001,
            lower=0.02,
            upper=0.04,
        )
        output = compile_hierarchical_gate(
            contract,
            branch_reports=reports,
        )
        assert output["branch_outputs"][0]["historical_evidence"] == ("INCONCLUSIVE")
        assert output["global_evidence"] == "INCONCLUSIVE"

    reports = _not_run_reports(contract)
    reports[0] = _branch_report(
        contract,
        BRANCH_IDS[0],
        accepted_digest="0" * 64,
        baseline_digest="0" * 64,
        endpoint_digest="a" * 64,
        historical_run_status="COMPLETE",
        primary_p_value=0.5,
        lower=-0.01,
        upper=0.02,
        mde=0.005,
        equivalence_power_sufficient=True,
        equivalence_upper=0.005,
    )
    identical_negative = compile_hierarchical_gate(
        contract,
        branch_reports=reports,
    )
    assert (
        identical_negative["branch_outputs"][0]["historical_evidence"] == "INCONCLUSIVE"
    )


def test_gate_missing_baseline_and_unresolved_preflight_are_not_run(
    contract,
) -> None:
    reports = _not_run_reports(contract)
    reports[1]["baseline_artifact_digest"] = None
    reports[1]["baseline_source_model_artifact_digest"] = None
    reports[1]["historical_run_status"] = "COMPLETE"
    missing = compile_hierarchical_gate(contract, branch_reports=reports)
    temporal = missing["branch_outputs"][1]
    assert temporal["measurement_health"] == "INCONCLUSIVE"
    assert temporal["historical_evidence"] == "NOT_RUN"
    assert temporal["baseline_dependency_reason"] == ("MISSING_BASELINE_ARTIFACT")

    reports = _not_run_reports(contract)
    reports[1]["identifiability_preflight_status"] = "UNRESOLVED"
    reports[1]["identifiability_preflight_artifact_digest"] = None
    reports[1]["historical_run_status"] = "COMPLETE"
    unresolved = compile_hierarchical_gate(
        contract,
        branch_reports=reports,
    )
    assert unresolved["branch_outputs"][1]["measurement_health"] == ("INCONCLUSIVE")
    assert unresolved["branch_outputs"][1]["historical_evidence"] == "NOT_RUN"


def test_gate_rejects_negative_mde(contract) -> None:
    reports = _not_run_reports(contract)
    reports[0]["mde_bits_per_issue"] = -0.001
    reports[0]["mde_provenance_artifact_digest"] = "b" * 64
    with pytest.raises(MeasurementContractV2Error) as caught:
        compile_hierarchical_gate(contract, branch_reports=reports)
    assert caught.value.code == "measurement_v2_gate_input_invalid"


def test_gate_rejects_contradictory_interval_and_equivalence_bound(
    contract,
) -> None:
    reports = _not_run_reports(contract)
    reports[0] = _branch_report(
        contract,
        BRANCH_IDS[0],
        accepted_digest="1" * 64,
        baseline_digest="0" * 64,
        endpoint_digest="a" * 64,
        historical_run_status="COMPLETE",
        primary_p_value=0.5,
        lower=0.02,
        upper=0.04,
        mde=0.005,
        equivalence_power_sufficient=True,
        equivalence_upper=0.005,
    )
    with pytest.raises(MeasurementContractV2Error) as caught:
        compile_hierarchical_gate(contract, branch_reports=reports)
    assert caught.value.code == "measurement_v2_gate_input_invalid"


def test_gate_requires_full_healthy_equivalent_family_for_negative(
    contract,
) -> None:
    reports = _not_run_reports(contract)
    for index, branch_id in enumerate(BRANCH_IDS):
        reports[index] = _branch_report(
            contract,
            branch_id,
            accepted_digest=str(index + 1) * 64,
            baseline_digest=(
                "0" * 64 if index == 0 else "1" * 64 if index == 1 else "9" * 64
            ),
            baseline_source_digest=(None if index == 0 else str(index) * 64),
            endpoint_digest="abcdef"[index] * 64,
            historical_run_status="COMPLETE",
            primary_p_value=0.5,
            lower=-0.01,
            upper=0.02,
            mde=0.005,
            equivalence_power_sufficient=True,
            equivalence_upper=0.005,
        )
    output = compile_hierarchical_gate(contract, branch_reports=reports)
    assert output["global_coverage"] == "FULL"
    assert output["global_evidence"] == "NO_DETECTABLE_INFORMATION"
    assert {item["historical_evidence"] for item in output["branch_outputs"]} == {
        "NEGATIVE"
    }

    reports[2]["equivalence_power_sufficient"] = False
    inconclusive = compile_hierarchical_gate(
        contract,
        branch_reports=reports,
    )
    assert inconclusive["global_coverage"] == "FULL"
    assert inconclusive["global_evidence"] == "INCONCLUSIVE"
    assert inconclusive["branch_outputs"][2]["historical_evidence"] == ("INCONCLUSIVE")

    reports[2]["equivalence_power_sufficient"] = True
    reports[2]["equivalence_upper_bound_bits_per_issue"] = None
    reports[2]["equivalence_upper_bound_provenance_artifact_digest"] = None
    missing_bound = compile_hierarchical_gate(
        contract,
        branch_reports=reports,
    )
    assert missing_bound["branch_outputs"][2]["historical_evidence"] == "INCONCLUSIVE"


def test_gate_holm_significant_primary_test_cannot_compile_negative(
    contract,
) -> None:
    reports = []
    for index, branch_id in enumerate(BRANCH_IDS):
        reports.append(
            _branch_report(
                contract,
                branch_id,
                accepted_digest=str(index + 1) * 64,
                baseline_digest=(
                    "0" * 64 if index == 0 else "1" * 64 if index == 1 else "9" * 64
                ),
                baseline_source_digest=(None if index == 0 else str(index) * 64),
                endpoint_digest="abcdef"[index] * 64,
                historical_run_status="COMPLETE",
                primary_p_value=0.000001,
                lower=-0.01,
                upper=0.02,
                mde=0.005,
                equivalence_power_sufficient=True,
                equivalence_upper=0.005,
            )
        )
    output = compile_hierarchical_gate(contract, branch_reports=reports)
    assert output["global_evidence"] == "INCONCLUSIVE"
    assert {item["historical_evidence"] for item in output["branch_outputs"]} == {
        "INCONCLUSIVE"
    }


def test_gate_rejects_duplicate_credit_and_marks_bad_baseline_not_run(
    contract,
) -> None:
    reports = _not_run_reports(contract)
    reports[0]["endpoint_digest"] = "a" * 64
    reports[1]["endpoint_digest"] = "a" * 64
    with pytest.raises(MeasurementContractV2Error) as duplicate:
        compile_hierarchical_gate(contract, branch_reports=reports)
    assert duplicate.value.code == "measurement_v2_duplicate_endpoint_credit"

    reports = _not_run_reports(contract)
    reports[2]["baseline_artifact_digest"] = "f" * 64
    reports[2]["baseline_source_model_artifact_digest"] = "f" * 64
    reports[2]["historical_run_status"] = "COMPLETE"
    baseline = compile_hierarchical_gate(contract, branch_reports=reports)
    joint = baseline["branch_outputs"][2]
    assert joint["measurement_health"] == "INCONCLUSIVE"
    assert joint["historical_evidence"] == "NOT_RUN"
    assert joint["historical_run_status"] == "NOT_RUN"
    assert joint["baseline_dependency_reason"] == ("BASELINE_SOURCE_MODEL_MISMATCH")

    reports = _not_run_reports(contract)
    reports[2]["baseline_artifact_digest"] = "2" * 64
    same_identity = compile_hierarchical_gate(
        contract,
        branch_reports=reports,
    )
    assert (
        same_identity["branch_outputs"][2]["baseline_dependency_reason"]
        == "DERIVED_JOINT_BASELINE_IDENTITY_REQUIRED"
    )


def test_gate_output_is_order_invariant(contract) -> None:
    reports = _not_run_reports(contract)
    direct = compile_hierarchical_gate(contract, branch_reports=reports)
    reversed_output = compile_hierarchical_gate(
        contract,
        branch_reports=list(reversed(reports)),
    )
    assert direct == reversed_output


def test_gate_output_digest_binds_full_consumed_branch_report(contract) -> None:
    reports = _not_run_reports(contract)
    reports[0] = _branch_report(
        contract,
        BRANCH_IDS[0],
        accepted_digest="1" * 64,
        baseline_digest="0" * 64,
        endpoint_digest="a" * 64,
        historical_run_status="COMPLETE",
        primary_p_value=0.001,
        lower=0.02,
        upper=0.04,
    )
    first = compile_hierarchical_gate(contract, branch_reports=reports)
    reports[0]["effect_interval_bits_per_issue"]["lower"] = 0.03
    second = compile_hierarchical_gate(contract, branch_reports=reports)
    assert first["global_evidence"] == second["global_evidence"]
    assert first["artifact_digest"] != second["artifact_digest"]
    assert first["branch_outputs"][0]["branch_report_digest"] != (
        second["branch_outputs"][0]["branch_report_digest"]
    )


def test_source_dag_supersedes_p2_6_1_compute_without_mutating_v2_lineage(
    contract,
) -> None:
    manifest = ControlPlaneManifest.from_dict(
        json.loads(CONTROL_PLANE_PATH.read_text(encoding="utf-8"))
    )
    tasks = {item.task_key: item for item in manifest.tasks}
    states = manifest.task_state_by_digest
    assert (
        tasks["m4-p2-false-positive-and-power-runs"].artifact_digest
        == "85a08402a4a0c37f75ee1675f4970ef00a7a0b0992b4204251c0c2cc79324de4"
    )
    assert (
        contract.payload["p2_6_1_lineage_boundary"]["task_digest"]
        == "80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa"
    )
    assert tasks[M4_V2_DESIGN_TASK_KEY].requested_capability == M4_V2_DESIGN_CAPABILITY
    assert (
        states[
            tasks[M4_V2_DESIGN_TASK_KEY].artifact_digest
        ].completion_classification.value
        == "INTEGRATION_PENDING"
    )
    snapshot = ResearchOSControlPlane().resolve(manifest)
    resolutions = {item.task_key: item for item in snapshot.resolutions}
    assert resolutions[M4_V2_DESIGN_TASK_KEY].status is TaskStatus.EXTERNAL_WAIT
    assert (
        resolutions[M4_P263_COMPATIBILITY_TASK_KEY].status
        is TaskStatus.DEPENDENCY_WAIT
    )
    assert (
        resolutions["m4-v2-branch-identifiability-preflight-design"].status
        is TaskStatus.DEPENDENCY_WAIT
    )
    status = build_m4_status(manifest, snapshot=snapshot)
    assert status["measurement_system_v2"] == {
        **status["measurement_system_v2"],
        "contract_digest": contract.artifact_digest,
        "resolver_status": "external_wait",
        "live_mainline_status": "INTEGRATION_PENDING",
        "p2_6_1_identity_changed": False,
        "p2_6_1_runtime_operation": "none",
        "formal_temporal_or_joint_execution": "NOT_AUTHORIZED",
        "evidence_progress_increment": 0,
    }
    assert status["measurement_system_v2"]["compatibility"] == {
        "task_key": M4_P263_COMPATIBILITY_TASK_KEY,
        "resolver_status": "dependency_wait",
        "verified": False,
        "p2_6_1_role": "FROZEN_HISTORICAL_BASELINE",
        "p2_6_3_role": "SUPERSEDING_MEASUREMENT_IMPLEMENTATION",
        "same_task_identity": False,
        "result_blind": True,
        "evidence_progress_increment": 0,
    }
    assert (
        M4_V2_DESIGN_CAPABILITY
        in ResearchEvidenceSupervisor(require_clean_tree=False).capabilities
    )
    assert (
        M4_P263_COMPATIBILITY_CAPABILITY
        in ResearchEvidenceSupervisor(require_clean_tree=False).capabilities
    )


def test_v2_task_becomes_ready_only_after_compatibility_and_runtime_release() -> None:
    payload = json.loads(CONTROL_PLANE_PATH.read_text(encoding="utf-8"))
    payload.pop("manifest_digest")
    initial = ControlPlaneManifest.from_dict(payload)
    tasks = {item.task_key: item for item in initial.tasks}
    prerequisite_keys = {
        "m4-p2-false-positive-and-power-runs",
        "m4-p2-automatic-gate-and-report",
    }
    for task in payload["tasks"]:
        if task["task_key"] in prerequisite_keys:
            task["status"] = "completed"
            task["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        mainline_completion_fact(
            task=tasks[task_key],
            execution_id=str(index) * 64,
        )
        for index, task_key in enumerate(sorted(prerequisite_keys), start=4)
    )
    payload["facts"]["external_events"].append("m4-runtime-slot:p2-6-1-released")
    prerequisites_complete = ControlPlaneManifest.from_dict(payload)
    snapshot = ResearchOSControlPlane().resolve(prerequisites_complete)
    resolutions = {item.task_key: item.status for item in snapshot.resolutions}
    assert resolutions[M4_P263_COMPATIBILITY_TASK_KEY] is TaskStatus.READY
    assert resolutions[M4_V2_DESIGN_TASK_KEY] is TaskStatus.DEPENDENCY_WAIT

    compatibility_task = next(
        item
        for item in prerequisites_complete.tasks
        if item.task_key == M4_P263_COMPATIBILITY_TASK_KEY
    )
    for task in payload["tasks"]:
        if task["task_key"] == M4_P263_COMPATIBILITY_TASK_KEY:
            task["status"] = "completed"
            task["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            mainline_completion_fact(
                task=compatibility_task,
                execution_id="6" * 64,
            ),
            COMPATIBILITY_COMPLETION_FACT,
        )
    )
    compatible = ControlPlaneManifest.from_dict(payload)
    snapshot = ResearchOSControlPlane().resolve(compatible)
    resolutions = {item.task_key: item.status for item in snapshot.resolutions}
    assert resolutions[M4_V2_DESIGN_TASK_KEY] is TaskStatus.READY


def test_source_capability_materializes_only_four_design_artifacts(
    tmp_path: Path,
) -> None:
    manifest = ControlPlaneManifest.from_dict(
        json.loads(CONTROL_PLANE_PATH.read_text(encoding="utf-8"))
    )
    task = next(
        item for item in manifest.tasks if item.task_key == M4_V2_DESIGN_TASK_KEY
    )
    target = tmp_path / "configs/research-os"
    target.mkdir(parents=True)
    shutil.copy2(CONTRACT_PATH, target / CONTRACT_PATH.name)
    result = M4MeasurementContractV2DesignCapability(root_dir=tmp_path).execute(
        control_plane_key="test-m4-v2",
        task=task,
        execution_id="5" * 64,
        git_commit="6" * 40,
    )
    assert result.execution_artifact["actual_fold_count"] == 0
    assert result.execution_artifact["formal_branch_runs_executed"] == 0
    assert result.execution_artifact["historical_outcomes_read"] is False
    assert len(result.registrations) == 5
    assert result.completion_facts == ("m4-measurement-contract-v2-design:FROZEN",)
