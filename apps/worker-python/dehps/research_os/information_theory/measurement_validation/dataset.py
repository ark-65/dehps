from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.calibration.mechanisms import (
    NUMBER_MARGINAL,
    _pair_event_probability,
    _sample_is1,
    _sample_is2,
    _sample_is3,
    _sample_is4,
)
from dehps.research_os.information_theory.synthetic.contracts import (
    SyntheticRunManifest,
)
from dehps.research_os.information_theory.walk_forward.contracts import (
    DatasetIssue,
    SyntheticDataset,
)

from .contracts import (
    DECISION_POLICY_DIGEST,
    INJECTED_SIGNAL_COMPLETION_DIGEST,
    PREREGISTRATION_DIGEST,
    SYNTHETIC_MANIFEST_DIGEST,
    MeasurementValidationContractError,
)
from .schedule import AnalysisReplicate, ROOT_SEED_SET_DIGEST


P24_EXECUTION_ID = (
    "772b5063f1a3578c7e8f8a2cd9f102357828608de8fbd80c2c1fb2c82b79afa2"
)
EVALUATION_FLAGS = (
    "FORMAL_P2_6_EVALUATION",
    "POWER_EVIDENCE_ELIGIBLE",
    "FALSE_POSITIVE_EVIDENCE_ELIGIBLE",
    "NOT_CALIBRATION_DATA",
    "SYNTHETIC_ONLY",
)
NULL_TRUTH_DIGEST = (
    "126f0a19596a5f6aadb0f468861c4af022d415a7344a6c10a71076b501a470b3"
)


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MeasurementValidationContractError(
            "measurement_validation_truth_invalid",
            f"{path}: {exc}",
        ) from exc
    if not isinstance(value, dict):
        raise MeasurementValidationContractError(
            "measurement_validation_truth_invalid",
            f"{path} is not an object",
        )
    return value


