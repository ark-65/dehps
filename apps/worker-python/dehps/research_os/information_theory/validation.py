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
_V1_0_1_DIGEST = "6e03cd828378badda6995c6582d80165b0a4ee3b5899b97737bad1494fcf1ae1"
_V1_0_2_DIGEST = "a8da6bf2404d3bf213ac74d331917d5308195b7c3174b002378e1bbd849f6dfa"


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


def _require_fields(
    payload: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    code: str,
) -> None:
    for key, value in expected.items():
        if payload.get(key) != value:
            _fail(code, f"{key} is not frozen to the preregistered value")


def _validate_resampling_semantics(payload: Mapping[str, Any]) -> None:
    semantics = _mapping(payload, "resampling_semantics")
    moving = _mapping(semantics, "moving_block")
    _require_fields(
        moving,
        {
            "topology": "non_circular",
            "block_size_primary": 5,
            "block_sizes_sensitivity": [3, 5, 8, 13],
            "start_positions": "all_integers_from_0_through_N_minus_L_inclusive",
            "source_block": "issues[start:start+L]",
            "sampling": "with_replacement",
            "concatenation": "preserve_within_block_order",
            "output_length": "original_issue_count_N",
            "overflow_policy": "truncate_right",
            "incomplete_source_tail_policy": "no_short_source_block",
            "incomplete_source_tail_included_via_valid_shorter_final_start": False,
            "source_tail_may_appear_inside_a_full_valid_block": True,
            "cluster_unit": "issue",
            "failure_when": "N<L",
            "failure_code": "insufficient_issues_for_block_size",
        },
        code="moving_block_semantics_invalid",
    )
    stationary = _mapping(semantics, "stationary_bootstrap")
    _require_fields(
        stationary,
        {
            "method": "Politis-Romano",
            "expected_block_length_primary": 5,
            "restart_probability_primary": 0.2,
            "topology": "circular",
            "initial_index": "uniform_over_0_through_N_minus_1",
            "continue_probability": "1_minus_restart_probability",
            "continue_index": "(current_index+1)_mod_N",
            "restart_index": "uniform_over_0_through_N_minus_1",
            "output_length": "original_issue_count_N",
            "expected_block_lengths_sensitivity": [3, 5, 8, 13],
            "restart_probability_by_expected_length": (
                "1_divided_by_expected_block_length"
            ),
            "role": "sensitivity_only",
            "eligible_as_primary": False,
        },
        code="stationary_bootstrap_semantics_invalid",
    )
    block_permutation = _mapping(semantics, "block_permutation")
    _require_fields(
        block_permutation,
        {
            "topology": "non_circular",
            "block_size": 5,
            "full_blocks": "floor(N/L)",
            "tail_block_policy": "include_as_final_distinct_block",
            "permutation_unit": "complete_blocks_plus_optional_tail_block",
            "within_block_order": "preserved",
            "tail_merge": "forbidden",
            "tail_split": "forbidden",
            "mapping_artifact_records_tail_length": True,
            "identity_block_permutation": "forbidden",
        },
        code="block_permutation_semantics_invalid",
    )
    shift = _mapping(semantics, "circular_shift")
    _require_fields(
        shift,
        {
            "formula": "shifted_target[t]=original_target[(t+k) mod N]",
            "direction": "target_forward_relative_to_prediction",
            "topology": "circular",
            "wrap": "modulo_N",
            "minimum_shift": 1,
            "maximum_shift": "N-1",
            "shift_zero": "forbidden",
            "effective_issue_count": "N",
            "frozen_shifts": [1, 2, 3, 5, 8, 13, 21],
            "circular_shift_randomized": False,
            "all_frozen_shifts_executed": True,
            "seed_policy": "none",
        },
        code="circular_shift_semantics_invalid",
    )
    if 0 in shift.get("frozen_shifts", ()):
        _fail("circular_shift_zero_forbidden", "shift=0 is forbidden")


