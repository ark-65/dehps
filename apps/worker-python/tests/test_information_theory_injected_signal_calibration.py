from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.calibration import (
    CALIBRATION_RUN_MANIFEST_DIGEST,
    calibrate_scenario,
    generate_calibration_dataset,
    load_calibration_manifest,
    run_p24_calibration,
    validate_calibration_manifest,
)
from dehps.research_os.information_theory.calibration.contracts import (
    CALIBRATION_DATASET_FLAGS,
    CalibrationContractError,
    EXPECTED_SCENARIOS,
)
from dehps.research_os.information_theory.calibration.mechanisms import (
    LEGAL_COMBINATION_COUNT,
)
from dehps.research_os.information_theory.walk_forward import (
    validate_synthetic_dataset,
)
from dehps.research_os.information_theory.walk_forward.errors import (
    WalkForwardError,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = (
    ROOT
    / "configs/research-os/"
    "m4-information-theory-p2-4-calibration-run-manifest-v1.json"
)
HARNESS_PATH = (
    ROOT
    / "configs/research-os/"
    "m4-information-theory-walk-forward-harness-v1.json"
)
PARENT_RUN_DIGEST = "c" * 64
TEST_COMMIT = "a" * 40


@pytest.fixture(scope="module")
def manifest():
    return load_calibration_manifest(MANIFEST_PATH)


@pytest.fixture(scope="module")
def calibrated(manifest):
    return tuple(
        calibrate_scenario(
            scenario_id,
            manifest=manifest,
            parent_run_digest=PARENT_RUN_DIGEST,
        )
        for scenario_id in manifest.scenario_ids
    )


def _truth(item, manifest) -> dict:
    return item.truth_artifact(manifest=manifest, git_commit=TEST_COMMIT)


def _rehash_dataset(payload: dict) -> None:
    identity = dict(payload)
    identity.pop("artifact_digest", None)
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.synthetic.dataset.v1",
    )


def test_frozen_manifest_binds_all_scenarios_and_exact_contract(manifest) -> None:
    assert manifest.artifact_digest == CALIBRATION_RUN_MANIFEST_DIGEST
    assert manifest.scenario_ids == EXPECTED_SCENARIOS
    assert manifest.smoke_dataset_issue_count == 902
    assert manifest.smoke_outer_fold_count == 2
    assert manifest.absolute_bits_tolerance == 1e-10
    assert manifest.relative_tolerance == 1e-6
    assert manifest.dataset_flags == CALIBRATION_DATASET_FLAGS

    changed = copy.deepcopy(dict(manifest.payload))
    changed["calibration"]["absolute_bits_tolerance"] = 1e-6
    with pytest.raises(
        CalibrationContractError,
        match="calibration solver contract changed",
    ):
        validate_calibration_manifest(changed)


def test_all_twelve_exact_truths_and_independent_mc_audits_pass(
    manifest,
    calibrated,
) -> None:
    assert len(calibrated) == 12
    assert {item.mechanism for item in calibrated} == {
        "single_number_conditional_shift",
        "local_temporal_state",
        "pair_conditional_signal",
        "marginal_preserving_conditional_signal",
    }
    for item in calibrated:
        assert item.absolute_error <= manifest.absolute_bits_tolerance
        assert item.relative_error <= manifest.relative_tolerance
        assert item.monotonicity_status == "MONOTONE_BRACKETED"
        assert item.mc_audit["status"] == "PASS"
        assert (
            item.mc_audit["standard_error_bits_per_issue"]
            <= manifest.mc_standard_error_tolerance
        )
        assert item.distribution.joint_information_bits == pytest.approx(
            item.requested_bits,
            abs=manifest.absolute_bits_tolerance,
            rel=manifest.relative_tolerance,
        )
        assert sum(item.distribution.marginal) == pytest.approx(1.0)
        assert all(sum(row) == pytest.approx(1.0) for row in item.distribution.conditional)


def test_calibration_and_truth_identity_replay_exactly(manifest, calibrated) -> None:
    first = calibrated[4]
    replay = calibrate_scenario(
        first.scenario_id,
        manifest=manifest,
        parent_run_digest=PARENT_RUN_DIGEST,
    )

    assert replay == first
    assert _truth(replay, manifest) == _truth(first, manifest)


