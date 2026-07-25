from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.artifact_contracts import (
    validate_artifact_identity,
)
from dehps.research_os.information_theory.digest import config_digest

from .aggregation import aggregate_issue_metrics
from .code_length import joint_uniform_code_length
from .contracts import (
    KERNEL_VERSION,
    METRIC_ARTIFACT_SCHEMA_VERSION,
    METRIC_INPUT_SCHEMA_VERSION,
    METRIC_MANIFEST_SCHEMA_VERSION,
    MetricKernelManifest,
    UnitContract,
)
from .errors import MetricKernelError
from .kernel import evaluate_issue


FROZEN_PREREGISTRATION_DIGEST = (
    "6e03cd828378badda6995c6582d80165b0a4ee3b5899b97737bad1494fcf1ae1"
)
FROZEN_DECISION_POLICY_DIGEST = (
    "824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d"
)
FROZEN_SYNTHETIC_MANIFEST_DIGEST = (
    "8493987cc4414414e33fb5c5ea148be1f42a1d9e57609600c4346fb642cbfa08"
)
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def load_metric_kernel_manifest(path: Path) -> MetricKernelManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise MetricKernelError("invalid_metric_manifest", "manifest must be an object")
    return validate_metric_kernel_manifest(payload)


def validate_metric_kernel_manifest(
    payload: Mapping[str, Any],
) -> MetricKernelManifest:
    if payload.get("schema_version") != METRIC_MANIFEST_SCHEMA_VERSION:
        raise MetricKernelError("invalid_metric_manifest", "unsupported schema")
    if (
        payload.get("phase") != "M4-P2.2"
        or payload.get("status") != "FROZEN"
        or payload.get("metric_kernel_version") != KERNEL_VERSION
    ):
        raise MetricKernelError("phase_gate_not_satisfied", "P2.2 manifest is not frozen")
    if payload.get("preregistration_digest") != FROZEN_PREREGISTRATION_DIGEST:
        raise MetricKernelError("preregistration_digest_mismatch", "frozen digest changed")
    if payload.get("decision_policy_digest") != FROZEN_DECISION_POLICY_DIGEST:
        raise MetricKernelError("decision_policy_digest_mismatch", "frozen digest changed")
    if payload.get("synthetic_manifest_digest") != FROZEN_SYNTHETIC_MANIFEST_DIGEST:
        raise MetricKernelError("synthetic_manifest_digest_mismatch", "P2.1 digest changed")
    if payload.get("probability_clip") != {
        "epsilon": 1e-6,
        "lower": 1e-6,
        "upper": 0.999999,
        "source": "preregistration_v1.0.1",
    }:
        raise MetricKernelError("epsilon_mismatch", "frozen probability clip changed")
    unit_payload = payload.get("unit_contract")
    if not isinstance(unit_payload, Mapping):
        raise MetricKernelError("unit_mismatch", "unit contract is required")
    unit = UnitContract(**dict(unit_payload))
    if payload.get("baseline") != {
        "identity": "NUMBER_EVENT_COMPOSITE_BASELINE",
        "probability": {"numerator": 6, "denominator": 33},
        "aggregation": "sum_33_number_event_losses_per_issue",
    }:
        raise MetricKernelError("unknown_baseline", "baseline identity changed")
    if payload.get("gain_contract") != {
        "name": "observed_oos_log_loss_gain",
        "formula": "baseline_minus_probe",
        "direction": "positive_probe_better",
        "eligible_for_pe1": True,
        "eligible_for_final_pe2": False,
    }:
        raise MetricKernelError("gain_contract_mismatch", "gain contract changed")
    if payload.get("seed_policy") != "none":
        raise MetricKernelError(
            "randomness_contract_violation", "deterministic kernel requires seed_policy=none"
        )
    expected = config_digest(payload)
    if payload.get("artifact_digest") != expected:
        raise MetricKernelError("metric_manifest_digest_mismatch", "manifest was modified")
    return MetricKernelManifest(
        payload=dict(payload),
        artifact_digest=expected,
        probability_epsilon=1e-6,
        unit_contract=unit,
    )


