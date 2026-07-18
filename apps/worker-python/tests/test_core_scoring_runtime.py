from __future__ import annotations

import itertools

import numpy as np
import pytest

from dehps.input_contracts import InputContractViolation
from dehps.models.frequency_ranker import FrequencyRankerConfig, train_frequency_stats
from dehps.optimization.walk_forward import (
    _config_weight_matrix,
    _kernel_score_rank,
    _target_scores,
    build_ranked_universe,
)
from dehps.scoring_kernel import (
    KernelRequest,
    KernelWorkspace,
    WeightMatrix,
    candidate_store_from_matrix,
    numbers_mask,
    pack_window_state,
    target_lex_id,
)
from dehps.scoring_kernel.numpy_backend import NumpyReferenceBackend
from dehps.scoring_kernel.runtime_input import default_runtime_input_compiler


def _case():
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
    configs = (
        FrequencyRankerConfig(),
        FrequencyRankerConfig(
            structural_weight=0.0,
            frequency_weight=0.45,
            omission_weight=0.35,
            previous_overlap_weight=-0.1,
            recent_neighbor_weight=0.2,
            qian_kun_pattern_weight=0.1,
        ),
    )
    target_numbers = tuple(int(value) for value in matrix.numbers[len(matrix) // 2])
    stats = train_frequency_stats(history)
    scores = _target_scores(target_numbers, stats, configs)
    return matrix, history, configs, target_numbers, stats, scores


def _legacy_result(matrix, configs, target_numbers, stats, scores):
    store = candidate_store_from_matrix(matrix)
    weights = WeightMatrix(
        np.ascontiguousarray(_config_weight_matrix(configs), dtype=np.float64)
    )
    request = KernelRequest(
        target_scores=np.ascontiguousarray(scores, dtype=np.float64),
        target_lex_id=target_lex_id(store, target_numbers),
        target_mask=numbers_mask(target_numbers),
        top_k=127,
        chunk_size=333,
        worker_count=2,
        exact_rank=True,
        red5=True,
        window_id=19,
    )
    backend = NumpyReferenceBackend()
    return backend.score_rank(
        backend.prepare(store),
        pack_window_state(stats),
        weights,
        request,
        KernelWorkspace(),
    )


def _assert_result_exact(actual, expected) -> None:
    for field in (
        "target_scores",
        "exact_ranks",
        "top_candidate_ids",
        "top_scores",
        "red5_candidate_ids",
        "red5_scores",
        "red5_ranks",
    ):
        assert np.array_equal(getattr(actual, field), getattr(expected, field))


def test_core_scoring_convergence_point_uses_verified_runtime_and_is_legacy_exact(
    monkeypatch,
) -> None:
    monkeypatch.delenv("DEHPS_SCORING_BACKEND", raising=False)
    monkeypatch.setenv("DEHPS_SCORING_CHUNK_SIZE", "333")
    compiler = default_runtime_input_compiler()
    compiler.cache.clear()
    matrix, history, configs, target_numbers, stats, scores = _case()
    legacy = _legacy_result(matrix, configs, target_numbers, stats, scores)

    migrated = _kernel_score_rank(
        matrix=matrix,
        train_history=history,
        configs=configs,
        target_numbers=target_numbers,
        target_scores=scores,
        target_draw_date=None,
        target_issue="2025051",
        top_k=127,
        workers=2,
        red5=True,
        window_id=19,
    )

    _assert_result_exact(migrated, legacy)
    assert migrated.backend == "feature_abi_numpy_reference"
    assert migrated.telemetry["verified_runtime_id"].startswith(
        "verified_runtime.v1-"
    )
    first_runtime = dict(matrix.cache_info["scoring_kernel"]["runtime_input"])
    assert first_runtime["runtime_abi_cache"]["runtime_cache_hit"] is False
    assert first_runtime["runtime_abi_cache"]["all_feature_cache_hits"] is False

    repeated = _kernel_score_rank(
        matrix=matrix,
        train_history=history,
        configs=configs,
        target_numbers=target_numbers,
        target_scores=scores,
        target_draw_date=None,
        target_issue="2025051",
        top_k=127,
        workers=1,
        red5=True,
        window_id=19,
    )

    _assert_result_exact(repeated, migrated)
    repeated_runtime = matrix.cache_info["scoring_kernel"]["runtime_input"]
    assert repeated_runtime["runtime_abi_cache"]["verified_runtime_id"] == (
        migrated.telemetry["verified_runtime_id"]
    )
    assert repeated_runtime["runtime_abi_cache"]["runtime_cache_hit"] is True
    assert repeated_runtime["runtime_abi_cache"]["all_feature_cache_hits"] is True


def test_core_scoring_numba_selection_consumes_feature_abi_runtime_exactly(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEHPS_SCORING_BACKEND", "numba_cpu")
    monkeypatch.setenv("DEHPS_SCORING_CHUNK_SIZE", "333")
    default_runtime_input_compiler().cache.clear()
    matrix, history, configs, target_numbers, stats, scores = _case()
    legacy = _legacy_result(matrix, configs, target_numbers, stats, scores)

    migrated = _kernel_score_rank(
        matrix=matrix,
        train_history=history,
        configs=configs,
        target_numbers=target_numbers,
        target_scores=scores,
        target_draw_date=None,
        target_issue="2025051",
        top_k=127,
        workers=2,
        red5=True,
        window_id=19,
    )

    _assert_result_exact(migrated, legacy)
    assert migrated.backend == "feature_abi_numba_cpu"
    assert migrated.telemetry["verified_runtime_id"] == matrix.cache_info[
        "scoring_kernel"
    ]["runtime_input"]["runtime_abi_cache"]["verified_runtime_id"]


def test_runtime_input_compiler_rejects_target_issue_leakage() -> None:
    matrix, history, _configs, _target_numbers, _stats, _scores = _case()
    store = candidate_store_from_matrix(matrix)

    with pytest.raises(InputContractViolation, match="target_issue_leakage"):
        default_runtime_input_compiler().compile_effective_history(
            history=history,
            candidate_store=store,
            tile_size=333,
            target_issue=history[-1][0],
        )