def locate_truth_artifacts(
    root_dir: Path,
    *,
    required_digests: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    truth_root = (
        root_dir
        / "runtime/research-os/mainline/tasks/"
        "m4-p2-injected-signal-calibration"
        / P24_EXECUTION_ID
        / "artifacts/truth"
    )
    by_scenario: dict[str, dict[str, Any]] = {}
    located: set[str] = set()
    for digest in required_digests:
        path = truth_root / digest / "truth.json"
        payload = _load_object(path)
        if (
            payload.get("artifact_digest") != digest
            or payload.get("artifact_type") != "injected_signal_truth"
            or payload.get("preregistration_digest") != PREREGISTRATION_DIGEST
            or payload.get("decision_policy_digest") != DECISION_POLICY_DIGEST
            or payload.get("synthetic_manifest_digest") != SYNTHETIC_MANIFEST_DIGEST
            or payload.get("eligible_for_p2_5_input") is not True
        ):
            raise MeasurementValidationContractError(
                "measurement_validation_truth_invalid",
                f"truth identity changed: {digest}",
            )
        scenario_id = str(payload["scenario_id"])
        if scenario_id in by_scenario:
            raise MeasurementValidationContractError(
                "measurement_validation_truth_duplicate",
                f"duplicate truth scenario: {scenario_id}",
            )
        by_scenario[scenario_id] = payload
        located.add(digest)
    if located != set(required_digests) or len(by_scenario) != 12:
        raise MeasurementValidationContractError(
            "measurement_validation_truth_incomplete",
            "all twelve accepted P2.4 truth artifacts are required",
        )
    return by_scenario


def _issue(
    issue_index: int,
    numbers: tuple[int, ...],
) -> DatasetIssue:
    target = tuple(1 if number in numbers else 0 for number in range(1, 34))
    return DatasetIssue(
        issue_index=issue_index,
        red_mask=sum(1 << (number - 1) for number in numbers),
        sorted_red_numbers=numbers,
        target_vector=target,
    )


def generate_evaluation_dataset(
    replicate: AnalysisReplicate,
    *,
    synthetic: SyntheticRunManifest,
    truth_artifact: Mapping[str, Any] | None,
) -> SyntheticDataset:
    cell = replicate.cell
    scale = synthetic.scale(cell.scale_id)
    generator = np.random.default_rng(replicate.evaluation_dataset_seed)
    issues: list[DatasetIssue] = []
    prior_states: list[int | None] = []
    initial_state = replicate.evaluation_dataset_seed % 2
    previous_half = initial_state
    legal = np.arange(1, 34, dtype=np.int64)

    if cell.scenario_id == "NULL_UNIFORM":
        if truth_artifact is not None:
            raise MeasurementValidationContractError(
                "measurement_validation_truth_invalid",
                "NULL_UNIFORM must use the accepted P2.1 analytic truth",
            )
        truth_digest = NULL_TRUTH_DIGEST
        truth_bits = 0.0
        parameter = None
    else:
        if (
            truth_artifact is None
            or truth_artifact.get("scenario_id") != cell.scenario_id
            or truth_artifact.get("mechanism") != cell.mechanism
        ):
            raise MeasurementValidationContractError(
                "measurement_validation_truth_invalid",
                f"wrong P2.4 truth for {cell.scenario_id}",
            )
        truth_digest = str(truth_artifact["artifact_digest"])
        truth_bits = float(
            truth_artifact["joint_draw_information_bits_per_issue"]
        )
        parameter = float(truth_artifact["parameter_value"])

    for issue_index in range(1, scale.sequence_length + 1):
        state = (initial_state + issue_index - 1) % 2
        if cell.scenario_id == "NULL_UNIFORM":
            numbers = tuple(
                sorted(
                    int(value)
                    for value in generator.choice(legal, 6, replace=False)
                )
            )
            prior_states.append(None)
        elif cell.mechanism == "single_number_conditional_shift":
            assert parameter is not None
            event_probability = float(NUMBER_MARGINAL) + (
                -parameter if state == 0 else parameter
            )
            numbers = _sample_is1(
                generator,
                event_probability=event_probability,
            )
            prior_states.append(state)
        elif cell.mechanism == "local_temporal_state":
            assert parameter is not None
            available_state = previous_half
            numbers, previous_half = _sample_is2(
                generator,
                previous_half=previous_half,
                match_probability=0.5 + parameter,
            )
            prior_states.append(available_state)
        elif cell.mechanism == "pair_conditional_signal":
            assert parameter is not None
            event_probability = float(_pair_event_probability()) + (
                -parameter if state == 0 else parameter
            )
            numbers = _sample_is3(
                generator,
                event_probability=event_probability,
            )
            prior_states.append(state)
        elif cell.mechanism == "marginal_preserving_conditional_signal":
            assert parameter is not None
            numbers = _sample_is4(
                generator,
                state=state,
                parameter=parameter,
            )
            prior_states.append(state)
        else:
            raise MeasurementValidationContractError(
                "measurement_validation_scenario_invalid",
                f"unknown mechanism: {cell.mechanism}",
            )
        issues.append(_issue(issue_index, numbers))

    draw_digest = canonical_digest(
        [
            {
                "issue_index": item.issue_index,
                "sorted_red_numbers": list(item.sorted_red_numbers),
            }
            for item in issues
        ],
        domain="dehps.m4.synthetic.draws.v1",
    )
    target_digest = canonical_digest(
        [list(item.target_vector) for item in issues],
        domain="dehps.m4.synthetic.targets.v1",
    )
    state_digest = canonical_digest(
        prior_states,
        domain="dehps.m4-p2.evaluation-prior-states.v1",
    )
    seed_policy = {
        "root_seed_set_digest": ROOT_SEED_SET_DIGEST,
        "seed_domain": "M4_P2_EVALUATION_DATASET",
        "power_replicate_seed_digest": replicate.power_replicate_seed_digest,
        "evaluation_dataset_seed_digest": (
            replicate.evaluation_dataset_seed_digest
        ),
        "selection_policy": "no_best_seed",
        "wall_clock_seed": "forbidden",
        "calibration_seed_reuse": False,
    }
    seed_policy_digest = canonical_digest(
        seed_policy,
        domain="dehps.m4.synthetic.seed-policy.v1",
    )
    raw: dict[str, Any] = {
        "schema_version": "dehps-m4-information-theory-synthetic-dataset.v1",
        "artifact_type": "synthetic_dataset",
        "artifact_digest": "",
        "data_source": "synthetic_only",
        "dataset_role": "formal_P2_6_evaluation",
        "dataset_flags": list(EVALUATION_FLAGS),
        "scenario": {
            **synthetic.scenario(cell.scenario_id).to_dict(),
            "implemented": True,
        },
        "scale": scale.to_dict(),
        "truth": {
            "truth_artifact_digest": truth_digest,
            "joint_draw_information_bits_per_issue": truth_bits,
            "requested_bits_per_issue": cell.target_bits_per_issue,
            "parameter_value": parameter,
        },
        "truth_artifact_digest": truth_digest,
        "seed_policy": seed_policy,
        "seed_policy_digest": seed_policy_digest,
        "replicate_seed": replicate.evaluation_dataset_seed % (2**32),
        "issue_count": len(issues),
        "draw_digest": draw_digest,
        "target_digest": target_digest,
        "prior_state_digest": state_digest,
        "prior_state_available_strictly_before_target": True,
        "preregistration_digest": PREREGISTRATION_DIGEST,
        "decision_policy_digest": DECISION_POLICY_DIGEST,
        "config_digest": SYNTHETIC_MANIFEST_DIGEST,
        "injected_signal_completion_digest": (
            INJECTED_SIGNAL_COMPLETION_DIGEST
        ),
        "evaluation_seed_domain": "M4_P2_EVALUATION_DATASET",
        "calibration_seed_domain_used": False,
        "eligible_for_evaluation": True,
        "eligible_for_power_evidence": True,
        "eligible_for_false_positive_evidence": True,
        "eligible_for_p2_gate_evidence": True,
    }
    identity = dict(raw)
    identity.pop("artifact_digest")
    raw["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.synthetic.dataset.v1",
    )
    return SyntheticDataset(
        artifact_digest=str(raw["artifact_digest"]),
        scenario_id=cell.scenario_id,
        scale_id=cell.scale_id,
        minimum_training_length=scale.minimum_training_length,
        outer_evaluation_length=scale.outer_evaluation_length,
        seed_policy=seed_policy,
        seed_policy_digest=seed_policy_digest,
        replicate_seed=int(raw["replicate_seed"]),
        issues=tuple(issues),
        raw_payload=raw,
    )
