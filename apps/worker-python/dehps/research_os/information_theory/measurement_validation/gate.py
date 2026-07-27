from __future__ import annotations

from math import fsum, isfinite, sqrt
from typing import Any, Mapping, Sequence

from dehps.contracts import canonical_digest

from .contracts import MeasurementValidationContractError, MeasurementValidationManifest
from .statistics import wilson_interval


PASS_FACT = "m4-p2-measurement-decision:PASS_TO_P3"
REPAIR_FACT = "m4-p2-measurement-decision:REPAIR_MEASUREMENT_SYSTEM"
EXPECTED_REPLICATES_PER_CELL = 1000
EXPECTED_CELL_COUNT = 31
EXPECTED_INJECTED_CELL_COUNT = 28


def _digest_payload(payload: dict[str, Any], *, domain: str) -> dict[str, Any]:
    identity = dict(payload)
    identity.pop("artifact_digest", None)
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def aggregate_cell(
    replicates: Sequence[Mapping[str, Any]],
    *,
    manifest: MeasurementValidationManifest,
) -> dict[str, Any]:
    if len(replicates) != EXPECTED_REPLICATES_PER_CELL:
        raise MeasurementValidationContractError(
            "measurement_validation_cell_incomplete",
            "every cell requires exactly 1000 replicate artifacts",
        )
    first = replicates[0]
    keys = (
        "cell_id",
        "scale_id",
        "scenario_id",
        "mechanism",
        "signal_strength",
        "target_bits_per_issue",
        "outer_issue_count",
    )
    identity = {key: first[key] for key in keys}
    truth_values = {
        float(item["truth_bits_per_issue"]) for item in replicates
    }
    if len(truth_values) != 1:
        raise MeasurementValidationContractError(
            "measurement_validation_truth_mixed",
            "cell replicates must bind one P2.4 truth value",
        )
    truth = truth_values.pop()
    if any(any(item.get(key) != value for key, value in identity.items()) for item in replicates):
        raise MeasurementValidationContractError(
            "measurement_validation_cell_mixed",
            "cell aggregate contains mixed identities",
        )
    indices = [int(item["replicate_index"]) for item in replicates]
    digests = [str(item["artifact_digest"]) for item in replicates]
    evaluation_seed_digests = [
        str(item["evaluation_dataset_seed_digest"]) for item in replicates
    ]
    if sorted(indices) != list(range(EXPECTED_REPLICATES_PER_CELL)):
        raise MeasurementValidationContractError(
            "measurement_validation_cell_incomplete",
            "replicate indices must be exactly 0 through 999",
        )
    if len(set(digests)) != EXPECTED_REPLICATES_PER_CELL:
        raise MeasurementValidationContractError(
            "measurement_validation_duplicate_replicate",
            "replicate artifact identities are not unique",
        )
    if (
        len(set(evaluation_seed_digests)) != EXPECTED_REPLICATES_PER_CELL
        or any(len(value) != 64 for value in evaluation_seed_digests)
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_duplicate_seed",
            "every cell requires 1000 unique evaluation-dataset seeds",
        )
    if any(item.get("status") != "COMPLETE" for item in replicates):
        raise MeasurementValidationContractError(
            "measurement_validation_failed_replicate",
            "failed replicates cannot enter a cell aggregate",
        )
    pe2 = [float(item["PE2"]) for item in replicates]
    if any(not isfinite(value) for value in pe2):
        raise MeasurementValidationContractError(
            "measurement_validation_nonfinite_estimator",
            "PE2 values must be finite",
        )
    positive_count = sum(bool(item["positive_signal_decision"]) for item in replicates)
    power = positive_count / EXPECTED_REPLICATES_PER_CELL
    errors = [value - truth for value in pe2]
    bias = fsum(errors) / EXPECTED_REPLICATES_PER_CELL
    rmse = sqrt(
        fsum(value * value for value in errors) / EXPECTED_REPLICATES_PER_CELL
    )
    covered = sum(
        float(item["confidence_intervals"]["PE2"]["lower"])
        <= truth
        <= float(item["confidence_intervals"]["PE2"]["upper"])
        for item in replicates
    )
    coverage = covered / EXPECTED_REPLICATES_PER_CELL
    null_cell = identity["scenario_id"] == "NULL_UNIFORM"
    wilson_lower, wilson_upper = wilson_interval(
        positive_count,
        EXPECTED_REPLICATES_PER_CELL,
    )
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-measurement-cell-aggregate.v1",
        "artifact_type": "measurement_validation_cell_aggregate",
        "artifact_digest": "",
        **identity,
        "truth_bits_per_issue": truth,
        "negative_control_id": (
            "NC6_SYNTHETIC_NULL" if null_cell else None
        ),
        "negative_control_replicate_count": (
            EXPECTED_REPLICATES_PER_CELL if null_cell else 0
        ),
        "negative_control_seed_set_digest": (
            canonical_digest(
                evaluation_seed_digests,
                domain="dehps.m4-p2.nc6-evaluation-dataset-seed-set.v1",
            )
            if null_cell
            else None
        ),
        "replicate_count": EXPECTED_REPLICATES_PER_CELL,
        "ordered_replicate_digests": digests,
        "ordered_replicate_digest_root": canonical_digest(
            digests,
            domain="dehps.m4-p2.cell-replicates.v1",
        ),
        "positive_signal_count": positive_count,
        "false_positive_rate": power if null_cell else None,
        "empirical_power": None if null_cell else power,
        "wilson_95_interval": {
            "lower": wilson_lower,
            "upper": wilson_upper,
        },
        "mean_PE2": truth + bias,
        "bias_bits_per_issue": bias,
        "absolute_bias_bits_per_issue": abs(bias),
        "rmse_bits_per_issue": rmse,
        "PE2_coverage_count": covered,
        "PE2_coverage_rate": coverage,
        "false_positive_point_gate_pass": (
            power <= 0.075 if null_cell else None
        ),
        "false_positive_wilson_gate_pass": (
            wilson_upper <= 0.09 if null_cell else None
        ),
        "practical_power_gate_pass": (
            power >= manifest.practical_power_min
            if identity["signal_strength"] == "MEDIUM_PRACTICAL"
            else None
        ),
        "strong_power_gate_pass": (
            power >= manifest.strong_power_min
            if identity["signal_strength"] == "STRONG"
            else None
        ),
        "bias_gate_pass": (
            abs(bias) <= 0.0025 if not null_cell else True
        ),
        "rmse_finite_gate_pass": isfinite(rmse),
        "coverage_gate_pass": (
            manifest.coverage_lower <= coverage <= manifest.coverage_upper
            if not null_cell
            else True
        ),
        "parent_digests": digests,
    }
    return _digest_payload(
        payload,
        domain="dehps.m4-p2.measurement-cell-aggregate.v1",
    )


