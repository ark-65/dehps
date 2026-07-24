from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from dehps.research_os.information_theory.digest import config_digest
from dehps.training.research_fingerprint import SeedPolicy

from .contracts import (
    RUN_SCHEMA_VERSION,
    SyntheticRunManifest,
    SyntheticScale,
    SyntheticScenario,
)


FROZEN_PREREGISTRATION_DIGEST = (
    "6e03cd828378badda6995c6582d80165b0a4ee3b5899b97737bad1494fcf1ae1"
)
FROZEN_DECISION_POLICY_DIGEST = (
    "824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d"
)


def load_synthetic_run_manifest(path: Path) -> SyntheticRunManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("synthetic run manifest root must be an object")
    return validate_synthetic_run_manifest(payload)


def validate_synthetic_run_manifest(payload: Mapping[str, Any]) -> SyntheticRunManifest:
    if payload.get("schema_version") != RUN_SCHEMA_VERSION:
        raise ValueError("unsupported synthetic run schema")
    if payload.get("phase") != "M4-P2.1" or payload.get("status") != "PLANNED":
        raise ValueError("phase_gate_not_satisfied: only planned P2.1 contract work is legal")
    if payload.get("data_source") != "synthetic_only" or payload.get("real_dataset_reference") is not None:
        raise ValueError("synthetic run manifest cannot reference real data")
    if payload.get("preregistration_digest") != FROZEN_PREREGISTRATION_DIGEST:
        raise ValueError("preregistration digest mismatch")
    if payload.get("decision_policy_digest") != FROZEN_DECISION_POLICY_DIGEST:
        raise ValueError("decision policy digest mismatch")
    supplied_digest = str(payload.get("artifact_digest", ""))
    expected_digest = config_digest(payload)
    if supplied_digest != expected_digest:
        raise ValueError("synthetic run manifest digest mismatch")

    raw_policy = payload.get("seed_policy")
    if not isinstance(raw_policy, Mapping):
        raise ValueError("synthetic run requires SeedPolicy")
    seed_range = raw_policy.get("seed_range")
    if not isinstance(seed_range, list) or len(seed_range) != 2:
        raise ValueError("seed policy requires [start,stop) seed_range")
    start, stop = (int(seed_range[0]), int(seed_range[1]))
    if (start, stop) != (200000, 201000):
        raise ValueError("frozen null seed range changed")
    policy = SeedPolicy(
        seeds=tuple(range(start, stop)),
        aggregation=str(raw_policy.get("aggregation", "distribution")),
        selection_policy=str(raw_policy.get("selection_policy", "no_best_seed")),
    )
    if len(policy.seeds) != int(payload.get("null_replicate_count", 0)):
        raise ValueError("replicate count must equal normalized seed count")

    raw_scenarios = payload.get("scenarios")
    if not isinstance(raw_scenarios, list) or len(raw_scenarios) != 13:
        raise ValueError("run manifest must freeze one null and twelve injected scenarios")
    scenarios = tuple(
        SyntheticScenario(
            scenario_id=str(item["scenario_id"]),
            mechanism=str(item["mechanism"]),
            signal_strength=str(item["signal_strength"]),
            target_bits_per_issue=float(item["target_bits_per_issue"]),
            implemented=bool(item["implemented"]),
            data_source=str(item.get("data_source", "synthetic_only")),
        )
        for item in raw_scenarios
    )
    nulls = [item for item in scenarios if item.scenario_id == "NULL_UNIFORM"]
    if len(nulls) != 1 or not nulls[0].implemented:
        raise ValueError("exactly one implemented NULL_UNIFORM scenario is required")
    if any(item.implemented for item in scenarios if item.scenario_id != "NULL_UNIFORM"):
        raise ValueError("injected-signal scenarios remain unimplemented in P2.1")
    expected_scenarios = {
        "NULL_UNIFORM": (
            "uniform_choose_6_without_replacement_from_33",
            "ZERO",
            0.0,
        ),
        **{
            f"{strength}_{suffix}": (mechanism, strength, bits)
            for strength, bits in (
                ("WEAK", 0.001),
                ("MEDIUM_PRACTICAL", 0.01),
                ("STRONG", 0.05),
            )
            for suffix, mechanism in (
                ("SINGLE_NUMBER", "single_number_conditional_shift"),
                ("LOCAL_TEMPORAL", "local_temporal_state"),
                ("PAIR", "pair_conditional_signal"),
                (
                    "MARGINAL_PRESERVING",
                    "marginal_preserving_conditional_signal",
                ),
            )
        },
    }
    actual_scenarios = {
        item.scenario_id: (
            item.mechanism,
            item.signal_strength,
            item.target_bits_per_issue,
        )
        for item in scenarios
    }
    if actual_scenarios != expected_scenarios:
        raise ValueError("frozen synthetic scenario definitions changed")

    raw_scales = payload.get("sequence_scales")
    if not isinstance(raw_scales, list):
        raise ValueError("sequence_scales must be an array")
    scales = tuple(
        SyntheticScale(
            scale_id=str(item["scale_id"]),
            sequence_length=int(item["sequence_length"]),
            minimum_training_length=int(item["minimum_training_length"]),
            outer_evaluation_length=int(item["outer_evaluation_length"]),
            derivation=str(item["derivation"]),
        )
        for item in raw_scales
    )
    frozen_lengths = {item.scale_id: item.sequence_length for item in scales}
    if frozen_lengths != {"HISTORICAL": 3481, "FORWARD_61": 961, "LONG": 6962}:
        raise ValueError("frozen synthetic sequence scales changed")
    if payload.get("probe_allowlist") != [
        "EMPIRICAL_BASELINE",
        "REGULARIZED_LOGISTIC_REGRESSION",
        "NAIVE_BAYES",
        "SHALLOW_CALIBRATED_TREE",
    ]:
        raise ValueError("probe allowlist changed")
    if payload.get("block_sizes") != {"primary": 5, "sensitivity": [3, 5, 8, 13]}:
        raise ValueError("block sizes changed")
    workload = payload.get("planned_workload")
    if not isinstance(workload, Mapping):
        raise ValueError("planned workload is required")
    expected_outer_predictions = (
        13 * 1000 * 2581
        + 13 * 1000 * 61
        + 5 * 1000 * 6062
    )
    if (
        workload.get("scenario_replicates") != 31000
        or workload.get("outer_issue_predictions") != expected_outer_predictions
        or workload.get("number_probability_predictions_per_probe")
        != expected_outer_predictions * 33
        or workload.get("all_four_probe_number_probability_predictions")
        != expected_outer_predictions * 33 * 4
    ):
        raise ValueError("planned workload arithmetic changed")
    if payload.get("execution") != {
        "large_replicates_executed": False,
        "metrics_executed": False,
        "real_data_executed": False,
    }:
        raise ValueError("P2.1 manifest must record zero formal execution")
    return SyntheticRunManifest(
        payload=dict(payload),
        artifact_digest=expected_digest,
        seed_policy=policy,
        scenarios=scenarios,
        scales=scales,
    )
