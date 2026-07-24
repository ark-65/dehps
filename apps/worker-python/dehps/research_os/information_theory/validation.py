from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from dehps.input_contracts.feature_contract import (
    FEATURE_COMPONENT_MANIFEST_DIGEST,
    FEATURE_VECTOR_LENGTH,
)

from .contracts import (
    DECISION_POLICY_SCHEMA_VERSION,
    INFORMATION_THEORY_CONTRACT_VERSION,
    P2_INPUT_SCHEMA_VERSION,
    PREREGISTRATION_SCHEMA_VERSION,
    RandomizedTaskContract,
)
from .digest import decision_policy_digest, preregistration_digest
from .enums import DecisionState, PreregistrationStatus


_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class InformationTheoryValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _fail(code: str, message: str) -> None:
    raise InformationTheoryValidationError(code, message)


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        _fail(f"missing_{key}", f"{key} must be an object")
    return value


def _sequence(payload: Mapping[str, Any], key: str) -> Sequence[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        _fail(f"missing_{key}", f"{key} must be a non-empty array")
    return value


def _keys(items: Sequence[Any], key: str) -> set[str]:
    return {
        str(item.get(key))
        for item in items
        if isinstance(item, Mapping) and item.get(key) is not None
    }


def validate_decision_policy(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != DECISION_POLICY_SCHEMA_VERSION:
        _fail("decision_policy_schema_invalid", "unsupported decision policy schema")
    if not str(payload.get("version", "")).strip():
        _fail("decision_policy_version_missing", "version is required")
    rules = _mapping(payload, "rules")
    expected = {state.value for state in DecisionState}
    if set(rules) != expected:
        _fail("decision_policy_states_invalid", "all and only allowed states are required")
    priority = payload.get("priority")
    if priority != [
        DecisionState.REPAIR_MEASUREMENT_SYSTEM.value,
        DecisionState.SUPPORTED_WEAK_SIGNAL.value,
        DecisionState.PRACTICALLY_UNPREDICTABLE.value,
        DecisionState.INCONCLUSIVE_DUE_TO_POWER.value,
    ]:
        _fail("decision_policy_priority_invalid", "decision priority is not frozen")
    for state, rule in rules.items():
        if not isinstance(rule, Mapping) or not rule.get("all"):
            _fail("decision_policy_rule_invalid", f"{state} requires explicit predicates")
    expected_digest = decision_policy_digest(payload)
    supplied = payload.get("artifact_digest")
    if supplied is not None and supplied != expected_digest:
        _fail("decision_policy_digest_mismatch", "decision policy was modified")
    return {
        "valid": True,
        "version": payload["version"],
        "digest": expected_digest,
    }


def validate_preregistration(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != PREREGISTRATION_SCHEMA_VERSION:
        _fail("preregistration_schema_invalid", "unsupported preregistration schema")
    if payload.get("contract_version") != INFORMATION_THEORY_CONTRACT_VERSION:
        _fail("contract_version_invalid", "information-theory contract version is not frozen")
    try:
        status = PreregistrationStatus(str(payload.get("status")))
    except ValueError:
        _fail("preregistration_status_invalid", "unsupported lifecycle status")
    if not str(payload.get("version", "")).strip():
        _fail("preregistration_version_missing", "version is required")

    endpoint_ids = _keys(_sequence(payload, "primary_endpoints"), "endpoint_id")
    if endpoint_ids != {"PE1", "PE2"}:
        _fail("missing_primary_endpoints", "PE1 and PE2 are jointly required")
    _sequence(payload, "secondary_endpoints")

    practical = _mapping(payload, "practical_null")
    if (
        practical.get("primary_metric") != "bits_gain_per_issue"
        or practical.get("lower_bound") != -0.01
        or practical.get("upper_bound") != 0.01
        or practical.get("frozen") is not True
        or not str(practical.get("rationale", "")).strip()
    ):
        _fail("missing_practical_null", "frozen [-0.01,+0.01] bits/issue is required")

    targets = _mapping(payload, "targets")
    primary = _mapping(targets, "primary")
    if (
        primary.get("event_count_per_issue") != 33
        or primary.get("positive_count_per_issue") != 6
        or primary.get("negative_count_per_issue") != 27
        or primary.get("resampling_unit") != "issue"
    ):
        _fail("target_contract_invalid", "primary target must preserve issue clusters")

    feature_families = _sequence(payload, "feature_families")
    if _keys(feature_families, "family_id") != {
        "F0", "F1", "F2", "F3", "F4", "F5", "F6"
    }:
        _fail("feature_families_invalid", "F0-F6 are all required")
    f5 = next(
        item for item in feature_families
        if isinstance(item, Mapping) and item.get("family_id") == "F5"
    )
    if (
        f5.get("feature_count") != FEATURE_VECTOR_LENGTH
        or f5.get("feature_manifest_digest") != FEATURE_COMPONENT_MANIFEST_DIGEST
    ):
        _fail("f5_manifest_invalid", "F5 must bind the immutable 32-component Feature ABI")

    null_models = _mapping(payload, "null_models")
    if (
        null_models.get("primary") != "F0_THEORETICAL_UNIFORM"
        or null_models.get("secondary") != "F0_TRAINING_EMPIRICAL_BASE_RATE"
    ):
        _fail("null_model_contract_invalid", "primary and sensitivity nulls are frozen")

    control_ids = _keys(_sequence(payload, "negative_controls"), "control_id")
    if control_ids != {"NC1", "NC2", "NC3", "NC4", "NC5", "NC6"}:
        _fail("missing_negative_controls", "NC1-NC6 are required")
    for control in payload["negative_controls"]:
        if not isinstance(control, Mapping):
            _fail("negative_control_invalid", "control must be an object")
        try:
            RandomizedTaskContract.from_dict(control)
        except ValueError as exc:
            _fail("randomized_control_seed_policy_invalid", str(exc))

    synthetic = _mapping(payload, "synthetic_validation")
    _mapping(synthetic, "synthetic_null")
    signals = _sequence(synthetic, "injected_signals")
    strengths = sorted(
        float(item.get("target_bits_per_issue"))
        for item in signals
        if isinstance(item, Mapping)
    )
    if strengths != [0.001, 0.01, 0.05]:
        _fail("missing_synthetic_injected_signal", "weak, medium, strong signals are required")
    if set(synthetic.get("mechanisms", ())) != {
        "single_number_conditional_shift",
        "local_temporal_state",
        "pair_conditional_signal",
        "marginal_preserving_conditional_signal",
    }:
        _fail("synthetic_mechanisms_invalid", "four model-agnostic mechanisms are required")

    bootstrap = _mapping(payload, "bootstrap_permutation")
    if (
        bootstrap.get("resampling_unit") != "issue"
        or bootstrap.get("primary_block_size") != 5
        or bootstrap.get("sensitivity_block_sizes") != [3, 5, 8, 13]
    ):
        _fail("bootstrap_contract_invalid", "issue-level block policy is frozen")

    multiplicity = _mapping(payload, "multiplicity")
    required_families = {
        "PRIMARY_ENDPOINT_FAMILY",
        "FEATURE_FAMILY_COMPARISON",
        "RED_NUMBER_FAMILY",
        "PAIR_FAMILY",
        "STRUCTURAL_TARGET_FAMILY",
        "SENSITIVITY_FAMILY",
    }
    if set(multiplicity.get("families", {})) != required_families:
        _fail("missing_multiplicity_family", "all multiplicity families are required")

    power = _mapping(payload, "power_equivalence")
    if (
        power.get("alpha") != 0.05
        or power.get("target_power") != 0.8
        or power.get("injected_practical_signal_power_gate") != 0.8
    ):
        _fail("missing_power_policy", "alpha and 80% power gates are required")

    dataset = _mapping(payload, "dataset_identity")
    for key in (
        "history_dataset_digest",
        "feature_contract_digest",
        "target_contract_digest",
        "decision_policy_digest",
    ):
        if not _DIGEST.fullmatch(str(dataset.get(key, ""))):
            _fail("missing_dataset_identity", f"{key} must be a sha256 digest")
    if (
        dataset.get("start_issue") != "2003001"
        or dataset.get("end_issue") != "2026084"
        or dataset.get("issue_count") != 3481
    ):
        _fail("dataset_range_invalid", "canonical historical range is frozen")
    if not str(dataset.get("draw_schema_version", "")).strip():
        _fail("missing_dataset_identity", "draw_schema_version is required")

    walk_forward = _mapping(payload, "walk_forward")
    if (
        walk_forward.get("minimum_training_issues") != 900
        or walk_forward.get("outer_mode") != "expanding_window"
        or walk_forward.get("outer_test_unit") != "one_issue"
        or walk_forward.get("test_horizon") != 1
    ):
        _fail("walk_forward_contract_invalid", "outer protocol is frozen")
    if set(walk_forward.get("train_only_fit_objects", ())) != {
        "scaling", "binning", "feature_selection", "missing_handling",
        "hyperparameters", "calibration", "estimator_smoothing", "base_rates",
    }:
        _fail("leakage_barrier_invalid", "all fit objects must remain inside training")

    models = _mapping(payload, "probe_models")
    if models.get("primary") != "REGULARIZED_LOGISTIC_REGRESSION":
        _fail("primary_probe_invalid", "primary probe is frozen")
    if set(models.get("allowed", ())) != {
        "EMPIRICAL_BASELINE",
        "REGULARIZED_LOGISTIC_REGRESSION",
        "NAIVE_BAYES",
        "SHALLOW_CALIBRATED_TREE",
    }:
        _fail("probe_allowlist_invalid", "probe allowlist is frozen")

    decision = _mapping(payload, "decision_policy")
    if not _DIGEST.fullmatch(str(decision.get("digest", ""))):
        _fail("missing_decision_policy", "decision policy digest is required")
    forward = _mapping(payload, "forward_evidence")
    if (
        forward.get("retroactively_ineligible_issues") != ["2026085"]
        or forward.get("production_action") != "none"
    ):
        _fail("forward_identity_invalid", "2026085 must stay retroactively ineligible")

    seed_policy = _mapping(payload, "seed_policy")
    if (
        seed_policy.get("deterministic") != "none"
        or seed_policy.get("selection_policy") != "no_best_seed"
    ):
        _fail("seed_policy_invalid", "existing SeedPolicy discipline is required")

    expected_digest = preregistration_digest(payload)
    supplied = payload.get("artifact_digest")
    if status in {PreregistrationStatus.FROZEN, PreregistrationStatus.SUPERSEDED}:
        if supplied != expected_digest:
            _fail("frozen_preregistration_modified", "frozen content digest mismatch")
        if payload.get("working_tree_clean") is not True:
            _fail("frozen_preregistration_dirty", "frozen artifact must record clean tree")
    elif supplied is not None:
        _fail("draft_preregistration_has_digest", "only frozen content has artifact_digest")

    if status is PreregistrationStatus.SUPERSEDED and not _DIGEST.fullmatch(
        str(payload.get("superseded_by_digest", ""))
    ):
        _fail("supersede_link_missing", "superseded artifact needs successor digest")
    if payload.get("supersedes_digest") is not None and not _DIGEST.fullmatch(
        str(payload["supersedes_digest"])
    ):
        _fail("supersedes_digest_invalid", "supersedes_digest must be sha256")
    if payload.get("supersedes_digest") is not None and payload.get("version") == "1.0.0":
        _fail(
            "supersede_version_not_advanced",
            "a superseding preregistration must use a new semantic version",
        )

    return {
        "valid": True,
        "status": status.value,
        "version": payload["version"],
        "digest": expected_digest,
        "contract_version": payload["contract_version"],
    }


def validate_p2_input_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != P2_INPUT_SCHEMA_VERSION:
        _fail("p2_input_schema_invalid", "unsupported P2 input schema")
    for field in ("preregistration_digest", "decision_policy_digest"):
        if not _DIGEST.fullmatch(str(payload.get(field, ""))):
            _fail("p2_input_digest_missing", f"{field} is required")
    if payload.get("preregistration_status") != "FROZEN":
        _fail("phase_gate_not_satisfied", "P2 requires a frozen preregistration")
    if payload.get("formal_real_data_analysis") != "NOT_STARTED":
        _fail("p2_input_real_data_state_invalid", "real-data analysis must not have started")
    if payload.get("synthetic_validation") != "NOT_STARTED":
        _fail("p2_input_synthetic_state_invalid", "synthetic validation must not have started")
    if payload.get("next_task") != "m4-p2-synthetic-measurement-validation":
        _fail("p2_input_next_task_invalid", "only P2 may become ready")
    return {"valid": True, "status": "VALID"}