def validate_metric_input(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != METRIC_INPUT_SCHEMA_VERSION:
        raise MetricKernelError("invalid_metric_input", "unsupported input schema")
    for field in ("source_dataset_digest",):
        if not _DIGEST.fullmatch(str(payload.get(field, ""))):
            raise MetricKernelError("invalid_source_digest", f"{field} must be sha256")
    parent_digests = payload.get("parent_digests")
    if not isinstance(parent_digests, list) or not parent_digests:
        raise MetricKernelError("invalid_parent_digests", "parent digests are required")
    if any(not _DIGEST.fullmatch(str(value)) for value in parent_digests):
        raise MetricKernelError("invalid_parent_digests", "parent digest must be sha256")
    if not str(payload.get("created_at", "")).strip():
        raise MetricKernelError("created_at_missing", "created_at is required")
    issues = payload.get("issues")
    if not isinstance(issues, list) or not issues:
        raise MetricKernelError("empty_metric_sequence", "issues are required")
    issue_ids: list[str] = []
    for issue in issues:
        if not isinstance(issue, Mapping):
            raise MetricKernelError("invalid_metric_input", "issue must be an object")
        issue_id = str(issue.get("issue_id", "")).strip()
        cluster_id = str(issue.get("cluster_id", "")).strip()
        if not issue_id or not cluster_id:
            raise MetricKernelError("issue_cluster_missing", "cluster identity is required")
        if issue_id != cluster_id:
            raise MetricKernelError("issue_cluster_mismatch", "cluster_id must equal issue_id")
        issue_ids.append(issue_id)
        evaluate_issue(
            issue_id=issue_id,
            cluster_id=cluster_id,
            target_vector=issue.get("target_vector", ()),
            baseline_probability_vector=issue.get(
                "baseline_probability_vector", ()
            ),
            probe_probability_vector=issue.get("probe_probability_vector", ()),
            baseline_identity=str(issue.get("baseline_identity", "")),
        )
    if len(set(issue_ids)) != len(issue_ids):
        raise MetricKernelError("duplicate_issue_id", "issue ids must be unique")
    return {
        "valid": True,
        "issue_count": len(issues),
        "descriptive_metric_artifact": True,
        "p2_gate_result": False,
        "real_data_evidence": False,
    }


def build_metric_artifact(
    input_payload: Mapping[str, Any],
    *,
    manifest: MetricKernelManifest,
    git_commit: str,
    working_tree_clean: bool,
) -> dict[str, Any]:
    validate_metric_input(input_payload)
    if not _GIT_COMMIT.fullmatch(git_commit):
        raise MetricKernelError("invalid_git_commit", "git commit must be sha1")
    if working_tree_clean is not True:
        raise MetricKernelError("dirty_worktree", "formal artifact requires clean tree")
    issues = tuple(
        evaluate_issue(
            issue_id=str(item["issue_id"]),
            cluster_id=str(item["cluster_id"]),
            target_vector=item["target_vector"],
            baseline_probability_vector=item["baseline_probability_vector"],
            probe_probability_vector=item["probe_probability_vector"],
            epsilon=manifest.probability_epsilon,
            baseline_identity=str(item["baseline_identity"]),
        )
        for item in input_payload["issues"]
    )
    aggregate = aggregate_issue_metrics(issues)
    payload: dict[str, Any] = {
        "schema_version": METRIC_ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "descriptive_metric_artifact",
        "artifact_digest": "",
        "created_at": input_payload["created_at"],
        "git_commit": git_commit,
        "working_tree_clean": True,
        "dataset_digest": input_payload["source_dataset_digest"],
        "source_dataset_digest": input_payload["source_dataset_digest"],
        "parent_digests": list(input_payload["parent_digests"]),
        "preregistration_digest": FROZEN_PREREGISTRATION_DIGEST,
        "decision_policy_digest": FROZEN_DECISION_POLICY_DIGEST,
        "config_digest": manifest.artifact_digest,
        "metric_kernel_version": manifest.metric_kernel_version,
        "metric_kernel_manifest_digest": manifest.artifact_digest,
        "seed_policy": "none",
        "unit_contract": manifest.unit_contract.to_dict(),
        "metric_identity": manifest.payload["metric_identity"],
        "baseline_identity": manifest.baseline_identity,
        "probability_epsilon": manifest.probability_epsilon,
        "issue_count": len(issues),
        "issues": [item.to_dict() for item in issues],
        "aggregate": aggregate.to_dict(),
        "joint_uniform_code_length": joint_uniform_code_length(),
        "bias_corrected_information_gain": {
            "status": "NOT_IMPLEMENTED",
            "reason": "requires synthetic calibration / bias validation contract",
            "eligible_for_final_pe2": False,
        },
        "interpretation": {
            "number_event_log_loss": "composite_proper_score",
            "joint_probability_from_marginal_product": "forbidden",
            "p2_gate_result": False,
            "real_data_evidence": False,
            "confidence_interval": "NOT_IMPLEMENTED",
        },
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity, domain="dehps.m4.metric-artifact.v1"
    )
    return payload


def validate_metric_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != METRIC_ARTIFACT_SCHEMA_VERSION:
        raise MetricKernelError("invalid_metric_artifact", "unsupported artifact schema")
    if payload.get("seed_policy") != "none":
        raise MetricKernelError(
            "randomness_contract_violation", "metric artifact must be deterministic"
        )
    validate_artifact_identity(payload, stochastic=False)
    identity = dict(payload)
    supplied = str(identity.pop("artifact_digest", ""))
    expected = canonical_digest(identity, domain="dehps.m4.metric-artifact.v1")
    if supplied != expected:
        raise MetricKernelError("metric_artifact_digest_mismatch", "artifact changed")
    aggregate = payload.get("aggregate")
    if not isinstance(aggregate, Mapping):
        raise MetricKernelError("invalid_metric_artifact", "aggregate is required")
    if aggregate.get("sample_size_for_inference") != payload.get("issue_count"):
        raise MetricKernelError(
            "issue_cluster_mismatch", "inference sample size must equal issue count"
        )
    if aggregate.get("iid_confidence_interval") is not None:
        raise MetricKernelError(
            "iid_uncertainty_forbidden", "P2.2 cannot emit an IID interval"
        )
    pe2 = payload.get("bias_corrected_information_gain")
    if not isinstance(pe2, Mapping) or pe2.get("status") != "NOT_IMPLEMENTED":
        raise MetricKernelError("pe2_contract_violation", "PE2 must remain not implemented")
    return {
        "valid": True,
        "artifact_digest": expected,
        "issue_count": payload["issue_count"],
        "descriptive_metric_artifact": True,
        "p2_gate_result": False,
        "real_data_evidence": False,
    }


def show_metric_artifact(*, digest: str, artifact_dir: Path) -> dict[str, Any]:
    if not _DIGEST.fullmatch(digest):
        raise MetricKernelError("invalid_artifact_digest", "digest must be sha256")
    path = artifact_dir / digest / "metric-artifact.json"
    if not path.exists():
        raise MetricKernelError("metric_artifact_not_found", f"missing {digest}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_metric_artifact(payload)
    return payload
