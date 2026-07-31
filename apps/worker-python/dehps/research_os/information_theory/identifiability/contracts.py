from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.walk_forward.feature_view import (
    FEATURE_MANIFEST_DIGEST,
)

IDENTIFIABILITY_PREFLIGHT_MANIFEST_DIGEST = (
    "5b2852741e544f93c5f9fbc80a307537b22e16ebc4cc818b0b6f426b591114e3"
)
SUPERSEDED_RUN_ARCHIVE_DIGEST = (
    "d2d959f6c326e42f80bf92ae652087c941c77e0bacbe22f29e04d4cf8c9f4d6d"
)
OLD_MEASUREMENT_VALIDATION_MANIFEST_DIGEST = (
    "953ae76e2e28523b7d067c2b73dac8bec63ff2417db283fd516fe900e52402f8"
)
P24_COMPLETION_DIGEST = (
    "328144fa1abebfee88d46dbbce6d9deb7b9f1f5834fb9a0c83cc55adef32a353"
)
METRIC_KERNEL_DIGEST = (
    "56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2"
)
WALK_FORWARD_HARNESS_DIGEST = (
    "177a3d591b7557a4231a276bfb007f0d42a94d942824403f5376f94fe904d2ca"
)


class IdentifiabilityContractError(ValueError):
    pass


@dataclass(frozen=True)
class IdentifiabilityPreflightManifest:
    payload: Mapping[str, Any]
    artifact_digest: str
    truth_artifact_digests: tuple[str, ...]
    comparison_tolerance_bits: float
    joint_signal_epsilon_bits: float
    approved_repair_strategy: str


