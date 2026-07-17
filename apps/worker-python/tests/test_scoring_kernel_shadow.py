from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from dehps.ranking_contract import STRICT_RANKING_CONTRACT
from dehps.scoring_kernel import (
    SHADOW_PROTOCOL_VERSION,
    KernelResult,
    ShadowEvidenceViolation,
    ShadowOperationalEvidence,
    compare_kernel_results,
    shadow_promotion_readiness,
    verify_shadow_evidence,
    write_shadow_artifact,
)


def kernel_result(backend: str, *, score_delta: float = 0.0) -> KernelResult:
    candidate_identity = {
        "candidate_contract": "candidate.v1.0.0",
        "candidate_abi": "candidate_abi.v1",
        "candidate_digest": "a" * 64,
        "candidate_layout_digest": "b" * 64,
        "candidate_package_digest": "c" * 64,
        "candidate_abi_verification_id": "verified_candidate.v1-1234567890abcdef",
    }
    top_scores = np.ascontiguousarray([[0.9 + score_delta, 0.8]], dtype=np.float64)
    return KernelResult(
        backend=backend,
        contract_version="dehps-scoring-strict-v1",
        target_scores=np.ascontiguousarray([0.25], dtype=np.float64),
        exact_ranks=np.ascontiguousarray([42], dtype=np.int64),
        top_candidate_ids=np.ascontiguousarray([[3, 8]], dtype=np.int64),
        top_scores=top_scores,
        red5_candidate_ids=np.ascontiguousarray([11], dtype=np.int64),
        red5_scores=np.ascontiguousarray([0.7], dtype=np.float64),
        red5_ranks=np.ascontiguousarray([100], dtype=np.int64),
        telemetry={
            "ranking_contract": STRICT_RANKING_CONTRACT,
            **candidate_identity,
        },
    )


def exact_evidence(
    issue: str = "2026082",
    line_key: str = "static_100",
    *,
    operational: ShadowOperationalEvidence | None = None,
) -> dict:
    return compare_kernel_results(
        target_issue=issue,
        line_key=line_key,
        config_fingerprint="config-1",
        candidate_store_version="candidate-store.v1",
        official=kernel_result("numpy_reference"),
        shadow=kernel_result("numba_cpu"),
        operational=operational,
    )


def passed_operational_evidence() -> ShadowOperationalEvidence:
    return ShadowOperationalEvidence(
        evaluation_status="passed",
        evaluation_mismatch_count=0,
        restart_recovery_result="passed",
        watchdog_result="passed",
    )


def test_exact_comparison_is_sealed_and_has_no_promotion_authority() -> None:
    evidence = exact_evidence()

    verify_shadow_evidence(evidence)
    assert evidence["protocol"] == SHADOW_PROTOCOL_VERSION
    assert evidence["comparison_status"] == "exact"
    assert evidence["comparison_passed"] is True
    assert evidence["official_result_digest"] == evidence["shadow_result_digest"]
    assert evidence["target_score_mismatch_count"] == 0
    assert evidence["rank_mismatch_count"] == 0
    assert evidence["topk_id_mismatch_count"] == 0
    assert evidence["topk_score_mismatch_count"] == 0
    assert evidence["red5_mismatch_count"] == 0
    assert evidence["candidate_identity_mismatch_count"] == 0
    assert evidence["runtime_envelope_mismatch_count"] == 0
    assert evidence["ranking_contract_mismatch_count"] == 0
    assert evidence["evaluation_status"] == "pending"
    assert evidence["automatic_promotion_allowed"] is False


def test_score_difference_is_preserved_as_mismatch_evidence() -> None:
    evidence = compare_kernel_results(
        target_issue="2026082",
        line_key="static_100",
        config_fingerprint="config-1",
        candidate_store_version="candidate-store.v1",
        official=kernel_result("numpy_reference"),
        shadow=kernel_result("numba_cpu", score_delta=0.00000001),
    )

    assert evidence["comparison_status"] == "mismatch"
    assert evidence["topk_score_mismatch_count"] == 1
    assert evidence["official_result_digest"] != evidence["shadow_result_digest"]
    assert evidence["automatic_promotion_allowed"] is False