def _mechanism_key(scenario_id: str) -> str:
    for prefix in ("WEAK_", "MEDIUM_PRACTICAL_", "STRONG_"):
        if scenario_id.startswith(prefix):
            return scenario_id[len(prefix) :]
    raise MeasurementValidationContractError(
        "measurement_validation_scenario_invalid",
        f"cannot derive mechanism key from {scenario_id}",
    )


def build_mde_summary(
    aggregates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_identity = {
        (str(item["scale_id"]), str(item["scenario_id"])): item
        for item in aggregates
    }
    mechanisms = (
        "SINGLE_NUMBER",
        "LOCAL_TEMPORAL",
        "PAIR",
        "MARGINAL_PRESERVING",
    )
    strengths = (
        (0.001, "WEAK"),
        (0.01, "MEDIUM_PRACTICAL"),
        (0.05, "STRONG"),
    )
    scales = ("FORWARD_61", "HISTORICAL", "LONG")
    issue_counts = {"FORWARD_61": 61, "HISTORICAL": 2581, "LONG": 6062}
    per_mechanism_scale: list[dict[str, Any]] = []
    for scale in scales:
        for mechanism in mechanisms:
            tested: list[dict[str, Any]] = []
            for strength, prefix in strengths:
                item = by_identity.get((scale, f"{prefix}_{mechanism}"))
                if item is not None:
                    tested.append(
                        {
                            "strength_bits_per_issue": strength,
                            "empirical_power": float(item["empirical_power"]),
                        }
                    )
            if not tested:
                continue
            passing = [
                item["strength_bits_per_issue"]
                for item in tested
                if item["empirical_power"] >= 0.8
            ]
            upper: float | None = min(passing) if passing else None
            per_mechanism_scale.append(
                {
                    "scale_id": scale,
                    "outer_issue_count": issue_counts[scale],
                    "mechanism": mechanism,
                    "tested_grid": tested,
                    "mde_conservative_upper_bits_per_issue": upper,
                    "mde_bracket": (
                        f"<= {upper:g}" if upper is not None else "> 0.05"
                    ),
                    "interpolation_used": False,
                }
            )
    forward = [
        item
        for item in per_mechanism_scale
        if item["scale_id"] == "FORWARD_61"
    ]
    if len(forward) != 4:
        raise MeasurementValidationContractError(
            "measurement_validation_mde_incomplete",
            "FORWARD_61 requires four mechanism MDE results",
        )
    forward_upper = [
        item["mde_conservative_upper_bits_per_issue"] for item in forward
    ]
    decision_upper = (
        max(float(value) for value in forward_upper)
        if all(value is not None for value in forward_upper)
        else None
    )

    required_counts: list[dict[str, Any]] = []
    for mechanism in mechanisms:
        for strength, prefix in strengths:
            scheduled = []
            for scale in scales:
                item = by_identity.get((scale, f"{prefix}_{mechanism}"))
                if item is not None:
                    scheduled.append(
                        (
                            issue_counts[scale],
                            float(item["empirical_power"]),
                        )
                    )
            passing_counts = [count for count, power in scheduled if power >= 0.8]
            required_counts.append(
                {
                    "mechanism": mechanism,
                    "strength_bits_per_issue": strength,
                    "tested_issue_counts_and_power": [
                        {"outer_issue_count": count, "empirical_power": power}
                        for count, power in sorted(scheduled)
                    ],
                    "required_issue_count": (
                        min(passing_counts) if passing_counts else None
                    ),
                    "required_issue_count_bracket": (
                        f"<= {min(passing_counts)}"
                        if passing_counts
                        else "> 6062"
                    ),
                }
            )
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-measurement-mde-summary.v1",
        "artifact_type": "measurement_validation_mde_summary",
        "artifact_digest": "",
        "target_power": 0.8,
        "tested_strengths_bits_per_issue": [0.001, 0.01, 0.05],
        "per_mechanism_scale": per_mechanism_scale,
        "decision_policy_mde_at_61_bits_per_issue": decision_upper,
        "decision_policy_mde_at_61_bracket": (
            f"<= {decision_upper:g}" if decision_upper is not None else "> 0.05"
        ),
        "decision_policy_mde_at_61_bits_per_red_number_event": (
            decision_upper / 33.0 if decision_upper is not None else None
        ),
        "required_issue_count_by_strength": required_counts,
        "interpolation_used": False,
        "parent_digests": [
            str(item["artifact_digest"]) for item in aggregates
        ],
    }
    return _digest_payload(
        payload,
        domain="dehps.m4-p2.measurement-mde-summary.v1",
    )