def _validate_inference_semantics(payload: Mapping[str, Any]) -> None:
    inference = _mapping(payload, "inference_semantics")
    _require_fields(
        inference,
        {
            "primary_tail": "upper",
            "upper_tail_p_plus_one": (
                "(1+count(T_null>=T_observed))/(R+1)"
            ),
            "lower_tail_p_plus_one": (
                "(1+count(T_null<=T_observed))/(R+1)"
            ),
            "two_sided_p_plus_one": "min(1,2*min(p_upper,p_lower))",
            "plus_one_correction": True,
            "rank_mid": "count(null<observed)+0.5*count(null==observed)",
            "empirical_cdf": "count(null<=observed)/R",
            "percentile_method": "midrank",
            "percentile_midrank": (
                "(count(null<observed)+0.5*count(null==observed))/R"
            ),
            "quantile_method": "Hyndman-Fan_type_7",
            "required_report_fields": [
                "empirical_cdf_inclusive",
                "percentile_midrank",
                "upper_tail_p_plus_one",
                "lower_tail_p_plus_one",
            ],
            "formal_seed_set_complete_required": True,
            "incomplete_replicates": "fail_closed",
            "failed_or_missing_replicates_excluded_from_count_only_after_completeness_gate": True,
            "smoke_aggregate_formal_p_value": "forbidden",
            "p_zero": "forbidden",
        },
        code="inference_semantics_invalid",
    )
    ties = _mapping(inference, "tie_handling")
    _require_fields(
        ties,
        {
            "p_value": "inclusive",
            "upper_tail_comparison": ">=",
            "lower_tail_comparison": "<=",
        },
        code="inference_tie_handling_invalid",
    )


