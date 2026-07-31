import hashlib
import json
from copy import deepcopy
from fractions import Fraction
from math import comb
from pathlib import Path

import pytest

from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory import (
    InformationTheoryValidationError,
    build_m4_status,
    derive_m4_p2_seed,
    load_m4_manifest,
    manifest_with_contract_repair_pending,
    preregistration_digest,
    validate_decision_policy,
    validate_preregistration,
)
from dehps.research_os.information_theory.synthetic import (
    load_synthetic_run_manifest,
)
from dehps.research_os.models import TaskStatus


ROOT = Path(__file__).resolve().parents[3]
V101_PATH = ROOT / "configs/research-os/m4-information-theory-preregistration-v1.json"
V102_PATH = (
    ROOT
    / "configs/research-os/m4-information-theory-preregistration-v1.0.2.json"
)
V103_PATH = (
    ROOT
    / "configs/research-os/m4-information-theory-preregistration-v1.0.3.json"
)
POLICY_PATH = ROOT / "configs/research-os/m4-information-theory-decision-policy-v1.json"
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
V101_DIGEST = "6e03cd828378badda6995c6582d80165b0a4ee3b5899b97737bad1494fcf1ae1"
V102_DIGEST = "a8da6bf2404d3bf213ac74d331917d5308195b7c3174b002378e1bbd849f6dfa"
V103_DIGEST = "4fff51c58e4a46d664e414bfe4cc0d7269c8e3712734153faec548648144d0d9"
POLICY_DIGEST = "824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d"
SYNTHETIC_V101_PATH = (
    ROOT
    / "configs/research-os/m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
)
SYNTHETIC_V101_DIGEST = (
    "f84c2da3565f7eda41c3782517c78211805f57ea8f3bfd00659a93c380826a3c"
)


