from __future__ import annotations

import pytest

from dehps.ranking_contract import (
    RANKING_CONTRACT_DIFFERENCE,
    SCORE_REGRESSION,
    ShadowComparisonReport,
    classify_ranking_comparison,
    normalize_ranking_contract,
    production_prediction_fingerprint,
    require_explicit_ranking_contract,
    with_effective_ranking_contract,
)


def metadata() -> dict:
    return {
        "snapshot_key": "training-next-2026080-config",
        "as_of_issue": "2026080",
        "history_fingerprint": "history-2026080",
        "config_hash": "config-1",
        "config": {"frequency_weight": 0.4},
        "scoring_contract": "dehps-scoring-strict-v1",
        "prediction_metadata": {"protocol": "static_training_best"},
        "git_commit": "abc123",
    }


def test_null_historical_contract_normalizes_to_legacy_without_changing_source() -> None:
    source = {"prediction_run_key": "old-1", "ranking_contract": None}

    normalized = with_effective_ranking_contract(source)

    assert normalized["ranking_contract"] == "legacy_score_partition"
    assert source["ranking_contract"] is None
    assert normalize_ranking_contract("") == "legacy_score_partition"


def test_new_contract_must_be_explicit_and_known() -> None:
    with pytest.raises(ValueError, match="explicitly provided"):
        require_explicit_ranking_contract(None)
    with pytest.raises(ValueError, match="unknown ranking contract"):
        require_explicit_ranking_contract("strict_v2")
    assert require_explicit_ranking_contract("strict_v1") == "strict_v1"


def test_ranking_contract_changes_new_production_fingerprint() -> None:
    strict = production_prediction_fingerprint(metadata(), ranking_contract="strict_v1")
    legacy = production_prediction_fingerprint(
        metadata(),
        ranking_contract="legacy_score_partition",
    )

    assert strict != legacy
    assert strict == production_prediction_fingerprint(metadata(), ranking_contract="strict_v1")


def test_tie_boundary_identity_change_is_not_reported_as_score_regression() -> None:
    assert classify_ranking_comparison(
        left_contract="legacy_score_partition",
        right_contract="strict_v1",
        topk_id_mismatch_count=146,
        topk_score_mismatch_count=0,
    ) == RANKING_CONTRACT_DIFFERENCE
    assert classify_ranking_comparison(
        left_contract="strict_v1",
        right_contract="strict_v1",
        topk_id_mismatch_count=0,
        topk_score_mismatch_count=1,
    ) == SCORE_REGRESSION


def test_shadow_report_carries_both_contracts_and_difference_classification() -> None:
    report = ShadowComparisonReport(
        target_issue="2026082",
        official_backend="numpy_reference",
        shadow_backend="numba_cpu",
        official_ranking_contract="legacy_score_partition",
        shadow_ranking_contract="strict_v1",
        candidate_store_version="ssq-6-of-33-v1",
        candidate_abi="candidate_abi.v1",
        candidate_digest="a" * 64,
        candidate_layout_digest="b" * 64,
        candidate_package_digest="c" * 64,
        config_fingerprint="config-1",
        target_score_diff=0.0,
        rank_diff=0,
        topk_id_mismatch_count=146,
        topk_score_mismatch_count=0,
        red5_mismatch_count=0,
        evaluation_mismatch_count=0,
        restart_recovery_result="passed",
        watchdog_result="passed",
    ).as_dict()

    assert report["difference_classification"] == "ranking-contract difference"
    assert report["official_ranking_contract"] == "legacy_score_partition"
    assert report["shadow_ranking_contract"] == "strict_v1"
    assert report["candidate_abi"] == "candidate_abi.v1"
    assert report["candidate_digest"] == "a" * 64
    assert report["candidate_layout_digest"] == "b" * 64
    assert report["candidate_package_digest"] == "c" * 64
    assert report["official_runtime_envelope"]["status"] == "unavailable"
    assert report["official_runtime_envelope"]["reason"] == (
        "legacy_official_run_without_runtime_envelope"
    )
    assert report["shadow_runtime_envelope"]["status"] == "unavailable"