def _validate_seed_domains(payload: Mapping[str, Any]) -> None:
    seed_domains = _mapping(payload, "seed_domains")
    if seed_domains.get("identity_fields") != [
        "seed_domain",
        "replicate_index",
        "scenario_id",
        "method_id",
        "parent_run_digest",
    ]:
        _fail("seed_identity_fields_invalid", "seed identity fields are frozen")
    keys = {
        "calibration",
        "evaluation_dataset",
        "bootstrap",
        "stationary_bootstrap",
        "issue_permutation",
        "number_permutation",
        "circular_shift",
        "random_feature",
        "random_score",
        "power_replicate",
        "shard_assignment",
    }
    if set(seed_domains) != keys | {"identity_fields"}:
        _fail("seed_domains_missing", "all and only frozen seed domains are required")
    expected_names = {
        "calibration": "M4_P2_CALIBRATION",
        "evaluation_dataset": "M4_P2_EVALUATION_DATASET",
        "bootstrap": "M4_P2_BOOTSTRAP",
        "stationary_bootstrap": "M4_P2_STATIONARY_BOOTSTRAP",
        "issue_permutation": "M4_P2_ISSUE_PERMUTATION",
        "number_permutation": "M4_P2_NUMBER_PERMUTATION",
        "circular_shift": "M4_P2_CIRCULAR_SHIFT",
        "random_feature": "M4_P2_RANDOM_FEATURE",
        "random_score": "M4_P2_RANDOM_SCORE",
        "power_replicate": "M4_P2_POWER_REPLICATE",
        "shard_assignment": "M4_P2_SHARD_ASSIGNMENT",
    }
    actual_names: list[str] = []
    for key, expected in expected_names.items():
        domain = _mapping(seed_domains, key)
        if domain.get("seed_domain") != expected:
            _fail("seed_domain_name_invalid", f"{key} seed domain changed")
        actual_names.append(expected)
    if len(actual_names) != len(set(actual_names)):
        _fail("seed_domains_not_unique", "seed domain names must be unique")

    evaluation = _mapping(seed_domains, "evaluation_dataset")
    _require_fields(
        evaluation,
        {
            "purpose": (
                "generate_independent_synthetic_evaluation_sequences_from_frozen_truth_artifacts"
            ),
            "must_not_overlap": "calibration_dataset_identity",
            "truth_parameters": "read_only_from_P2.4_truth_artifact",
            "recalibration": "forbidden",
            "required_artifact_fields": [
                "truth_artifact_digest",
                "evaluation_seed",
                "scenario_id",
                "issue_count",
            ],
        },
        code="evaluation_seed_policy_invalid",
    )
    random_feature = _mapping(seed_domains, "random_feature")
    _require_fields(
        random_feature,
        {
            "randomization_unit": "scenario_x_replicate_x_outer_fold",
            "target_access": "forbidden",
            "retrain_required": True,
            "seed_scope": "feature_generation_only",
        },
        code="random_feature_seed_policy_invalid",
    )
    random_score = _mapping(seed_domains, "random_score")
    _require_fields(
        random_score,
        {
            "randomization_unit": "scenario_x_replicate_x_issue",
            "target_access": "forbidden",
            "retrain_required": "false_unless_score_enters_model_fitting",
            "matching_source": "probe_score_distribution_only",
            "forbidden_inputs": [
                "actual_target",
                "PE1",
                "Brier",
                "hit_rank",
                "settlement_result",
            ],
        },
        code="random_score_seed_policy_invalid",
    )
    circular_shift = _mapping(seed_domains, "circular_shift")
    _require_fields(
        circular_shift,
        {"randomized": False, "seed_policy": "none"},
        code="circular_shift_seed_policy_invalid",
    )
    power = _mapping(seed_domains, "power_replicate")
    _require_fields(
        power,
        {
            "purpose": "orchestrate_complete_independent_replicate_identity",
            "direct_reuse_by_components": "forbidden",
            "child_streams": [
                "evaluation_dataset",
                "model_randomness_if_required",
                "bootstrap",
                "stationary_bootstrap",
                "issue_permutation",
                "number_permutation",
                "random_feature",
                "random_score",
            ],
        },
        code="power_seed_policy_invalid",
    )

    separation = _mapping(payload, "seed_domain_separation")
    _require_fields(
        separation,
        {
            "root_identity": "root_seed_set_digest",
            "derivation_policy": (
                "derive(root_seed_set_digest,seed_domain,scenario_id,method_id,"
                "replicate_index,parent_run_digest)"
            ),
            "domain_identity_defines_rng_stream": True,
            "raw_integer_equality_does_not_merge_streams": True,
            "domain_enters_artifact_digest": True,
            "wall_clock_seed": "forbidden",
            "retry_reuses_child_seed": True,
            "resume_reuses_child_seed": True,
            "shard_change_preserves_child_seed": True,
        },
        code="seed_derivation_policy_invalid",
    )
    expected_pairs = {
        frozenset(("M4_P2_CALIBRATION", "M4_P2_EVALUATION_DATASET")),
        frozenset(("M4_P2_CALIBRATION", "M4_P2_BOOTSTRAP")),
        frozenset(("M4_P2_CALIBRATION", "M4_P2_ISSUE_PERMUTATION")),
        frozenset(("M4_P2_CALIBRATION", "M4_P2_NUMBER_PERMUTATION")),
        frozenset(("M4_P2_CALIBRATION", "M4_P2_POWER_REPLICATE")),
        frozenset(("M4_P2_EVALUATION_DATASET", "M4_P2_POWER_REPLICATE")),
        frozenset(("M4_P2_RANDOM_FEATURE", "M4_P2_RANDOM_SCORE")),
        frozenset(("M4_P2_BOOTSTRAP", "M4_P2_ISSUE_PERMUTATION")),
        frozenset(("M4_P2_BOOTSTRAP", "M4_P2_NUMBER_PERMUTATION")),
    }
    actual_pairs = {
        frozenset(str(item) for item in pair)
        for pair in separation.get("required_disjoint_pairs", ())
        if isinstance(pair, list) and len(pair) == 2
    }
    if actual_pairs != expected_pairs:
        _fail("seed_domain_separation_invalid", "required disjoint pairs changed")