def _load(path: Path = V102_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _invalid(payload: dict, code: str) -> None:
    with pytest.raises(InformationTheoryValidationError) as exc_info:
        validate_preregistration(payload)
    assert exc_info.value.code == code


def _resolutions(manifest) -> dict[str, TaskStatus]:
    snapshot = ResearchOSControlPlane().resolve(manifest)
    return {item.task_key: item.status for item in snapshot.resolutions}


def test_v101_is_readable_and_byte_identical_to_accepted_blob() -> None:
    payload = _load(V101_PATH)
    assert validate_preregistration(payload)["digest"] == V101_DIGEST
    assert hashlib.sha256(V101_PATH.read_bytes()).hexdigest() == (
        "40e3dee2477fba838ee5f0f5f9edc434c68fb2623f0ddcd6a34e22a4a6111e18"
    )


def test_v101_cannot_be_modified_in_place() -> None:
    payload = _load(V101_PATH)
    payload["bootstrap_permutation"]["primary_block_size"] = 8
    _invalid(payload, "bootstrap_contract_invalid")


def test_v102_is_frozen_and_supersedes_v101() -> None:
    payload = _load()
    result = validate_preregistration(payload)
    assert result["version"] == "1.0.2"
    assert result["digest"] == payload["artifact_digest"] == V102_DIGEST
    assert payload["supersedes_digest"] == V101_DIGEST
    assert preregistration_digest(payload) == V102_DIGEST


def test_v103_is_frozen_and_supersedes_v102() -> None:
    payload = _load(V103_PATH)
    result = validate_preregistration(payload)
    assert result["version"] == "1.0.3"
    assert result["digest"] == payload["artifact_digest"] == V103_DIGEST
    assert payload["supersedes_digest"] == V102_DIGEST
    assert preregistration_digest(payload) == V103_DIGEST


@pytest.mark.parametrize(
    "path,value,code",
    [
        (
            ("calibration_tolerance", "absolute_bits_tolerance"),
            1e-6,
            "calibration_tolerance_invalid",
        ),
        (
            ("calibration_tolerance", "relative_tolerance"),
            0.1,
            "calibration_tolerance_invalid",
        ),
        (
            (
                "monte_carlo_truth_audit",
                "maximum_standard_error_bits_per_issue",
            ),
            0.01,
            "calibration_monte_carlo_contract_invalid",
        ),
        (
            ("solver_contract", "bracket_required"),
            False,
            "calibration_solver_contract_invalid",
        ),
        (
            ("requested_strength_binding",),
            "composite_number_event_information_bits_per_issue",
            "injected_signal_calibration_contract_invalid",
        ),
    ],
)
def test_v103_calibration_semantics_are_fail_closed(path, value, code: str) -> None:
    payload = _load(V103_PATH)
    target = payload["injected_signal_calibration_contract"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    _invalid(payload, code)


def test_v103_is4_weights_preserve_mass_and_number_marginals_exactly() -> None:
    payload = _load(V103_PATH)
    raw_weights = payload["injected_signal_calibration_contract"][
        "mechanism_contracts"
    ]["IS4_MARGINAL_PRESERVING_CONDITIONAL"]["orthogonal_weight_by_K"]
    weights = {
        item["K"]: Fraction(item["numerator"], item["denominator"])
        for item in raw_weights
    }
    total = comb(33, 6)
    probabilities = {
        k: Fraction(comb(16, k) * comb(17, 6 - k), total)
        for k in range(7)
    }
    assert sum(probabilities[k] * weights[k] for k in range(7)) == 0
    assert sum(
        probabilities[k] * k * weights[k] for k in range(7)
    ) == 0


def test_superseding_synthetic_manifest_binds_v103_without_execution() -> None:
    manifest = load_synthetic_run_manifest(SYNTHETIC_V101_PATH)
    calibration = manifest.payload["injected_signal_calibration_contract"]
    assert manifest.artifact_digest == SYNTHETIC_V101_DIGEST
    assert manifest.payload["preregistration_digest"] == V103_DIGEST
    assert calibration["requested_strength_binding"] == (
        "joint_draw_information_bits_per_issue"
    )
    assert calibration["formal_calibration_executed"] is False
    assert all(
        not scenario.implemented
        for scenario in manifest.scenarios
        if scenario.scenario_id != "NULL_UNIFORM"
    )


@pytest.mark.parametrize(
    "field,code",
    [
        ("resampling_semantics", "missing_resampling_semantics"),
        ("inference_semantics", "missing_inference_semantics"),
        ("seed_domains", "missing_seed_domains"),
        ("seed_domain_separation", "missing_seed_domain_separation"),
    ],
)
def test_v102_requires_every_new_schema_section(field: str, code: str) -> None:
    payload = _load()
    payload.pop(field)
    _invalid(payload, code)


@pytest.mark.parametrize(
    "section,key,value,code",
    [
        ("moving_block", "topology", "circular", "moving_block_semantics_invalid"),
        (
            "moving_block",
            "incomplete_source_tail_policy",
            "short_final_block",
            "moving_block_semantics_invalid",
        ),
        (
            "moving_block",
            "overflow_policy",
            "keep_overflow",
            "moving_block_semantics_invalid",
        ),
        (
            "stationary_bootstrap",
            "restart_probability_primary",
            0.25,
            "stationary_bootstrap_semantics_invalid",
        ),
        (
            "stationary_bootstrap",
            "topology",
            "non_circular",
            "stationary_bootstrap_semantics_invalid",
        ),
        (
            "block_permutation",
            "tail_block_policy",
            "merge_previous",
            "block_permutation_semantics_invalid",
        ),
        (
            "circular_shift",
            "direction",
            "target_backward_relative_to_prediction",
            "circular_shift_semantics_invalid",
        ),
    ],
)
def test_resampling_semantics_are_exactly_frozen(
    section: str, key: str, value, code: str
) -> None:
    payload = _load()
    payload["resampling_semantics"][section][key] = value
    _invalid(payload, code)


def test_circular_shift_zero_is_rejected() -> None:
    payload = _load()
    payload["resampling_semantics"]["circular_shift"]["frozen_shifts"].append(0)
    _invalid(payload, "circular_shift_semantics_invalid")


@pytest.mark.parametrize(
    "path,value,code",
    [
        (("plus_one_correction",), False, "inference_semantics_invalid"),
        (
            ("tie_handling", "upper_tail_comparison"),
            ">",
            "inference_tie_handling_invalid",
        ),
        (
            ("tie_handling", "lower_tail_comparison"),
            "<",
            "inference_tie_handling_invalid",
        ),
        (("quantile_method",), "linear_unspecified", "inference_semantics_invalid"),
    ],
)
def test_inference_semantics_are_exactly_frozen(path, value, code: str) -> None:
    payload = _load()
    target = payload["inference_semantics"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    _invalid(payload, code)


def test_midrank_and_empirical_cdf_fixtures_match_contract() -> None:
    null = [1.0, 2.0, 2.0, 4.0]
    observed = 2.0
    below = sum(value < observed for value in null)
    equal = sum(value == observed for value in null)
    inclusive = sum(value <= observed for value in null)
    assert (below + 0.5 * equal) / len(null) == 0.5
    assert inclusive / len(null) == 0.75


def test_plus_one_p_value_fixture_is_inclusive_and_nonzero() -> None:
    null = [1.0, 2.0, 2.0, 4.0]
    observed = 2.0
    upper = (1 + sum(value >= observed for value in null)) / (len(null) + 1)
    lower = (1 + sum(value <= observed for value in null)) / (len(null) + 1)
    assert (upper, lower, min(1.0, 2 * min(upper, lower))) == (0.8, 0.8, 1.0)
    assert upper > 0


def test_all_seed_domains_exist_and_are_unique() -> None:
    domains = _load()["seed_domains"]
    names = [
        value["seed_domain"]
        for key, value in domains.items()
        if key != "identity_fields"
    ]
    assert len(names) == len(set(names)) == 11


@pytest.mark.parametrize(
    "left,right",
    [
        ("M4_P2_CALIBRATION", "M4_P2_EVALUATION_DATASET"),
        ("M4_P2_RANDOM_FEATURE", "M4_P2_RANDOM_SCORE"),
        ("M4_P2_BOOTSTRAP", "M4_P2_ISSUE_PERMUTATION"),
        ("M4_P2_BOOTSTRAP", "M4_P2_NUMBER_PERMUTATION"),
    ],
)
def test_required_seed_domain_separation_is_frozen(left: str, right: str) -> None:
    pairs = {
        frozenset(pair)
        for pair in _load()["seed_domain_separation"]["required_disjoint_pairs"]
    }
    assert frozenset((left, right)) in pairs


def test_seed_derivation_is_stable_across_retry_resume_and_shard_change() -> None:
    identity = {
        "root_seed_set_digest": "a" * 64,
        "seed_domain": "M4_P2_POWER_REPLICATE",
        "scenario_id": "MEDIUM_PRACTICAL",
        "method_id": "power_root",
        "replicate_index": 17,
        "parent_run_digest": "b" * 64,
    }
    first = derive_m4_p2_seed(**identity)
    retry = derive_m4_p2_seed(**identity)
    resumed_on_another_shard = derive_m4_p2_seed(**identity)
    assert first == retry == resumed_on_another_shard


def test_different_domains_create_different_stream_identities() -> None:
    common = {
        "root_seed_set_digest": "a" * 64,
        "scenario_id": "S1",
        "method_id": "M1",
        "replicate_index": 1,
        "parent_run_digest": "b" * 64,
    }
    feature = derive_m4_p2_seed(seed_domain="M4_P2_RANDOM_FEATURE", **common)
    score = derive_m4_p2_seed(seed_domain="M4_P2_RANDOM_SCORE", **common)
    assert feature["identity"] != score["identity"]
    assert feature["seed_digest"] != score["seed_digest"]


def test_wall_clock_seed_policy_is_rejected() -> None:
    payload = _load()
    payload["seed_domain_separation"]["wall_clock_seed"] = "allowed"
    _invalid(payload, "seed_derivation_policy_invalid")


def test_random_feature_and_random_score_access_boundaries_are_frozen() -> None:
    domains = _load()["seed_domains"]
    assert domains["random_feature"]["target_access"] == "forbidden"
    assert domains["random_feature"]["retrain_required"] is True
    assert domains["random_score"]["target_access"] == "forbidden"
    assert domains["random_score"]["matching_source"] == (
        "probe_score_distribution_only"
    )


def test_evaluation_and_power_seed_policies_are_frozen() -> None:
    domains = _load()["seed_domains"]
    assert domains["evaluation_dataset"]["truth_parameters"] == (
        "read_only_from_P2.4_truth_artifact"
    )
    assert domains["evaluation_dataset"]["recalibration"] == "forbidden"
    assert domains["power_replicate"]["direct_reuse_by_components"] == "forbidden"
    assert "evaluation_dataset" in domains["power_replicate"]["child_streams"]


def test_contract_repair_pending_blocks_p24_and_is_unique_ready() -> None:
    final = load_m4_manifest(MANIFEST_PATH)
    pending = manifest_with_contract_repair_pending(final)
    snapshot = ResearchOSControlPlane().resolve(pending)
    states = _resolutions(pending)
    status = build_m4_status(pending, snapshot=snapshot)
    assert [item.task_key for item in snapshot.ready_queue] == [
        "m4-p1-repair-injected-signal-preregistration-contract"
    ]
    assert states["m4-p2-injected-signal-calibration"] is (
        TaskStatus.BLOCKED_BY_CONTRACT
    )
    assert states["m4-p2-resampling"] is TaskStatus.DEPENDENCY_WAIT
    assert states["m4-p2-false-positive-and-power-runs"] is (
        TaskStatus.DEPENDENCY_WAIT
    )
    assert (status["current_phase"], status["current_state"]) == ("M4-P1", "BLOCKED")


def test_completed_p25_restores_only_identifiability_preflight_ready() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    states = _resolutions(manifest)
    status = build_m4_status(manifest, snapshot=snapshot)
    assert [item.task_key for item in snapshot.ready_queue] == [
        "m4-p2-measurement-identifiability-preflight"
    ]
    assert states["m4-p1-repair-injected-signal-preregistration-contract"] is (
        TaskStatus.COMPLETED
    )
    assert states["m4-p2-injected-signal-calibration"] is TaskStatus.COMPLETED
    assert states["m4-p2-resampling"] is TaskStatus.COMPLETED
    assert states["m4-p2-measurement-identifiability-preflight"] is (
        TaskStatus.READY
    )
    assert states["m4-p2-false-positive-and-power-runs"] is (
        TaskStatus.DEPENDENCY_WAIT
    )
    assert status["preregistration"] == {"status": "FROZEN", "version": "1.0.3"}
    assert status["progress"]["engineering_percent"] == 37
    assert status["progress"]["evidence_percent"] == 0


def test_decision_policy_is_unchanged_and_does_not_embed_repaired_semantics() -> None:
    policy = _load(POLICY_PATH)
    assert validate_decision_policy(policy)["digest"] == POLICY_DIGEST
    serialized = json.dumps(policy, sort_keys=True)
    for forbidden in (
        "upper_tail_p_plus_one",
        "percentile_midrank",
        "seed_domain",
        "preregistration_digest",
    ):
        assert forbidden not in serialized


def test_scope_and_governance_remain_closed() -> None:
    preregistration = _load()
    manifest = load_m4_manifest(MANIFEST_PATH)
    status = build_m4_status(manifest)
    repair = next(
        task
        for task in manifest.tasks
        if task.task_key == "m4-p1-repair-resampling-preregistration-contract"
    )
    metric = json.loads(repair.metric_contract)
    assert metric["p2_4_execution"] == metric["p2_5_execution"] == "not_started"
    assert preregistration["phase_gates"]["synthetic_validation"] == "NOT_STARTED"
    assert preregistration["phase_gates"]["formal_real_data_analysis"] == "NOT_STARTED"
    assert status["gate_status"] == {
        "promotion_gate": "CLOSED",
        "adaptive_supervisor": "STOPPED",
        "production_action": "none",
    }
    assert status["old_training_mainline"] == "FROZEN"