def test_comparison_rejects_missing_candidate_identity_and_shape_drift() -> None:
    missing = kernel_result("numba_cpu")
    del missing.telemetry["candidate_package_digest"]
    with pytest.raises(ShadowEvidenceViolation) as identity_error:
        compare_kernel_results(
            target_issue="2026082",
            line_key="static_100",
            config_fingerprint="config-1",
            candidate_store_version="candidate-store.v1",
            official=kernel_result("numpy_reference"),
            shadow=missing,
        )
    assert identity_error.value.code == "shadow_candidate_identity_missing"

    wrong_shape = replace(
        kernel_result("numba_cpu"),
        top_scores=np.ascontiguousarray([[0.9]], dtype=np.float64),
    )
    with pytest.raises(ShadowEvidenceViolation) as shape_error:
        compare_kernel_results(
            target_issue="2026082",
            line_key="static_100",
            config_fingerprint="config-1",
            candidate_store_version="candidate-store.v1",
            official=kernel_result("numpy_reference"),
            shadow=wrong_shape,
        )
    assert shape_error.value.code == "shadow_result_shape_mismatch"


def test_artifact_write_is_digest_checked_and_append_only_by_identity(tmp_path) -> None:
    evidence = exact_evidence()
    first = write_shadow_artifact(tmp_path, evidence)
    second = write_shadow_artifact(tmp_path, evidence)

    assert first == second
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
    tampered = deepcopy(evidence)
    tampered["topk_id_mismatch_count"] = 1
    with pytest.raises(ShadowEvidenceViolation) as error:
        write_shadow_artifact(tmp_path, tampered)
    assert error.value.code == "shadow_comparison_digest_mismatch"

    first.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ShadowEvidenceViolation) as collision:
        write_shadow_artifact(tmp_path, evidence)
    assert collision.value.code == "shadow_artifact_identity_collision"


def test_three_issue_gate_requires_every_line_and_completed_operations() -> None:
    rows = [
        exact_evidence(issue, line, operational=passed_operational_evidence())
        for issue in ("2026082", "2026083", "2026084")
        for line in ("static_100", "dynamic_kdj", "dynamic_kdj_near")
    ]

    gate = shadow_promotion_readiness(rows)

    assert gate["evidence_sufficient"] is True
    assert gate["selected_issues"] == ["2026082", "2026083", "2026084"]
    assert gate["issues_are_consecutive"] is True
    assert gate["status"] == "ready_for_independent_approval"
    assert gate["automatic_promotion_allowed"] is False

    pending = rows.copy()
    pending[-1] = exact_evidence("2026084", "dynamic_kdj_near")
    pending_gate = shadow_promotion_readiness(pending)
    assert pending_gate["evidence_sufficient"] is False
    assert "dynamic_kdj_near:evaluation" in pending_gate["issue_results"][-1]["failures"]


def test_gate_rejects_nonconsecutive_duplicate_or_tampered_evidence() -> None:
    rows = [
        exact_evidence(issue, line, operational=passed_operational_evidence())
        for issue in ("2026082", "2026084", "2026085")
        for line in ("static_100", "dynamic_kdj", "dynamic_kdj_near")
    ]
    assert shadow_promotion_readiness(rows)["evidence_sufficient"] is False

    duplicated = rows + [rows[-1]]
    duplicate_gate = shadow_promotion_readiness(duplicated)
    assert duplicate_gate["evidence_sufficient"] is False
    assert duplicate_gate["duplicate_evidence_keys"] == ["2026085:dynamic_kdj_near"]

    extra_line = exact_evidence(
        "2026086",
        "forward_challenger",
        operational=passed_operational_evidence(),
    )
    ignored_gate = shadow_promotion_readiness(rows + [extra_line])
    assert ignored_gate["ignored_evidence_keys"] == ["2026086:forward_challenger"]

    tampered = deepcopy(rows)
    tampered[0]["comparison_status"] = "mismatch"
    tampered_gate = shadow_promotion_readiness(tampered)
    assert "static_100:invalid_evidence" in tampered_gate["issue_results"][0]["failures"]