def test_pair_claims_report_leakage_and_is4_preserves_marginals(calibrated) -> None:
    pair_results = [
        item
        for item in calibrated
        if item.mechanism == "pair_conditional_signal"
    ]
    assert all(
        item.marginal_diagnostics["classification"]
        in {"PAIR_DOMINANT", "PAIR_CONDITIONAL_WITH_MARGINAL_LEAKAGE"}
        for item in pair_results
    )
    assert any(
        item.marginal_diagnostics["classification"]
        == "PAIR_CONDITIONAL_WITH_MARGINAL_LEAKAGE"
        for item in pair_results
    )

    is4_results = [
        item
        for item in calibrated
        if item.mechanism == "marginal_preserving_conditional_signal"
    ]
    assert all(
        item.marginal_diagnostics["marginal_preservation_tolerance_passed"]
        is True
        for item in is4_results
    )
    assert all(
        item.marginal_diagnostics[
            "max_absolute_conditional_marginal_deviation"
        ]
        == 0.0
        for item in is4_results
    )


def test_each_generator_emits_only_legal_six_of_thirty_three_issues(
    manifest,
    calibrated,
) -> None:
    medium = [
        item
        for item in calibrated
        if item.scenario_id.startswith("MEDIUM_PRACTICAL_")
    ]
    assert len(medium) == 4
    for item in medium:
        truth = _truth(item, manifest)
        dataset = generate_calibration_dataset(
            item,
            truth_artifact=truth,
            manifest=manifest,
            issue_count=64,
            parent_run_digest=PARENT_RUN_DIGEST,
        )
        assert dataset["dataset_flags"] == list(CALIBRATION_DATASET_FLAGS)
        assert dataset["eligible_for_evaluation"] is False
        for issue in dataset["issues"]:
            numbers = issue["sorted_red_numbers"]
            assert len(numbers) == len(set(numbers)) == 6
            assert numbers == sorted(numbers)
            assert all(1 <= number <= 33 for number in numbers)
            assert len(issue["target_vector"]) == 33
            assert sum(issue["target_vector"]) == 6
        assert LEGAL_COMBINATION_COUNT == 1_107_568


def test_walk_forward_accepts_only_exact_calibration_boundary(
    manifest,
    calibrated,
) -> None:
    item = calibrated[4]
    truth = _truth(item, manifest)
    payload = generate_calibration_dataset(
        item,
        truth_artifact=truth,
        manifest=manifest,
        issue_count=902,
        parent_run_digest=PARENT_RUN_DIGEST,
    )
    dataset = validate_synthetic_dataset(payload)
    assert dataset.issue_count == 902

    changed = copy.deepcopy(payload)
    changed["eligible_for_evaluation"] = True
    _rehash_dataset(changed)
    with pytest.raises(
        WalkForwardError,
        match="calibration_dataset_boundary_violation",
    ):
        validate_synthetic_dataset(changed)

    missing_truth = copy.deepcopy(payload)
    missing_truth["truth_artifact_digest"] = ""
    _rehash_dataset(missing_truth)
    with pytest.raises(
        WalkForwardError,
        match="calibration_truth_identity_missing",
    ):
        validate_synthetic_dataset(missing_truth)


def test_full_runner_uses_p23_p22_and_replays_immutably(
    tmp_path: Path,
    manifest,
) -> None:
    first = run_p24_calibration(
        manifest=manifest,
        harness_path=HARNESS_PATH,
        output_dir=tmp_path,
        execution_id="d" * 64,
        git_commit=TEST_COMMIT,
    )
    replay = run_p24_calibration(
        manifest=manifest,
        harness_path=HARNESS_PATH,
        output_dir=tmp_path,
        execution_id="d" * 64,
        git_commit=TEST_COMMIT,
    )

    assert first.calibration_artifact == replay.calibration_artifact
    assert first.completion_artifact == replay.completion_artifact
    assert first.truth_artifacts == replay.truth_artifacts
    assert first.actual_fold_count == 8
    assert len(first.truth_artifacts) == 12
    assert first.completion_artifact["status"] == "COMPLETE"
    assert all(first.completion_artifact["requirements"].values())
    assert first.calibration_artifact["evidence_created"] is False
    assert first.calibration_artifact["formal_power_executed"] is False
    assert first.calibration_artifact["formal_false_positive_executed"] is False
    assert all(path.is_file() for path in first.artifact_paths)


def test_p24_schemas_are_present_and_valid_json() -> None:
    expected = {
        "m4-p2-injected-signal-calibration-run-v1.schema.json",
        "m4-p2-injected-signal-truth-v1.schema.json",
        "m4-p2-injected-signal-completion-v1.schema.json",
    }
    schema_root = ROOT / "schemas/research-os"
    for name in expected:
        payload = json.loads((schema_root / name).read_text(encoding="utf-8"))
        assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"
