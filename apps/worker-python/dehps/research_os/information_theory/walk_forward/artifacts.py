from __future__ import annotations

from math import fsum
from statistics import median
from typing import Any, Mapping, Sequence

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory import metrics as metric_kernel

from .contracts import (
    FROZEN_METRIC_KERNEL_DIGEST,
    RUN_SCHEMA_VERSION,
    SETTLEMENT_SCHEMA_VERSION,
    THEORETICAL_PROBABILITY,
    FoldIdentity,
)
from .errors import WalkForwardError


def settle_fold(
    *,
    fold: FoldIdentity,
    prediction_checkpoint: Mapping[str, Any],
    target_vector: Sequence[int],
    metric_kernel_digest: str,
) -> dict[str, Any]:
    if metric_kernel_digest != FROZEN_METRIC_KERNEL_DIGEST:
        raise WalkForwardError(
            "metric_kernel_identity_mismatch", "P2.2 kernel digest changed"
        )
    if prediction_checkpoint.get("fold_digest") != fold.fold_digest:
        raise WalkForwardError(
            "prediction_fold_mismatch", "checkpoint belongs to another fold"
        )
    metric = metric_kernel.evaluate_issue(
        issue_id=str(fold.test_issue),
        cluster_id=str(fold.test_issue),
        target_vector=target_vector,
        baseline_probability_vector=(THEORETICAL_PROBABILITY,) * 33,
        probe_probability_vector=prediction_checkpoint["probabilities_33"],
    )
    metric_payload = metric.to_dict()
    issue_metric_digest = canonical_digest(
        metric_payload, domain="dehps.m4.walk-forward.issue-metric.v1"
    )
    target_digest = canonical_digest(
        list(target_vector), domain="dehps.m4.walk-forward.revealed-target.v1"
    )
    payload: dict[str, Any] = {
        "schema_version": SETTLEMENT_SCHEMA_VERSION,
        "artifact_type": "settled_fold_metric",
        "artifact_digest": "",
        "fold_id": fold.fold_id,
        "fold_digest": fold.fold_digest,
        "test_issue": fold.test_issue,
        "prediction_checkpoint_digest": prediction_checkpoint["artifact_digest"],
        "target_digest": target_digest,
        "issue_metric_artifact_digest": issue_metric_digest,
        "pe1_bits_per_issue": metric.observed_log_loss_gain_bits_per_issue,
        "brier_gain_per_issue": metric.brier_gain_per_issue,
        "probability_clipping_diagnostics": metric.probe_clip_diagnostics.to_dict(),
        "issue_metric": metric_payload,
        "metric_kernel_digest": metric_kernel_digest,
        "eligible_for_p2_gate": False,
        "descriptive_only": True,
        "pe2_status": "NOT_IMPLEMENTED",
        "parent_digests": [
            prediction_checkpoint["artifact_digest"],
            target_digest,
            metric_kernel_digest,
        ],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity, domain="dehps.m4.walk-forward.fold-settlement.v1"
    )
    return payload


def aggregate_settlements(
    settlements: Sequence[Mapping[str, Any]],
    *,
    failed_folds: Sequence[Mapping[str, Any]],
    fallback_fold_count: int,
) -> dict[str, Any]:
    ordered = sorted(settlements, key=lambda item: int(item["test_issue"]))
    gains = [float(item["pe1_bits_per_issue"]) for item in ordered]
    brier = [float(item["brier_gain_per_issue"]) for item in ordered]
    predicted_counts = [
        float(item["issue_metric"]["predicted_red_count"]) for item in ordered
    ]
    clip_count = sum(
        int(item["probability_clipping_diagnostics"]["clip_count_low"])
        + int(item["probability_clipping_diagnostics"]["clip_count_high"])
        for item in ordered
    )
    completed = len(ordered)
    aggregate = {
        "fold_count": completed + len(failed_folds),
        "completed_fold_count": completed,
        "failed_fold_count": len(failed_folds),
        "fallback_fold_count": fallback_fold_count,
        "sample_size_for_inference": completed,
        "mean_pe1_bits_per_issue": fsum(gains) / completed if completed else None,
        "median_pe1_bits_per_issue": median(gains) if gains else None,
        "cumulative_pe1_bits": fsum(gains),
        "mean_brier_gain_per_issue": fsum(brier) / completed if completed else None,
        "mean_predicted_red_count": (
            fsum(predicted_counts) / completed if completed else None
        ),
        "probability_clip_count": clip_count,
        "convergence_summary": {
            "completed": completed,
            "failed": len(failed_folds),
            "fallback": fallback_fold_count,
        },
        "failed_folds": [dict(value) for value in failed_folds],
        "iid_confidence_interval": None,
        "block_bootstrap_confidence_interval": None,
        "permutation_p_value": None,
        "minimum_detectable_effect": None,
        "power": "NOT_EVALUATED",
        "pe2": "NOT_IMPLEMENTED",
        "descriptive_only": True,
        "eligible_for_p2_gate": False,
        "evidence_eligibility": [
            "SMOKE_TEST_ONLY",
            "NOT_POWER_EVIDENCE",
            "NOT_P2_GATE_EVIDENCE",
        ],
    }
    return aggregate


def build_run_artifact(
    *,
    run_digest: str,
    dataset_digest: str,
    harness_manifest_digest: str,
    probe_id: str,
    probe_manifest_digest: str,
    fold_digests: Sequence[str],
    probe_state_digests: Sequence[str],
    preprocessing_state_digests: Sequence[str],
    prediction_digests: Sequence[str],
    settlement_digests: Sequence[str],
    aggregate: Mapping[str, Any],
    git_commit: str,
    created_at: str,
    seed_policy: Mapping[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": RUN_SCHEMA_VERSION,
        "artifact_type": "synthetic_walk_forward_smoke",
        "artifact_digest": "",
        "run_digest": run_digest,
        "dataset_digest": dataset_digest,
        "harness_manifest_digest": harness_manifest_digest,
        "probe_id": probe_id,
        "probe_manifest_digest": probe_manifest_digest,
        "fold_digests": list(fold_digests),
        "probe_state_digests": list(probe_state_digests),
        "preprocessing_state_digests": list(preprocessing_state_digests),
        "prediction_checkpoint_digests": list(prediction_digests),
        "settlement_digests": list(settlement_digests),
        "aggregate": dict(aggregate),
        "git_commit": git_commit,
        "working_tree_clean": True,
        "created_at": created_at,
        "seed_policy": dict(seed_policy),
        "descriptive_only": True,
        "eligible_for_p2_gate": False,
        "formal_power_evidence": False,
        "real_data_evidence": False,
        "production_checkpoint": False,
        "parent_digests": [
            dataset_digest,
            harness_manifest_digest,
            probe_manifest_digest,
            *fold_digests,
            *probe_state_digests,
            *preprocessing_state_digests,
            *prediction_digests,
            *settlement_digests,
        ],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity, domain="dehps.m4.walk-forward.run-artifact.v1"
    )
    return payload
