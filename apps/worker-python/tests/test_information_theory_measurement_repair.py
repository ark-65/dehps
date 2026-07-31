from __future__ import annotations

import json
from functools import cache
from pathlib import Path

import pytest
from dehps.research_os.information_theory.measurement_validation import (
    PASS_FACT,
    REPAIR_FACT,
    build_cells,
    build_mde_summary,
    build_replicate,
    evaluate_automatic_gate,
)
from dehps.research_os.information_theory.measurement_validation.repaired_contracts import (
    REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
    load_repaired_measurement_validation_manifest,
)
from dehps.research_os.information_theory.repair import (
    MEASUREMENT_REPAIR_MANIFEST_DIGEST,
    MeasurementRepairError,
    calibrate_marginal_target,
    load_measurement_repair_manifest,
    validate_measurement_repair_manifest,
)
from dehps.research_os.information_theory.repair.execution import (
    REPAIRED_FACT,
    run_measurement_contract_repair,
)
from dehps.research_os.information_theory.synthetic import (
    load_synthetic_run_manifest,
)

ROOT = Path(__file__).resolve().parents[3]
REPAIR_MANIFEST = (
    ROOT
    / "configs/research-os/"
    "m4-information-theory-p2-6-1-measurement-contract-repair-v1.json"
)
P261_MANIFEST = (
    ROOT
    / "configs/research-os/"
    "m4-information-theory-p2-6-1-measurement-validation-v1.json"
)
SYNTHETIC_MANIFEST = (
    ROOT
    / "configs/research-os/"
    "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
)


@cache
def _run():
    return run_measurement_contract_repair(
        root_dir=ROOT,
        execution_id="a" * 64,
        git_commit="b" * 40,
    )


def test_scheme_a_exact_truths_have_complete_typed_dispositions() -> None:
    manifest = load_measurement_repair_manifest(REPAIR_MANIFEST)
    assert manifest.artifact_digest == MEASUREMENT_REPAIR_MANIFEST_DIGEST
    roles = [item["role"] for item in manifest.scenarios]
    assert roles.count("FORMAL_POWER_TARGET") == 8
    assert roles.count("JOINT_ONLY_NEGATIVE_CONTROL") == 3
    assert roles.count("MARGINAL_FEASIBILITY_SENTINEL") == 1
    preserving = [
        item
        for item in manifest.scenarios
        if item["role"] == "JOINT_ONLY_NEGATIVE_CONTROL"
    ]
    assert all(
        item["marginal_information_bits_per_issue"] == 0
        and item["joint_information_bits_per_issue"] > 0
        for item in preserving
    )


def test_strong_pair_marginal_target_is_proved_unreachable() -> None:
    result = calibrate_marginal_target(
        "pair_conditional_signal",
        0.05,
    )
    assert result.classification == (
        "TARGET_NOT_REACHABLE_BY_FROZEN_GENERATOR"
    )
    assert result.marginal_information_bits_per_issue == pytest.approx(
        0.011422379570594537,
        abs=1e-15,
    )
    assert result.marginal_information_bits_per_issue < 0.05


def test_repair_manifest_mutation_fails_closed() -> None:
    payload = json.loads(REPAIR_MANIFEST.read_text(encoding="utf-8"))
    payload["scenario_contracts"][0]["parameter_value"] += 0.001
    with pytest.raises(
        MeasurementRepairError,
        match="measurement_repair_manifest_digest_mismatch",
    ):
        validate_measurement_repair_manifest(payload)


def test_development_selection_replays_without_formal_outcome_or_seed_reuse() -> (
    None
):
    selection = _run().development_selection
    assert selection["artifact_digest"] == (
        "90459ebf8b88afcc60ee1177043e436b90b71c00b557f15e9e4d7026f37586f2"
    )
    assert selection["selected_config_ids"] == {
        "REGULARIZED_LOGISTIC_REGRESSION": "C=0.1",
        "NAIVE_BAYES": "alpha=2",
        "SHALLOW_CALIBRATED_TREE": (
            "max_depth=2,min_samples_leaf=50"
        ),
    }
    assert selection["candidate_fit_count"] == 126
    assert selection["formal_outer_metrics_used"] is False
    assert selection["formal_evaluation_seed_reuse"] is False
    assert selection["eligible_for_evidence"] is False


def test_repaired_manifest_binds_marginal_truths_and_preserves_long_lane() -> (
    None
):
    manifest = load_repaired_measurement_validation_manifest(P261_MANIFEST)
    assert (
        manifest.artifact_digest
        == REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST
    )
    assert manifest.scenario_replicates == 31_000
    assert manifest.outer_issue_predictions == 64_656_000
    cells = build_cells(
        manifest,
        load_synthetic_run_manifest(SYNTHETIC_MANIFEST),
    )
    assert len(cells) == 31
    assert sum(item.formal_power_eligible is True for item in cells) == 19
    sentinel = next(
        item
        for item in cells
        if item.scale_id == "FORWARD_61"
        and item.scenario_id == "STRONG_PAIR"
    )
    assert sentinel.scenario_role == "MARGINAL_FEASIBILITY_SENTINEL"
    assert sentinel.formal_power_eligible is False
    assert sentinel.target_bits_per_issue == pytest.approx(
        0.011422379570594537
    )


