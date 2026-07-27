import hashlib
import json
from copy import deepcopy
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
from dehps.research_os.models import TaskStatus


ROOT = Path(__file__).resolve().parents[3]
V101_PATH = ROOT / "configs/research-os/m4-information-theory-preregistration-v1.json"
V102_PATH = (
    ROOT
    / "configs/research-os/m4-information-theory-preregistration-v1.0.2.json"
)
POLICY_PATH = ROOT / "configs/research-os/m4-information-theory-decision-policy-v1.json"
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
V101_DIGEST = "6e03cd828378badda6995c6582d80165b0a4ee3b5899b97737bad1494fcf1ae1"
V102_DIGEST = "a8da6bf2404d3bf213ac74d331917d5308195b7c3174b002378e1bbd849f6dfa"
POLICY_DIGEST = "824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d"


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
        "m4-p1-repair-resampling-preregistration-contract"
    ]
    assert states["m4-p2-injected-signal-calibration"] is (
        TaskStatus.BLOCKED_BY_CONTRACT
    )
    assert states["m4-p2-resampling"] is TaskStatus.DEPENDENCY_WAIT
    assert states["m4-p2-false-positive-and-power-runs"] is (
        TaskStatus.DEPENDENCY_WAIT
    )
    assert (status["current_phase"], status["current_state"]) == ("M4-P1", "BLOCKED")


def test_completed_repair_restores_only_p24_ready() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    states = _resolutions(manifest)
    status = build_m4_status(manifest, snapshot=snapshot)
    assert [item.task_key for item in snapshot.ready_queue] == [
        "m4-p2-injected-signal-calibration"
    ]
    assert states["m4-p1-repair-resampling-preregistration-contract"] is (
        TaskStatus.COMPLETED
    )
    assert states["m4-p2-resampling"] is TaskStatus.DEPENDENCY_WAIT
    assert states["m4-p2-false-positive-and-power-runs"] is (
        TaskStatus.DEPENDENCY_WAIT
    )
    assert status["preregistration"] == {"status": "FROZEN", "version": "1.0.2"}
    assert status["progress"]["engineering_percent"] == 30
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