def evaluate_automatic_gate(
    *,
    manifest: MeasurementValidationManifest,
    completion: Mapping[str, Any],
    aggregates: Sequence[Mapping[str, Any]],
    deterministic_replay_passed: bool,
) -> dict[str, Any]:
    if len(aggregates) != EXPECTED_CELL_COUNT:
        raise MeasurementValidationContractError(
            "measurement_validation_aggregate_incomplete",
            "automatic gate requires exactly 31 cell aggregates",
        )
    null_cells = [
        item for item in aggregates if item["scenario_id"] == "NULL_UNIFORM"
    ]
    injected = [
        item for item in aggregates if item["scenario_id"] != "NULL_UNIFORM"
    ]
    practical = [
        item
        for item in injected
        if item["signal_strength"] == "MEDIUM_PRACTICAL"
    ]
    strong = [
        item for item in injected if item["signal_strength"] == "STRONG"
    ]
    if (
        len(null_cells) != 3
        or len(injected) != EXPECTED_INJECTED_CELL_COUNT
        or len(practical) != 12
        or len(strong) != 8
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_gate_scope_incomplete",
            "null, practical, strong, or injected cell scope changed",
        )

    requirements = {
        "all_31000_analysis_replicates_and_frozen_seeds_complete_exactly_once": (
            completion.get("replicate_count") == 31000
            and completion.get("duplicate_replicate_count") == 0
            and completion.get("failed_replicate_count") == 0
            and completion.get("negative_control_id")
            == "NC6_SYNTHETIC_NULL"
            and completion.get("negative_control_cell_count") == 3
            and completion.get("negative_control_replicates_per_cell")
            == manifest.negative_control_replicates
            and completion.get("negative_control_replicate_count") == 3000
            and completion.get("checkpoint_journal_count") == 31000
            and completion.get("checkpoint_journal_failure_count") == 0
        ),
        "all_bootstrap_and_permutation_seed_sets_complete": (
            completion.get("bootstrap_seed_count") == 31_000 * 2000
            and completion.get("permutation_seed_count") == 31_000 * 2000
            and completion.get("incomplete_seed_set_count") == 0
        ),
        "all_NULL_UNIFORM_point_and_Wilson_false_positive_gates_pass": all(
            item["false_positive_point_gate_pass"]
            and item["false_positive_wilson_gate_pass"]
            for item in null_cells
        ),
        "all_practical_strength_cell_power_gates_pass": all(
            item["practical_power_gate_pass"] for item in practical
        ),
        "all_strong_signal_cell_power_gates_pass": all(
            item["strong_power_gate_pass"] for item in strong
        ),
        "all_primary_PE2_absolute_bias_cell_gates_pass": all(
            item["bias_gate_pass"] for item in injected
        ),
        "all_primary_PE2_coverage_cell_gates_pass": all(
            item["coverage_gate_pass"] for item in injected
        ),
        "all_RMSE_outputs_finite": all(
            item["rmse_finite_gate_pass"] for item in injected
        ),
        "all_leakage_checks_pass": completion.get("leakage_failure_count") == 0,
        "deterministic_replay_passes": deterministic_replay_passed,
    }
    expected = manifest.payload["automatic_gate"]["PASS_TO_P3_requires_all"]
    if set(requirements) != set(expected):
        raise MeasurementValidationContractError(
            "measurement_validation_gate_requirement_mismatch",
            "implemented gate requirements differ from the frozen manifest",
        )
    passed = all(requirements.values())
    decision = "PASS_TO_P3" if passed else "REPAIR_MEASUREMENT_SYSTEM"
    decision_fact = PASS_FACT if passed else REPAIR_FACT
    mde = build_mde_summary(aggregates)
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-automatic-measurement-gate.v1",
        "artifact_type": "automatic_measurement_gate",
        "artifact_digest": "",
        "measurement_validation_manifest_digest": manifest.artifact_digest,
        "decision": decision,
        "decision_fact": decision_fact,
        "requirements": requirements,
        "failed_requirements": [
            key for key, value in requirements.items() if not value
        ],
        "manual_override_used": False,
        "facts_mutually_exclusive": True,
        "P3_reachable": passed,
        "repair_reachable": not passed,
        "mde_summary": mde,
        "parent_digests": [
            str(completion["artifact_digest"]),
            *(str(item["artifact_digest"]) for item in aggregates),
            str(mde["artifact_digest"]),
        ],
    }
    return _digest_payload(
        payload,
        domain="dehps.m4-p2.automatic-measurement-gate.v1",
    )