def test_repair_completion_is_result_blind_and_emits_only_availability_fact() -> (
    None
):
    run = _run()
    assert run.identifiability_confirmation["decision"] == (
        "MEASUREMENT_CONTRACT_REPAIRED"
    )
    assert run.completion["completion_fact"] == REPAIRED_FACT
    assert run.completion["old_partial_statistical_results_inspected"] is False
    assert run.completion["actual_fold_count"] == 0
    assert run.completion["evidence_created"] is False
    assert run.completion["outer_fold_fit_count_before"] == 46
    assert run.completion["outer_fold_fit_count_after"] == 4


def _repaired_aggregate(cell) -> dict:
    null = cell.scenario_id == "NULL_UNIFORM"
    formal = cell.formal_power_eligible is True
    joint_only = cell.scenario_role == "JOINT_ONLY_NEGATIVE_CONTROL"
    return {
        "artifact_digest": build_replicate(
            cell=cell,
            replicate_index=0,
            parent_execution_id="c" * 64,
        ).artifact_digest,
        **cell.to_dict(),
        "false_positive_rate": 0.04 if null else None,
        "joint_only_control_false_positive_rate": (
            0.04 if joint_only else None
        ),
        "empirical_power": 0.96 if formal else None,
        "false_positive_point_gate_pass": True if null else None,
        "false_positive_wilson_gate_pass": True if null else None,
        "joint_only_control_point_gate_pass": (
            True if joint_only else None
        ),
        "joint_only_control_wilson_gate_pass": (
            True if joint_only else None
        ),
        "practical_power_gate_pass": (
            True
            if formal and cell.signal_strength == "MEDIUM_PRACTICAL"
            else None
        ),
        "strong_power_gate_pass": (
            True if formal and cell.signal_strength == "STRONG" else None
        ),
        "bias_gate_pass": True,
        "coverage_gate_pass": True,
        "rmse_finite_gate_pass": True,
        "PE2_coverage_rate": 0.95,
    }


def _formal_completion() -> dict:
    return {
        "artifact_digest": "f" * 64,
        "replicate_count": 31_000,
        "duplicate_replicate_count": 0,
        "failed_replicate_count": 0,
        "negative_control_id": "NC6_SYNTHETIC_NULL",
        "negative_control_cell_count": 3,
        "negative_control_replicates_per_cell": 1000,
        "negative_control_replicate_count": 3000,
        "checkpoint_journal_count": 31_000,
        "checkpoint_journal_failure_count": 0,
        "bootstrap_seed_count": 31_000 * 2000,
        "permutation_seed_count": 31_000 * 2000,
        "incomplete_seed_set_count": 0,
        "leakage_failure_count": 0,
    }


def test_repaired_gate_separates_power_controls_and_feasibility_sentinel() -> (
    None
):
    manifest = load_repaired_measurement_validation_manifest(P261_MANIFEST)
    cells = build_cells(
        manifest,
        load_synthetic_run_manifest(SYNTHETIC_MANIFEST),
    )
    aggregates = [_repaired_aggregate(cell) for cell in cells]

    mde = build_mde_summary(aggregates)
    assert {
        item["mechanism"] for item in mde["per_mechanism_scale"]
    } == {"SINGLE_NUMBER", "LOCAL_TEMPORAL", "PAIR"}
    assert len(mde["per_mechanism_scale"]) == 9

    passed = evaluate_automatic_gate(
        manifest=manifest,
        completion=_formal_completion(),
        aggregates=aggregates,
        deterministic_replay_passed=True,
    )
    assert passed["decision"] == "PASS_TO_P3"
    assert passed["decision_fact"] == PASS_FACT
    assert (
        passed["requirements"][
            "all_joint_only_marginal_controls_false_positive_gates_pass"
        ]
        is True
    )

    joint_only = next(
        item
        for item in aggregates
        if item.get("scenario_role") == "JOINT_ONLY_NEGATIVE_CONTROL"
    )
    joint_only["joint_only_control_point_gate_pass"] = False
    failed = evaluate_automatic_gate(
        manifest=manifest,
        completion=_formal_completion(),
        aggregates=aggregates,
        deterministic_replay_passed=True,
    )
    assert failed["decision"] == "REPAIR_MEASUREMENT_SYSTEM"
    assert failed["decision_fact"] == REPAIR_FACT
