from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from dehps.research_os.information_theory.calibration.contracts import (
    EXPECTED_SCENARIOS,
)
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.identifiability import (
    IDENTIFIABILITY_PREFLIGHT_MANIFEST_DIGEST,
    REPAIR_REQUIRED_FACT,
    IdentifiabilityContractError,
    load_identifiability_preflight_manifest,
    load_superseded_run_archive,
    run_identifiability_preflight,
)
from dehps.research_os.information_theory.measurement_validation.contracts import (
    DECISION_POLICY_DIGEST,
    PREREGISTRATION_DIGEST,
    SYNTHETIC_MANIFEST_DIGEST,
)
from dehps.research_os.information_theory.measurement_validation.dataset import (
    P24_EXECUTION_ID,
)

ROOT = Path(__file__).resolve().parents[3]
PREFLIGHT_PATH = (
    ROOT
    / "configs/research-os/"
    "m4-information-theory-p2-6-identifiability-preflight-v1.json"
)
ARCHIVE_PATH = (
    ROOT
    / "configs/research-os/"
    "m4-information-theory-p2-6-superseded-run-archive-v1.json"
)


def _truth_fixture(root: Path) -> None:
    manifest = load_identifiability_preflight_manifest(PREFLIGHT_PATH)
    truth_root = (
        root
        / "runtime/research-os/mainline/tasks/"
        "m4-p2-injected-signal-calibration"
        / P24_EXECUTION_ID
        / "artifacts/truth"
    )
    mechanisms = {
        "SINGLE_NUMBER": "single_number_conditional_shift",
        "LOCAL_TEMPORAL": "local_temporal_state",
        "PAIR": "pair_conditional_signal",
        "MARGINAL_PRESERVING": "marginal_preserving_conditional_signal",
    }
    strengths = {
        "WEAK": 0.001,
        "MEDIUM_PRACTICAL": 0.01,
        "STRONG": 0.05,
    }
    for scenario_id, digest in zip(
        EXPECTED_SCENARIOS,
        manifest.truth_artifact_digests,
        strict=True,
    ):
        mechanism_key = next(
            key for key in mechanisms if scenario_id.endswith(key)
        )
        strength_key = scenario_id.removesuffix(
            f"_{mechanism_key}"
        )
        joint = strengths[strength_key]
        marginal = (
            0.0
            if mechanism_key == "MARGINAL_PRESERVING"
            else joint
        )
        payload = {
            "schema_version": "dehps-m4-p2-injected-signal-truth.v1",
            "artifact_type": "injected_signal_truth",
            "artifact_digest": digest,
            "scenario_id": scenario_id,
            "mechanism": mechanisms[mechanism_key],
            "preregistration_digest": PREREGISTRATION_DIGEST,
            "decision_policy_digest": DECISION_POLICY_DIGEST,
            "synthetic_manifest_digest": SYNTHETIC_MANIFEST_DIGEST,
            "joint_draw_information_bits_per_issue": joint,
            "composite_number_event_information_bits_per_issue": marginal,
            "eligible_for_p2_5_input": True,
        }
        path = truth_root / digest / "truth.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )


def test_frozen_preflight_and_superseded_archive_are_result_blind() -> None:
    manifest = load_identifiability_preflight_manifest(PREFLIGHT_PATH)
    archive = load_superseded_run_archive(ARCHIVE_PATH)

    assert (
        manifest.artifact_digest
        == IDENTIFIABILITY_PREFLIGHT_MANIFEST_DIGEST
    )
    assert (
        manifest.approved_repair_strategy
        == "SCHEME_A_MARGINAL_TRUTH_TO_MARGINAL_METRIC"
    )
    assert archive["checkpoint"]["checkpoint_preserved"] is True
    assert archive["checkpoint"]["artifacts_deleted"] is False
    assert (
        archive["result_blindness"][
            "partial_statistical_results_inspected"
        ]
        is False
    )
    assert archive["result_blindness"]["evidence_progress_increment"] == 0


def test_preflight_contract_mutation_fails_after_self_digest_recompute() -> None:
    payload = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
    mutated = deepcopy(payload)
    mutated["measurement_contract"]["current_metric_estimand"] = (
        "I(Y_vector; state)"
    )
    mutated["artifact_digest"] = config_digest(mutated)

    with pytest.raises(
        IdentifiabilityContractError,
        match="manifest digest changed",
    ):
        from dehps.research_os.information_theory.identifiability.contracts import (
            validate_identifiability_preflight_manifest,
        )

        validate_identifiability_preflight_manifest(mutated)


def test_joint_only_signal_fails_without_running_any_outer_fold(
    tmp_path: Path,
) -> None:
    _truth_fixture(tmp_path)
    manifest = load_identifiability_preflight_manifest(PREFLIGHT_PATH)

    first = run_identifiability_preflight(
        manifest=manifest,
        root_dir=tmp_path,
        execution_id="a" * 64,
        git_commit="b" * 40,
    )
    replay = run_identifiability_preflight(
        manifest=manifest,
        root_dir=tmp_path,
        execution_id="a" * 64,
        git_commit="b" * 40,
    )
    joint_only = [
        row
        for row in first.report["scenarios"]
        if "NOT_IDENTIFIABLE_BY_CURRENT_METRIC"
        in row["classifications"]
    ]

    assert first == replay
    assert first.decision_fact == REPAIR_REQUIRED_FACT
    assert first.report["decision"] == (
        "MEASUREMENT_CONTRACT_REPAIR_REQUIRED"
    )
    assert first.report["evidence_progress_increment"] == 0
    assert first.report["p2_6_partial_statistical_results_inspected"] is False
    assert len(joint_only) == 3
    assert all(
        row["joint_information_bits_per_issue"] > 0
        and row["composite_marginal_information_bits_per_issue"] == 0
        and row["current_metric_oracle_signal"] == "FAIL"
        for row in joint_only
    )