def load_superseded_run_archive(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentifiabilityContractError(str(exc)) from exc
    if not isinstance(payload, Mapping):
        raise IdentifiabilityContractError(
            "superseded run archive must be an object"
        )
    if (
        payload.get("schema_version")
        != "dehps-m4-p2-superseded-run-archive.v1"
        or payload.get("artifact_type")
        != "measurement_validation_superseded_run_archive"
        or payload.get("status") != "SUPERSEDED"
        or payload.get("production_action") != "none"
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("artifact_digest") != SUPERSEDED_RUN_ARCHIVE_DIGEST
    ):
        raise IdentifiabilityContractError(
            "superseded run archive identity changed"
        )
    old_task = payload.get("old_task")
    checkpoint = payload.get("checkpoint")
    blindness = payload.get("result_blindness")
    successor = payload.get("successor")
    if (
        not isinstance(old_task, Mapping)
        or old_task.get("task_key")
        != "m4-p2-false-positive-and-power-runs"
        or old_task.get("parent_execution_id")
        != "8e1c601233833b60442b45ebaeeaea53679c34eef1d00de5480827f415d517fd"
        or old_task.get("measurement_validation_manifest_digest")
        != OLD_MEASUREMENT_VALIDATION_MANIFEST_DIGEST
        or not isinstance(checkpoint, Mapping)
        or checkpoint.get("complete_replicate_artifacts") != 13223
        or checkpoint.get("checkpoint_preserved") is not True
        or checkpoint.get("artifacts_deleted") is not False
        or not isinstance(blindness, Mapping)
        or blindness.get("partial_statistical_results_inspected") is not False
        or blindness.get("partial_results_eligible_for_evidence") is not False
        or not isinstance(successor, Mapping)
        or successor.get("repair_strategy")
        != "SCHEME_A_MARGINAL_TRUTH_TO_MARGINAL_METRIC"
        or successor.get("old_execution_resumable") is not False
    ):
        raise IdentifiabilityContractError(
            "superseded run archive safety contract changed"
        )
    return payload


def load_identifiability_preflight_manifest(
    path: Path,
) -> IdentifiabilityPreflightManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentifiabilityContractError(str(exc)) from exc
    if not isinstance(payload, Mapping):
        raise IdentifiabilityContractError(
            "identifiability preflight manifest must be an object"
        )
    return validate_identifiability_preflight_manifest(payload)


def validate_identifiability_preflight_manifest(
    payload: Mapping[str, Any],
) -> IdentifiabilityPreflightManifest:
    if (
        payload.get("schema_version")
        != "dehps-m4-p2-identifiability-preflight-manifest.v1"
        or payload.get("artifact_type")
        != "measurement_identifiability_preflight_manifest"
        or payload.get("phase") != "M4-P2.6-PREFLIGHT"
        or payload.get("status") != "FROZEN"
        or payload.get("production_action") != "none"
    ):
        raise IdentifiabilityContractError(
            "identifiability preflight identity or governance changed"
        )
    supplied_digest = str(payload.get("artifact_digest") or "")
    if (
        supplied_digest != config_digest(payload)
        or supplied_digest != IDENTIFIABILITY_PREFLIGHT_MANIFEST_DIGEST
    ):
        raise IdentifiabilityContractError(
            "identifiability preflight manifest digest changed"
        )
    result_blind = payload.get("result_blind_freeze")
    if not isinstance(result_blind, Mapping) or dict(result_blind) != {
        "p2_6_partial_statistical_results_inspected": False,
        "decision_uses_only_frozen_contracts_and_p2_4_truth": True,
        "decision_frozen_before_repaired_p2_6_execution": True,
    }:
        raise IdentifiabilityContractError(
            "identifiability preflight must remain result blind"
        )
    upstream = payload.get("upstream_identities")
    if not isinstance(upstream, Mapping):
        raise IdentifiabilityContractError(
            "identifiability preflight upstream identities are missing"
        )
    expected_upstream = {
        "old_measurement_validation_manifest_digest": (
            OLD_MEASUREMENT_VALIDATION_MANIFEST_DIGEST
        ),
        "p2_4_completion_digest": P24_COMPLETION_DIGEST,
        "metric_kernel_digest": METRIC_KERNEL_DIGEST,
        "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
        "feature_manifest_digest": FEATURE_MANIFEST_DIGEST,
        "superseded_run_archive_digest": SUPERSEDED_RUN_ARCHIVE_DIGEST,
    }
    if {
        key: upstream.get(key) for key in expected_upstream
    } != expected_upstream:
        raise IdentifiabilityContractError(
            "identifiability preflight upstream identity changed"
        )
    truth_digests = tuple(str(value) for value in upstream.get(
        "p2_4_truth_artifact_digests", ()
    ))
    if len(truth_digests) != 12 or len(set(truth_digests)) != 12:
        raise IdentifiabilityContractError(
            "all twelve unique P2.4 truth artifacts are required"
        )
    contract = payload.get("measurement_contract")
    if not isinstance(contract, Mapping) or dict(contract) != {
        "current_truth_estimand": "I(Y_vector; state)",
        "current_metric_estimand": "sum_n I(Y_n; state)",
        "current_metric_observation_unit": "33_independent_Bernoulli_events",
        "approved_repair_strategy": "SCHEME_A_MARGINAL_TRUTH_TO_MARGINAL_METRIC",
        "repaired_truth_estimand": "sum_n I(Y_n; state)",
        "joint_only_mechanisms": "negative_control_not_power_target",
    }:
        raise IdentifiabilityContractError(
            "truth and metric estimand binding changed"
        )
    rules = payload.get("decision_rules")
    if not isinstance(rules, Mapping):
        raise IdentifiabilityContractError("decision rules are missing")
    if (
        rules.get("joint_signal_epsilon_bits") != 1e-12
        or rules.get("comparison_tolerance_bits") != 0.0025
        or rules.get("joint_positive_marginal_zero")
        != "NOT_IDENTIFIABLE_BY_CURRENT_METRIC"
        or rules.get("absolute_estimand_gap_above_tolerance")
        != "TRUTH_METRIC_ESTIMAND_MISMATCH"
        or rules.get("required_conditioning_state_not_representable")
        != "STATE_NOT_EXPOSED_TO_PROBE"
        or rules.get("any_failure")
        != "MEASUREMENT_CONTRACT_REPAIR_REQUIRED"
        or rules.get("all_pass")
        != "MEASUREMENT_CONTRACT_IDENTIFIABLE"
    ):
        raise IdentifiabilityContractError("decision rules changed")
    facts = payload.get("automatic_decision_facts")
    if facts != {
        "identifiable": (
            "m4-p2-identifiability-decision:"
            "MEASUREMENT_CONTRACT_IDENTIFIABLE"
        ),
        "repair_required": (
            "m4-p2-identifiability-decision:"
            "MEASUREMENT_CONTRACT_REPAIR_REQUIRED"
        ),
        "mutual_exclusion": "exactly_one",
    }:
        raise IdentifiabilityContractError("automatic decision facts changed")
    return IdentifiabilityPreflightManifest(
        payload=payload,
        artifact_digest=supplied_digest,
        truth_artifact_digests=truth_digests,
        comparison_tolerance_bits=float(
            rules["comparison_tolerance_bits"]
        ),
        joint_signal_epsilon_bits=float(
            rules["joint_signal_epsilon_bits"]
        ),
        approved_repair_strategy=str(
            contract["approved_repair_strategy"]
        ),
    )