def _validate_injected_signal_calibration(
    payload: Mapping[str, Any],
) -> None:
    contract = _mapping(payload, "injected_signal_calibration_contract")
    _require_fields(
        contract,
        {
            "contract_id": "m4-p2-injected-signal-calibration-v1",
            "status": "FROZEN",
            "repair_type": "REPAIR_PREREGISTRATION_CONTRACT",
            "requested_strength_binding": (
                "joint_draw_information_bits_per_issue"
            ),
            "requested_strengths_bits_per_issue": [0.001, 0.01, 0.05],
            "calibration_dataset_flags": [
                "CALIBRATION_ONLY",
                "NOT_EVALUATION_DATA",
                "NOT_POWER_DATA",
                "NOT_FALSE_POSITIVE_DATA",
                "NOT_P2_GATE_EVIDENCE",
            ],
        },
        code="injected_signal_calibration_contract_invalid",
    )
    timing = _mapping(contract, "repair_timing")
    if any(timing.get(key) is not False for key in (
        "calibration_executed_before_freeze",
        "truth_artifacts_created_before_freeze",
        "probe_results_used",
        "power_results_used",
        "evidence_created",
    )):
        _fail(
            "result_driven_calibration_contract",
            "calibration contract must be frozen before every result",
        )
    definitions = _mapping(contract, "information_definitions")
    required_definitions = {
        "joint_draw_information_bits_per_issue",
        "composite_number_event_information_bits_per_issue",
        "pair_information_bits_per_issue",
        "conditional_kl_bits_per_issue",
        "unconditional_kl_bits_per_issue",
    }
    if set(definitions) != required_definitions:
        _fail(
            "calibration_information_definition_invalid",
            "joint, composite, pair, and KL definitions are all required",
        )
    tolerance = _mapping(contract, "calibration_tolerance")
    _require_fields(
        tolerance,
        {
            "absolute_bits_tolerance": 1e-10,
            "relative_tolerance": 1e-6,
            "pass_rule": (
                "absolute_error<=absolute_bits_tolerance_and_"
                "relative_error<=relative_tolerance"
            ),
            "zero_requested_relative_error": "not_applicable",
            "selection_timing": "frozen_before_all_calibration_output",
        },
        code="calibration_tolerance_invalid",
    )
    solver = _mapping(contract, "solver_contract")
    _require_fields(
        solver,
        {
            "method": "deterministic_bisection",
            "bracket_required": True,
            "extrapolation": "forbidden",
            "maximum_iterations": 128,
            "parameter_width_tolerance": 1e-14,
            "monotonicity_grid_points": 65,
            "monotonicity_rule": (
                "nondecreasing_with_at_least_one_strict_increase_and_"
                "target_bracketed"
            ),
            "unbracketed_failure": "REPAIR_INJECTED_SIGNAL_CALIBRATION",
        },
        code="calibration_solver_contract_invalid",
    )
    monte_carlo = _mapping(contract, "monte_carlo_truth_audit")
    _require_fields(
        monte_carlo,
        {
            "role": "independent_non_calibrating_confirmation",
            "maximum_standard_error_bits_per_issue": 0.00025,
            "agreement_standard_errors": 4,
            "agreement_rule": (
                "abs(mc_mean-exact_truth)<=4*mc_standard_error+"
                "absolute_bits_tolerance"
            ),
            "sample_schedule": [
                262144,
                524288,
                1048576,
                2097152,
                4194304,
                8388608,
            ],
            "maximum_samples": 8388608,
            "seed_domain": "M4_P2_CALIBRATION",
            "may_change_solved_parameter": False,
        },
        code="calibration_monte_carlo_contract_invalid",
    )
    invariants = _mapping(contract, "numerical_invariants")
    _require_fields(
        invariants,
        {
            "probability_normalization_tolerance": 1e-12,
            "null_limit_tolerance": 1e-15,
            "unconditional_number_marginal_tolerance": 1e-12,
            "conditional_number_marginal_tolerance_for_IS4": 1e-12,
            "expected_selected_count_tolerance": 1e-12,
            "negative_probability_tolerance": 0,
            "legal_combination_count": 1107568,
            "selected_numbers_per_issue": 6,
            "target_vector_length": 33,
        },
        code="calibration_numerical_invariants_invalid",
    )
    pair = _mapping(contract, "pair_dominance_contract")
    _require_fields(
        pair,
        {
            "maximum_single_number_information_fraction_of_pair_information": 0.1,
            "maximum_single_number_probability_shift": 0.01,
            "pass_label": "PAIR_DOMINANT",
            "fail_label": "PAIR_CONDITIONAL_WITH_MARGINAL_LEAKAGE",
            "classification_is_not_calibration_gate": True,
        },
        code="pair_dominance_contract_invalid",
    )
    mechanisms = _mapping(contract, "mechanism_contracts")
    if set(mechanisms) != {
        "IS1_SINGLE_NUMBER_CONDITIONAL_SHIFT",
        "IS2_LOCAL_TEMPORAL_STATE",
        "IS3_PAIR_CONDITIONAL",
        "IS4_MARGINAL_PRESERVING_CONDITIONAL",
    }:
        _fail(
            "calibration_mechanism_contract_invalid",
            "all and only IS1 through IS4 are required",
        )
    is2 = _mapping(mechanisms, "IS2_LOCAL_TEMPORAL_STATE")
    if (
        is2.get("available_through_issue") != "t"
        or is2.get("target_issue") != "t_plus_1"
        or is2.get("timestamp_guard_required_in_smoke") is not True
    ):
        _fail(
            "calibration_temporal_boundary_invalid",
            "IS2 must bind state t to target t+1 through the timestamp guard",
        )
    is4 = _mapping(mechanisms, "IS4_MARGINAL_PRESERVING_CONDITIONAL")
    weights = is4.get("orthogonal_weight_by_K")
    expected_weights = [
        (0, 219, 221),
        (1, -1, 1),
        (2, 1, 1),
        (3, -1, 1),
        (4, 1, 1),
        (5, -219, 221),
        (6, 1, 1),
    ]
    actual_weights = [
        (item.get("K"), item.get("numerator"), item.get("denominator"))
        for item in weights
        if isinstance(item, Mapping)
    ] if isinstance(weights, list) else []
    if actual_weights != expected_weights:
        _fail(
            "marginal_preserving_weights_invalid",
            "IS4 exact orthogonal weights are frozen",
        )
    failure_states = _mapping(contract, "failure_states")
    _require_fields(
        failure_states,
        {
            "contract": "REPAIR_PREREGISTRATION_CONTRACT",
            "generator": "REPAIR_INJECTED_SIGNAL_GENERATOR",
            "calibration": "REPAIR_INJECTED_SIGNAL_CALIBRATION",
        },
        code="calibration_failure_states_invalid",
    )


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
    version = str(payload.get("version", "")).strip()
    if not version:
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

    if version == "1.0.2":
        if payload.get("supersedes_digest") != _V1_0_1_DIGEST:
            _fail("supersedes_digest_invalid", "v1.0.2 must supersede v1.0.1")
        _validate_resampling_semantics(payload)
        _validate_inference_semantics(payload)
        _validate_seed_domains(payload)
    if version == "1.0.3":
        if payload.get("supersedes_digest") != _V1_0_2_DIGEST:
            _fail("supersedes_digest_invalid", "v1.0.3 must supersede v1.0.2")
        _validate_resampling_semantics(payload)
        _validate_inference_semantics(payload)
        _validate_seed_domains(payload)
        _validate_injected_signal_calibration(payload)

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
