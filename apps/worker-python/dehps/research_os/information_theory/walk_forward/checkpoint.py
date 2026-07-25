from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from dehps.contracts import canonical_digest

from .contracts import (
    FROZEN_METRIC_KERNEL_DIGEST,
    FROZEN_PREREGISTRATION_DIGEST,
    PREDICTION_SCHEMA_VERSION,
    FoldIdentity,
    ProbeState,
)
from .errors import WalkForwardError


_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_KEYS = {
    "actual",
    "actual_target",
    "target",
    "target_vector",
    "red_mask",
    "sorted_red_numbers",
    "pe1",
    "brier",
    "decision",
    "loss",
}


def prediction_identity(
    *,
    dataset_digest: str,
    probe_manifest_digest: str,
    test_issue: int,
) -> str:
    return canonical_digest(
        {
            "dataset_digest": dataset_digest,
            "probe_manifest_digest": probe_manifest_digest,
            "test_issue": test_issue,
        },
        domain="dehps.m4.prediction-identity.v1",
    )


def build_prediction_checkpoint(
    *,
    fold: FoldIdentity,
    probe_state: ProbeState,
    probabilities: Sequence[float],
    probe_manifest_digest: str,
    scenario: str,
    created_at: str,
    git_commit: str,
    working_tree_clean: bool,
) -> dict[str, Any]:
    normalized = tuple(float(value) for value in probabilities)
    if (
        len(normalized) != 33
        or any(value < 0 or value > 1 for value in normalized)
        or any(value != value or value in (float("inf"), float("-inf")) for value in normalized)
    ):
        raise WalkForwardError(
            "invalid_probe_probability", "checkpoint requires 33 finite probabilities"
        )
    if not working_tree_clean:
        raise WalkForwardError(
            "dirty_worktree", "formal P2.3 smoke requires a clean worktree"
        )
    identity = prediction_identity(
        dataset_digest=fold.dataset_digest,
        probe_manifest_digest=probe_manifest_digest,
        test_issue=fold.test_issue,
    )
    payload: dict[str, Any] = {
        "schema_version": PREDICTION_SCHEMA_VERSION,
        "artifact_type": "prediction_checkpoint",
        "artifact_digest": "",
        "prediction_identity": identity,
        "fold_id": fold.fold_id,
        "fold_digest": fold.fold_digest,
        "test_issue": fold.test_issue,
        "training_range": {
            "start_issue": fold.train_start_issue,
            "end_issue": fold.train_end_issue,
        },
        "dataset_digest": fold.dataset_digest,
        "scenario": scenario,
        "feature_view_digest": fold.feature_view_digest,
        "preprocessing_digest": probe_state.preprocessing_state_digest,
        "probe_manifest_digest": probe_manifest_digest,
        "probe_state_digest": probe_state.state_digest,
        "convergence_status": probe_state.convergence_status,
        "probabilities_33": list(normalized),
        "probability_order": "red_numbers_1_to_33",
        "predicted_red_count": sum(normalized),
        "created_before_target_access": True,
        "metric_kernel_digest": FROZEN_METRIC_KERNEL_DIGEST,
        "preregistration_digest": FROZEN_PREREGISTRATION_DIGEST,
        "git_commit": git_commit,
        "working_tree_clean": True,
        "seed_policy": dict(probe_state.seed_policy),
        "created_at": created_at,
        "parent_digests": [
            fold.dataset_digest,
            fold.fold_digest,
            fold.feature_view_digest,
            fold.preprocessing_manifest_digest,
            probe_state.preprocessing_state_digest,
            probe_manifest_digest,
            probe_state.state_digest,
        ],
    }
    identity_payload = dict(payload)
    identity_payload.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity_payload, domain="dehps.m4.prediction-checkpoint.v1"
    )
    validate_prediction_checkpoint(payload)
    return payload


def validate_prediction_checkpoint(payload: Mapping[str, Any]) -> None:
    if (
        payload.get("schema_version") != PREDICTION_SCHEMA_VERSION
        or payload.get("artifact_type") != "prediction_checkpoint"
    ):
        raise WalkForwardError(
            "invalid_prediction_checkpoint", "unsupported prediction schema"
        )
    forbidden = _FORBIDDEN_KEYS.intersection(key.lower() for key in payload)
    if forbidden:
        raise WalkForwardError(
            "target_access_boundary_violation",
            f"prediction checkpoint contains forbidden fields: {sorted(forbidden)}",
        )
    if payload.get("created_before_target_access") is not True:
        raise WalkForwardError(
            "target_access_boundary_violation", "checkpoint is not blind"
        )
    probabilities = payload.get("probabilities_33")
    if not isinstance(probabilities, list) or len(probabilities) != 33:
        raise WalkForwardError(
            "invalid_probe_probability", "checkpoint probability shape changed"
        )
    supplied = str(payload.get("artifact_digest", ""))
    if not _DIGEST.fullmatch(supplied):
        raise WalkForwardError(
            "invalid_prediction_checkpoint", "artifact digest is invalid"
        )
    identity = dict(payload)
    identity.pop("artifact_digest", None)
    expected = canonical_digest(
        identity, domain="dehps.m4.prediction-checkpoint.v1"
    )
    if supplied != expected:
        raise WalkForwardError(
            "prediction_checkpoint_digest_mismatch", "checkpoint changed"
        )


def persist_prediction_checkpoint(
    checkpoint: Mapping[str, Any],
    *,
    output_dir: Path,
) -> Path:
    validate_prediction_checkpoint(checkpoint)
    digest = str(checkpoint["artifact_digest"])
    identity = str(checkpoint["prediction_identity"])
    destination = output_dir / "predictions" / digest / "prediction.json"
    identity_path = output_dir / "prediction-identities" / f"{identity}.json"
    if identity_path.exists():
        existing_identity = json.loads(identity_path.read_text(encoding="utf-8"))
        existing_digest = existing_identity.get("artifact_digest")
        if existing_digest != digest:
            raise WalkForwardError(
                "duplicate_prediction_identity",
                "formal prediction already exists for dataset/probe/test issue",
            )
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if existing != checkpoint:
            raise WalkForwardError(
                "prediction_checkpoint_digest_mismatch",
                "replay content differs under the same digest",
            )
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(checkpoint, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    identity_path.write_text(
        json.dumps(
            {
                "prediction_identity": identity,
                "artifact_digest": digest,
                "path": str(destination),
            },
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination
