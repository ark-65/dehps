from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from dehps.contracts import canonical_digest

from .contracts import (
    FROZEN_DECISION_POLICY_DIGEST,
    FROZEN_PREREGISTRATION_DIGEST,
    DatasetIssue,
    SyntheticDataset,
    TrainingDatasetView,
)
from .errors import WalkForwardError


SYNTHETIC_DATASET_SCHEMA = "dehps-m4-information-theory-synthetic-dataset.v1"
CALIBRATION_PREREGISTRATION_DIGEST = (
    "4fff51c58e4a46d664e414bfe4cc0d7269c8e3712734153faec548648144d0d9"
)
CALIBRATION_DATASET_FLAGS = [
    "CALIBRATION_ONLY",
    "NOT_EVALUATION_DATA",
    "NOT_POWER_DATA",
    "NOT_FALSE_POSITIVE_DATA",
    "NOT_P2_GATE_EVIDENCE",
]


def load_synthetic_dataset(path: Path) -> SyntheticDataset:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WalkForwardError("invalid_synthetic_dataset", str(exc)) from exc
    if not isinstance(payload, Mapping):
        raise WalkForwardError("invalid_synthetic_dataset", "dataset must be an object")
    return validate_synthetic_dataset(payload)


def validate_synthetic_dataset(payload: Mapping[str, Any]) -> SyntheticDataset:
    if (
        payload.get("schema_version") != SYNTHETIC_DATASET_SCHEMA
        or payload.get("artifact_type") != "synthetic_dataset"
        or payload.get("data_source") != "synthetic_only"
        or payload.get("real_dataset_reference") is not None
    ):
        raise WalkForwardError(
            "non_synthetic_dataset_forbidden_in_p2",
            "P2.3 accepts only P2.1 synthetic dataset artifacts",
        )
    identity = dict(payload)
    supplied_digest = str(identity.pop("artifact_digest", ""))
    expected_digest = canonical_digest(
        identity, domain="dehps.m4.synthetic.dataset.v1"
    )
    if supplied_digest != expected_digest:
        raise WalkForwardError(
            "dataset_digest_mismatch", "synthetic dataset artifact changed"
        )
    preregistration_digest = payload.get("preregistration_digest")
    if preregistration_digest not in {
        FROZEN_PREREGISTRATION_DIGEST,
        CALIBRATION_PREREGISTRATION_DIGEST,
    }:
        raise WalkForwardError(
            "preregistration_digest_mismatch", "dataset preregistration changed"
        )
    if preregistration_digest == CALIBRATION_PREREGISTRATION_DIGEST:
        if (
            payload.get("dataset_role") != "calibration_smoke_only"
            or payload.get("dataset_flags") != CALIBRATION_DATASET_FLAGS
            or payload.get("calibration_seed_domain") != "M4_P2_CALIBRATION"
            or payload.get("evaluation_seed_domain_used") is not False
            or payload.get("eligible_for_evaluation") is not False
            or payload.get("eligible_for_power_evidence") is not False
            or payload.get("eligible_for_false_positive_evidence") is not False
            or payload.get("eligible_for_p2_gate_evidence") is not False
        ):
            raise WalkForwardError(
                "calibration_dataset_boundary_violation",
                "P2.4 calibration dataset flags or seed domain changed",
            )
        truth_digest = str(payload.get("truth_artifact_digest", ""))
        if len(truth_digest) != 64:
            raise WalkForwardError(
                "calibration_truth_identity_missing",
                "P2.4 calibration dataset requires frozen truth identity",
            )
    if payload.get("decision_policy_digest") != FROZEN_DECISION_POLICY_DIGEST:
        raise WalkForwardError(
            "decision_policy_digest_mismatch", "dataset decision policy changed"
        )
    scenario = payload.get("scenario")
    scale = payload.get("scale")
    seed_policy = payload.get("seed_policy")
    issues_payload = payload.get("issues")
    if not isinstance(scenario, Mapping) or scenario.get("data_source") != "synthetic_only":
        raise WalkForwardError(
            "non_synthetic_dataset_forbidden_in_p2", "scenario must be synthetic"
        )
    if not isinstance(scale, Mapping):
        raise WalkForwardError("invalid_synthetic_dataset", "scale is required")
    if not isinstance(seed_policy, Mapping) or not seed_policy:
        raise WalkForwardError("seed_policy_missing", "complete SeedPolicy is required")
    if not isinstance(issues_payload, list) or not issues_payload:
        raise WalkForwardError("invalid_synthetic_dataset", "issues are required")
    issues: list[DatasetIssue] = []
    expected_indexes = list(range(1, len(issues_payload) + 1))
    actual_indexes = [item.get("issue_index") for item in issues_payload if isinstance(item, Mapping)]
    if actual_indexes != expected_indexes:
        raise WalkForwardError(
            "non_chronological_dataset", "issue indexes must be unique and ordered"
        )
    for raw in issues_payload:
        if not isinstance(raw, Mapping):
            raise WalkForwardError("invalid_synthetic_dataset", "issue must be an object")
        numbers = tuple(raw.get("sorted_red_numbers", ()))
        target = tuple(raw.get("target_vector", ()))
        if (
            len(numbers) != 6
            or tuple(sorted(set(numbers))) != numbers
            or any(not isinstance(number, int) or number < 1 or number > 33 for number in numbers)
            or len(target) != 33
            or any(value not in (0, 1) for value in target)
            or sum(target) != 6
        ):
            raise WalkForwardError(
                "invalid_six_red_target", "each issue must encode legal six-of-33 reds"
            )
        expected_target = tuple(
            1 if number in numbers else 0 for number in range(1, 34)
        )
        expected_mask = sum(1 << (number - 1) for number in numbers)
        if target != expected_target or raw.get("red_mask") != expected_mask:
            raise WalkForwardError(
                "red_mask_target_mismatch", "red mask and target disagree"
            )
        issues.append(
            DatasetIssue(
                issue_index=int(raw["issue_index"]),
                red_mask=int(raw["red_mask"]),
                sorted_red_numbers=tuple(int(value) for value in numbers),
                target_vector=tuple(int(value) for value in target),
            )
        )
    expected_draw_digest = canonical_digest(
        [
            {
                "issue_index": item.issue_index,
                "sorted_red_numbers": list(item.sorted_red_numbers),
            }
            for item in issues
        ],
        domain="dehps.m4.synthetic.draws.v1",
    )
    expected_target_digest = canonical_digest(
        [list(item.target_vector) for item in issues],
        domain="dehps.m4.synthetic.targets.v1",
    )
    if (
        payload.get("draw_digest") != expected_draw_digest
        or payload.get("target_digest") != expected_target_digest
    ):
        raise WalkForwardError(
            "dataset_digest_mismatch", "draw or target digest changed"
        )
    expected_seed_policy_digest = canonical_digest(
        dict(seed_policy), domain="dehps.m4.synthetic.seed-policy.v1"
    )
    if payload.get("seed_policy_digest") != expected_seed_policy_digest:
        raise WalkForwardError(
            "seed_policy_digest_mismatch", "dataset SeedPolicy changed"
        )
    if int(payload.get("issue_count", -1)) != len(issues):
        raise WalkForwardError("dataset_issue_count_mismatch", "issue count changed")
    minimum = int(scale.get("minimum_training_length", 0))
    outer = int(scale.get("outer_evaluation_length", -1))
    if minimum < 1 or len(issues) - minimum != outer:
        raise WalkForwardError(
            "outer_scale_contract_mismatch", "scale lengths are inconsistent"
        )
    return SyntheticDataset(
        artifact_digest=supplied_digest,
        scenario_id=str(scenario.get("scenario_id", "")),
        scale_id=str(scale.get("scale_id", "")),
        minimum_training_length=minimum,
        outer_evaluation_length=outer,
        seed_policy=dict(seed_policy),
        seed_policy_digest=str(payload.get("seed_policy_digest", "")),
        replicate_seed=int(payload.get("replicate_seed")),
        issues=tuple(issues),
        raw_payload=dict(payload),
    )


def reveal_target(
    dataset: SyntheticDataset,
    *,
    test_issue: int,
    prediction_checkpoint: Mapping[str, Any],
) -> tuple[int, ...]:
    if prediction_checkpoint.get("created_before_target_access") is not True:
        raise WalkForwardError(
            "target_access_boundary_violation", "checkpoint was not blind"
        )
    if prediction_checkpoint.get("dataset_digest") != dataset.artifact_digest:
        raise WalkForwardError(
            "dataset_mutation_detected", "dataset changed after prediction"
        )
    if prediction_checkpoint.get("test_issue") != test_issue:
        raise WalkForwardError(
            "prediction_issue_mismatch", "checkpoint and reveal issue differ"
        )
    return dataset.issue(test_issue).target_vector


def restrict_to_training_history(
    dataset: SyntheticDataset,
    *,
    available_through_issue: int,
) -> TrainingDatasetView:
    if available_through_issue < 1 or available_through_issue >= dataset.issue_count:
        raise WalkForwardError(
            "target_access_boundary_violation",
            "training view must stop before at least one test issue",
        )
    return TrainingDatasetView(
        source_dataset_digest=dataset.artifact_digest,
        scenario_id=dataset.scenario_id,
        scale_id=dataset.scale_id,
        minimum_training_length=dataset.minimum_training_length,
        seed_policy=dict(dataset.seed_policy),
        seed_policy_digest=dataset.seed_policy_digest,
        replicate_seed=dataset.replicate_seed,
        issues=dataset.issues[:available_through_issue],
        available_through_issue=available_through_issue,
    )
