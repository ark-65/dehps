from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

from .contracts import (
    FROZEN_DECISION_POLICY_DIGEST,
    FROZEN_METRIC_KERNEL_DIGEST,
    FROZEN_PREREGISTRATION_DIGEST,
    FROZEN_SYNTHETIC_MANIFEST_DIGEST,
    HARNESS_SCHEMA_VERSION,
    HARNESS_VERSION,
    HarnessManifest,
)
from .errors import WalkForwardError


def load_harness_manifest(path: Path) -> HarnessManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WalkForwardError("invalid_walk_forward_manifest", str(exc)) from exc
    if not isinstance(payload, Mapping):
        raise WalkForwardError(
            "invalid_walk_forward_manifest", "manifest must be an object"
        )
    return validate_harness_manifest(payload)


def validate_harness_manifest(payload: Mapping[str, Any]) -> HarnessManifest:
    if (
        payload.get("schema_version") != HARNESS_SCHEMA_VERSION
        or payload.get("harness_version") != HARNESS_VERSION
        or payload.get("phase") != "M4-P2.3"
        or payload.get("status") != "FROZEN"
    ):
        raise WalkForwardError(
            "phase_gate_not_satisfied", "P2.3 manifest is not frozen"
        )
    frozen = {
        "preregistration_digest": FROZEN_PREREGISTRATION_DIGEST,
        "decision_policy_digest": FROZEN_DECISION_POLICY_DIGEST,
        "synthetic_manifest_digest": FROZEN_SYNTHETIC_MANIFEST_DIGEST,
        "metric_kernel_digest": FROZEN_METRIC_KERNEL_DIGEST,
    }
    for field, expected in frozen.items():
        if payload.get(field) != expected:
            code = (
                "metric_kernel_identity_mismatch"
                if field == "metric_kernel_digest"
                else f"{field}_mismatch"
            )
            raise WalkForwardError(code, f"{field} changed")
    split = payload.get("outer_split")
    if split != {
        "mode": "expanding_window",
        "minimum_training_issues": 900,
        "test_horizon": 1,
        "test_issue_prediction_count": 1,
    }:
        raise WalkForwardError(
            "outer_split_contract_mismatch", "frozen outer split changed"
        )
    inner = payload.get("inner_validation")
    if inner != {
        "method": "three_fold_expanding_blocked_time_series",
        "fold_count": 3,
        "selection_metric": "issue_mean_log_loss",
        "all_preprocessing_nested": True,
        "outer_test_metrics_used": False,
        "tie_break": "lower_complexity_then_lexical_config_id",
    }:
        raise WalkForwardError(
            "inner_validation_contract_mismatch", "frozen inner contract changed"
        )
    probes = payload.get("probes")
    if not isinstance(probes, Mapping):
        raise WalkForwardError(
            "missing_probe_hyperparameter_contract", "probe registry is required"
        )
    logistic = probes.get("REGULARIZED_LOGISTIC_REGRESSION")
    if not isinstance(logistic, Mapping) or dict(logistic) != {
        "probe_type": "regularized_logistic_regression",
        "penalty": ["l2"],
        "C": [0.01, 0.1, 1.0],
        "class_weight": [None],
        "solver": "liblinear",
        "max_iter": 1000,
        "tol": 0.0001,
        "implementation": "scikit-learn==1.9.0",
        "convergence_fail_policy": "outer_prediction_invalid_fail_closed",
        "seed_source": "dataset_replicate_seed",
    }:
        raise WalkForwardError(
            "missing_probe_hyperparameter_contract",
            "logistic contract must exactly match preregistration",
        )
    empirical = probes.get("EMPIRICAL_BASELINE")
    if not isinstance(empirical, Mapping) or empirical.get("smoothing") != (
        "beta_binomial_jeffreys_alpha_0_5_beta_0_5"
    ):
        raise WalkForwardError(
            "missing_probe_hyperparameter_contract",
            "empirical smoothing contract changed",
        )
    smoke = payload.get("smoke_execution")
    if not isinstance(smoke, Mapping) or (
        not isinstance(smoke.get("outer_fold_count"), int)
        or smoke["outer_fold_count"] < 1
        or smoke["outer_fold_count"] > 3
        or smoke.get("evidence_eligibility")
        != ["SMOKE_TEST_ONLY", "NOT_POWER_EVIDENCE", "NOT_P2_GATE_EVIDENCE"]
    ):
        raise WalkForwardError(
            "large_synthetic_run_forbidden", "P2.3 permits only a tiny smoke"
        )
    if payload.get("pe2_status") != "NOT_IMPLEMENTED":
        raise WalkForwardError("pe2_contract_violation", "PE2 remains unimplemented")
    expected = config_digest(payload)
    if payload.get("artifact_digest") != expected:
        raise WalkForwardError(
            "walk_forward_manifest_digest_mismatch", "manifest changed"
        )
    if not str(payload.get("created_at", "")).strip():
        raise WalkForwardError(
            "invalid_walk_forward_manifest", "created_at is required"
        )
    return HarnessManifest(
        payload=dict(payload),
        artifact_digest=expected,
        minimum_training_issues=900,
        smoke_outer_fold_count=int(smoke["outer_fold_count"]),
        created_at=str(payload["created_at"]),
    )


def probe_manifest_digest(
    manifest: HarnessManifest,
    *,
    probe_id: str,
) -> str:
    return canonical_digest(
        {
            "harness_manifest_digest": manifest.artifact_digest,
            "probe_id": probe_id,
            "probe": manifest.probe(probe_id),
        },
        domain="dehps.m4.probe-manifest.v1",
    )


def preprocessing_manifest_digest(manifest: HarnessManifest) -> str:
    return canonical_digest(
        manifest.payload["preprocessing"],
        domain="dehps.m4.preprocessing-manifest.v1",
    )
