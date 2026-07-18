from __future__ import annotations

import itertools

import pytest

import dehps.forward_runtime.shadow_capture as shadow_capture_module
from dehps.forward_runtime.shadow_capture import (
    capture_forward_snapshot_shadow,
    forward_shadow_capture_enabled,
)
from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.walk_forward import (
    build_ranked_universe,
    config_hash,
    top_candidates_for_next,
)
from dehps.optimization.next_candidates import attach_forward_shadow_capture
from dehps.scoring_kernel import verify_shadow_evidence
from dehps.source_version import resolve_git_commit


def test_simultaneous_capture_binds_generated_candidates_before_persistence() -> None:
    shadow_capture_module._FORWARD_SHADOW_RUNTIME_CACHE.clear()
    combinations = list(
        itertools.islice(itertools.combinations(range(1, 34), 6), 3_000)
    )
    matrix = build_ranked_universe(
        combinations,
        use_cache=False,
        include_hard_filter_exclusions=True,
    )
    history = [
        (f"2025{index:03d}", tuple(int(value) for value in row))
        for index, row in enumerate(matrix.numbers[100:2_100:40], start=1)
    ]
    config = FrequencyRankerConfig()
    candidates = top_candidates_for_next(
        history=history,
        top_n=100,
        config=config,
        ranked_universe=matrix,
        workers=2,
    )
    metadata = {
        "line_key": "static_100",
        "snapshot_key": "fixture-snapshot",
        "next_issue": "2026082",
        "top_n": 100,
        "config_hash": config_hash(config),
        "ranking_contract": "strict_v1",
        "git_commit": resolve_git_commit(),
    }

    evidence = capture_forward_snapshot_shadow(
        metadata=metadata,
        candidates=candidates,
        history=history,
        config=config,
        ranked_universe=matrix,
        target_draw_date=None,
        worker_count=2,
    )

    assert evidence["evidence_phase"] == "scoring_capture"
    assert evidence["capture_mode"] == "simultaneous"
    assert evidence["comparison_status"] == "exact"
    assert evidence["official_backend"] == "feature_abi_numpy_reference"
    assert evidence["shadow_backend"] == "feature_abi_numba_cpu"
    assert evidence["runtime_identity_mismatch_count"] == 0
    assert evidence["verified_runtime_id"].startswith("verified_runtime.v1-")
    assert evidence["runtime_verification_digest"]
    assert evidence["feature_runtime_digest"]
    assert evidence["runtime_abi_cache"]["verified_runtime_id"] == evidence[
        "verified_runtime_id"
    ]
    assert evidence["runtime_abi_cache"]["runtime_cache_hit"] is False
    assert evidence["runtime_abi_cache"]["all_feature_cache_hits"] is False
    assert evidence["official_candidate_artifact_status"] == "matched"
    assert evidence["official_candidate_id_mismatch_count"] == 0
    assert evidence["official_candidate_score_mismatch_count"] == 0
    assert evidence["evaluation_status"] == "pending"
    assert evidence["prediction_run_key"] == "static_100:2026082:fixture-snapshot"
    assert evidence["automatic_promotion_allowed"] is False
    verify_shadow_evidence(evidence)

    repeated = capture_forward_snapshot_shadow(
        metadata=metadata,
        candidates=candidates,
        history=history,
        config=config,
        ranked_universe=matrix,
        target_draw_date=None,
        worker_count=2,
    )

    assert repeated["comparison_status"] == "exact"
    assert repeated["verified_runtime_id"] == evidence["verified_runtime_id"]
    assert repeated["official_result_digest"] == evidence["official_result_digest"]
    assert repeated["shadow_result_digest"] == evidence["shadow_result_digest"]
    assert repeated["runtime_abi_cache"]["runtime_cache_hit"] is True
    assert repeated["runtime_abi_cache"]["all_feature_cache_hits"] is True
    verify_shadow_evidence(repeated)


def test_shadow_capture_flag_is_explicit_and_fail_closed(monkeypatch) -> None:
    monkeypatch.delenv("DEHPS_FORWARD_SHADOW_CAPTURE", raising=False)
    assert forward_shadow_capture_enabled() is False
    monkeypatch.setenv("DEHPS_FORWARD_SHADOW_CAPTURE", "true")
    assert forward_shadow_capture_enabled() is True
    monkeypatch.setenv("DEHPS_FORWARD_SHADOW_CAPTURE", "sometimes")
    try:
        forward_shadow_capture_enabled()
    except ValueError as exc:
        assert "must be a boolean flag" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("invalid capture flag must fail closed")


def test_shadow_failure_is_structured_without_replacing_official_candidates(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEHPS_FORWARD_SHADOW_CAPTURE", "true")

    def fail_capture(**_kwargs):
        raise RuntimeError("shadow backend unavailable")

    monkeypatch.setattr(
        shadow_capture_module,
        "capture_forward_snapshot_shadow",
        fail_capture,
    )
    metadata = {"line_key": "static_100"}
    candidates = [(1, (1, 2, 3, 4, 5, 6), 0.5)]
    with pytest.warns(RuntimeWarning, match="shadow capture failed"):
        attach_forward_shadow_capture(
            metadata=metadata,
            candidates=candidates,
            history=[],
            config=FrequencyRankerConfig(),
            ranked_universe=object(),
            target_draw_date=None,
        )

    assert candidates == [(1, (1, 2, 3, 4, 5, 6), 0.5)]
    assert metadata["shadow_scoring_failure"]["status"] == "failed"
    assert metadata["shadow_scoring_failure"]["automatic_promotion_allowed"] is False
    assert "shadow_scoring_evidence" not in metadata
