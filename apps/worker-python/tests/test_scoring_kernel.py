from __future__ import annotations

from dataclasses import replace
import itertools

import numpy as np
import pytest

import dehps.scoring_kernel.numba_backend as numba_backend_module
from dehps.models.frequency_ranker import FrequencyRankerConfig, train_frequency_stats
from dehps.input_contracts import CandidateContractViolation, CandidateUniverseManifest, candidate_rank
from dehps.optimization.walk_forward import (
    _components_for_matrix,
    _config_weight_matrix,
    _target_scores,
    build_ranked_universe,
)
from dehps.scoring_kernel import (
    STRICT_CONTRACT_VERSION,
    KernelPlanner,
    KernelRequest,
    KernelWorkspace,
    WeightMatrix,
    candidate_store_from_matrix,
    numbers_mask,
    pack_window_state,
    run_shadow_comparison,
    target_lex_id,
)
from dehps.scoring_kernel.numba_backend import NumbaCpuBackend, _score_rank_tile
from dehps.scoring_kernel.numpy_backend import NumpyReferenceBackend, component_tile


@pytest.fixture(scope="module")
def kernel_case():
    combinations = list(
        itertools.islice(itertools.combinations(range(1, 34), 6), 12_000)
    )
    matrix = build_ranked_universe(combinations, use_cache=False)
    history_numbers = [
        tuple(int(number) for number in row)
        for row in matrix.numbers[100:4_100:50]
    ]
    history = [
        (f"2025{index:03d}", numbers)
        for index, numbers in enumerate(history_numbers, start=1)
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
        FrequencyRankerConfig(
            structural_weight=0.23,
            frequency_weight=-0.17,
            omission_weight=0.31,
            stable_range_weight=0.19,
            weekday_trend_weight=0.13,
            short_hot_frequency_weight=0.11,
            long_omission_cooldown_weight=-0.07,
        ),
    )
    stats = train_frequency_stats(history)
    store = candidate_store_from_matrix(matrix)
    state = pack_window_state(stats)
    weights = WeightMatrix(np.ascontiguousarray(_config_weight_matrix(configs)))
    target_id = len(matrix) // 2
    target_numbers = tuple(int(number) for number in matrix.numbers[target_id])
    target_scores = np.ascontiguousarray(
        _target_scores(target_numbers, stats, configs), dtype=np.float64
    )
    return {
        "matrix": matrix,
        "stats": stats,
        "store": store,
        "state": state,
        "weights": weights,
        "target_id": target_id,
        "target_numbers": target_numbers,
        "target_scores": target_scores,
    }


def _strict_expected(case, *, top_k: int):
    matrix = case["matrix"]
    scores = np.round(
        _components_for_matrix(matrix, case["stats"]) @ case["weights"].values.T,
        8,
    )
    ids = np.arange(len(matrix), dtype=np.int64)
    target_scores = case["target_scores"]
    target_id = case["target_id"]
    ranks = (
        (scores > target_scores).sum(axis=0, dtype=np.int64)
        + ((scores == target_scores) & (ids[:, None] < target_id)).sum(
            axis=0, dtype=np.int64
        )
        + 1
    )
    top_ids = np.stack(
        [np.lexsort((ids, -scores[:, index]))[:top_k] for index in range(scores.shape[1])]
    )
    masks = case["store"].candidate_mask
    red5_ids = np.flatnonzero(
        np.bitwise_count(masks & numbers_mask(case["target_numbers"])) == 5
    )
    best_ids = []
    best_scores = []
    best_ranks = []
    for config_index in range(scores.shape[1]):
        order = np.lexsort((red5_ids, -scores[red5_ids, config_index]))
        best_id = int(red5_ids[int(order[0])])
        best_score = float(scores[best_id, config_index])
        best_ids.append(best_id)
        best_scores.append(best_score)
        best_ranks.append(
            int(
                (scores[:, config_index] > best_score).sum()
                + (
                    (scores[:, config_index] == best_score)
                    & (ids < best_id)
                ).sum()
                + 1
            )
        )
    return {
        "scores": scores,
        "ranks": ranks,
        "top_ids": top_ids,
        "top_scores": np.stack(
            [scores[top_ids[index], index] for index in range(scores.shape[1])]
        ),
        "red5_ids": np.array(best_ids, dtype=np.int64),
        "red5_scores": np.array(best_scores, dtype=np.float64),
        "red5_ranks": np.array(best_ranks, dtype=np.int64),
    }


def _run(case, backend, *, chunk_size: int, worker_count: int, top_k: int = 257):
    request = KernelRequest(
        target_scores=case["target_scores"],
        target_lex_id=target_lex_id(case["store"], case["target_numbers"]),
        target_mask=numbers_mask(case["target_numbers"]),
        top_k=top_k,
        chunk_size=chunk_size,
        worker_count=worker_count,
        exact_rank=True,
        red5=True,
        window_id=79,
    )
    prepared = backend.prepare(case["store"])
    return backend.score_rank(
        prepared,
        case["state"],
        case["weights"],
        request,
        KernelWorkspace(),
    )


def test_shadow_runtime_executes_numpy_and_numba_against_one_request(kernel_case):
    request = KernelRequest(
        target_scores=kernel_case["target_scores"],
        target_lex_id=target_lex_id(
            kernel_case["store"], kernel_case["target_numbers"]
        ),
        target_mask=numbers_mask(kernel_case["target_numbers"]),
        top_k=257,
        chunk_size=2_048,
        worker_count=4,
        exact_rank=True,
        red5=True,
        window_id=79,
    )

    evidence = run_shadow_comparison(
        target_issue="2026082",
        line_key="static_100",
        config_fingerprint="fixture-config",
        candidate_store=kernel_case["store"],
        window_state=kernel_case["state"],
        weights=kernel_case["weights"],
        request=request,
    )

    assert evidence["comparison_status"] == "exact"
    assert evidence["official_backend"] == "numpy_reference"
    assert evidence["shadow_backend"] == "numba_cpu"
    assert evidence["official_result_digest"] == evidence["shadow_result_digest"]
    assert evidence["automatic_promotion_allowed"] is False


def _assert_strict_result(result, expected):
    assert result.contract_version == STRICT_CONTRACT_VERSION
    assert np.array_equal(result.exact_ranks, expected["ranks"])
    assert np.array_equal(result.top_candidate_ids, expected["top_ids"])
    assert np.array_equal(result.top_scores, expected["top_scores"])
    assert np.array_equal(result.red5_candidate_ids, expected["red5_ids"])
    assert np.array_equal(result.red5_scores, expected["red5_scores"])
    assert np.array_equal(result.red5_ranks, expected["red5_ranks"])


def test_packed_components_and_scores_are_bit_exact(kernel_case):
    legacy = _components_for_matrix(kernel_case["matrix"], kernel_case["stats"])
    packed = component_tile(
        kernel_case["store"], kernel_case["state"], 0, len(kernel_case["store"])
    )
    assert legacy.dtype == np.float64
    assert np.array_equal(packed, legacy)
    assert np.array_equal(
        np.round(packed @ kernel_case["weights"].values.T, 8),
        np.round(legacy @ kernel_case["weights"].values.T, 8),
    )


@pytest.mark.parametrize("chunk_size", [113, 1_024, 65_536])
def test_numpy_reference_is_chunk_invariant_and_matches_strict_legacy(
    kernel_case, chunk_size
):
    expected = _strict_expected(kernel_case, top_k=257)
    _assert_strict_result(
        _run(
            kernel_case,
            NumpyReferenceBackend(),
            chunk_size=chunk_size,
            worker_count=1,
        ),
        expected,
    )


@pytest.mark.parametrize(
    ("chunk_size", "worker_count"),
    [(257, 1), (1_024, 2), (4_096, 4)],
)
def test_numba_is_chunk_and_worker_invariant_and_matches_reference(
    kernel_case, chunk_size, worker_count
):
    expected = _strict_expected(kernel_case, top_k=257)
    _assert_strict_result(
        _run(
            kernel_case,
            NumbaCpuBackend(),
            chunk_size=chunk_size,
            worker_count=worker_count,
        ),
        expected,
    )


@pytest.mark.parametrize("backend", [NumpyReferenceBackend(), NumbaCpuBackend()])
def test_equal_score_boundary_uses_lex_id_and_exact_red5(backend, kernel_case):
    case = dict(kernel_case)
    config_count = 2
    case["weights"] = WeightMatrix(np.zeros((config_count, 32), dtype=np.float64))
    case["target_scores"] = np.zeros(config_count, dtype=np.float64)
    result = _run(case, backend, chunk_size=333, worker_count=4, top_k=101)
    assert np.array_equal(result.exact_ranks, np.full(config_count, case["target_id"] + 1))
    assert np.array_equal(
        result.top_candidate_ids,
        np.tile(np.arange(101, dtype=np.int64), (config_count, 1)),
    )
    assert np.array_equal(result.top_scores, np.zeros((config_count, 101)))
    matching = np.flatnonzero(
        np.bitwise_count(
            case["store"].candidate_mask & numbers_mask(case["target_numbers"])
        )
        == 5
    )
    assert np.array_equal(
        result.red5_candidate_ids, np.full(config_count, int(matching[0]))
    )
    assert np.array_equal(result.red5_ranks, np.full(config_count, int(matching[0]) + 1))


def test_strict_contract_rejects_non_finite_and_wrong_dtype(kernel_case):
    with pytest.raises(ValueError, match="weights must be float64"):
        WeightMatrix(np.zeros((1, 32), dtype=np.float32))
    with pytest.raises(ValueError, match="weights must be finite"):
        WeightMatrix(np.full((1, 32), np.inf, dtype=np.float64))
    invalid = replace(
        kernel_case["store"],
        structural_score=np.full(len(kernel_case["store"]), np.nan, dtype=np.float64),
    )
    with pytest.raises(ValueError, match="structural scores must be finite"):
        invalid.validate()


def test_candidate_and_window_hot_path_arrays_are_dense(kernel_case):
    for value in vars(kernel_case["store"]).values():
        if isinstance(value, np.ndarray):
            assert not value.dtype.hasobject
            assert value.flags.c_contiguous
    for value in vars(kernel_case["state"]).values():
        if isinstance(value, np.ndarray):
            assert not value.dtype.hasobject
            assert value.flags.c_contiguous
    assert kernel_case["store"].numbers.dtype == np.uint8
    assert kernel_case["store"].candidate_mask.dtype == np.uint64
    assert kernel_case["store"].lex_code.dtype == np.uint64
    assert kernel_case["store"].candidate_abi_package is not None
    assert np.shares_memory(
        kernel_case["store"].numbers, kernel_case["matrix"].numbers
    )
    assert np.shares_memory(
        kernel_case["store"].candidate_abi_package.numbers,
        kernel_case["store"].numbers,
    )
    assert np.shares_memory(
        kernel_case["store"].candidate_abi_package.mask,
        kernel_case["store"].candidate_mask,
    )
    assert kernel_case["store"].candidate_abi_package.header.row_count == len(kernel_case["store"])
    assert int(kernel_case["store"].candidate_abi_package.lex_id[kernel_case["target_id"]]) == candidate_rank(
        kernel_case["target_numbers"],
        universe=CandidateUniverseManifest(domain_size=33, pick_count=6),
    )


def test_candidate_store_from_mmap_matrix_reuses_candidate_abi_payload_buffers(tmp_path):
    combinations = list(itertools.islice(itertools.combinations(range(1, 34), 6), 400))
    matrix = build_ranked_universe(combinations, cache_dir=tmp_path, use_cache=True)
    assert isinstance(matrix.numbers, np.memmap)

    store = candidate_store_from_matrix(matrix)

    assert store.candidate_abi_package is not None
    assert np.shares_memory(store.candidate_abi_package.numbers, matrix.numbers)
    assert np.shares_memory(store.candidate_abi_package.numbers, store.numbers)
    assert np.shares_memory(store.candidate_abi_package.mask, store.candidate_mask)
    assert matrix.cache_info["candidate_abi"]["candidate_abi"] == "candidate_abi.v1"
    assert matrix.cache_info["candidate_store_fingerprint"] == store.fingerprint


def test_kernel_prepare_rejects_candidate_abi_mismatch_without_repair(kernel_case):
    package = kernel_case["store"].candidate_abi_package
    assert package is not None
    invalid_package = replace(
        package,
        header=replace(package.header, layout_digest="0" * 64),
    )
    invalid_store = replace(kernel_case["store"], candidate_abi_package=invalid_package)

    with pytest.raises(CandidateContractViolation) as error:
        NumpyReferenceBackend().prepare(invalid_store)

    assert error.value.code == "candidate_layout_digest_mismatch"


def test_planner_defaults_to_reference_and_has_explicit_rollback(monkeypatch):
    monkeypatch.delenv("DEHPS_SCORING_BACKEND", raising=False)
    assert KernelPlanner().backend().name == "numpy_reference"
    monkeypatch.setenv("DEHPS_SCORING_BACKEND", "numba_cpu")
    assert KernelPlanner().backend().name == "numba_cpu"
    monkeypatch.setenv("DEHPS_SCORING_BACKEND", "numpy_reference")
    assert KernelPlanner().backend().name == "numpy_reference"


def test_numba_contract_disables_fastmath_and_enables_parallel():
    assert _score_rank_tile.targetoptions["parallel"] is True
    assert _score_rank_tile.targetoptions["fastmath"] is False


def test_numba_caps_requested_workers_to_runtime_capacity(monkeypatch, kernel_case):
    monkeypatch.setattr(numba_backend_module.numba_config, "NUMBA_NUM_THREADS", 2)
    result = _run(
        kernel_case,
        NumbaCpuBackend(),
        chunk_size=1_024,
        worker_count=4,
    )
    assert result.telemetry["worker_count"] == 2
    _assert_strict_result(result, _strict_expected(kernel_case, top_k=257))


def test_streaming_workspace_and_per_kernel_telemetry_are_bounded(kernel_case):
    chunk_size = 333
    workspace = KernelWorkspace()
    backend = NumpyReferenceBackend()
    request = KernelRequest(
        target_scores=kernel_case["target_scores"],
        target_lex_id=kernel_case["target_id"],
        target_mask=numbers_mask(kernel_case["target_numbers"]),
        top_k=17,
        chunk_size=chunk_size,
        worker_count=1,
        exact_rank=True,
        red5=True,
        window_id=79,
    )
    result = backend.score_rank(
        backend.prepare(kernel_case["store"]),
        kernel_case["state"],
        kernel_case["weights"],
        request,
        workspace,
    )
    assert workspace.score_buffer is not None
    assert workspace.score_buffer.shape == (
        min(chunk_size, len(kernel_case["store"])),
        kernel_case["weights"].config_count,
    )
    assert result.telemetry["score_cells"] == (
        len(kernel_case["store"]) * kernel_case["weights"].config_count * 2
    )
    required = {
        "backend",
        "contract_version",
        "ranking_contract",
        "candidate_store_version",
        "candidate_count",
        "candidate_contract",
        "candidate_abi",
        "candidate_digest",
        "candidate_layout_digest",
        "candidate_package_digest",
        "candidate_identity_id_kind",
        "window_id",
        "config_count",
        "score_cells",
        "chunk_size",
        "worker_count",
        "prepare_time",
        "feature_time",
        "kernel_time",
        "rank_time",
        "topk_merge_time",
        "topk_reducer",
        "topk_reduction_workers",
        "topk_shard_count",
        "topk_merge_levels",
        "topk_workspace_bytes_estimate",
        "red5_reducer",
        "wall_time",
        "cpu_time",
        "peak_rss",
        "cells_per_second",
        "bytes_read_estimate",
        "workspace_bytes_estimate",
    }
    assert required <= result.telemetry.keys()
    assert result.telemetry["ranking_contract"] == "strict_v1"
    assert result.telemetry["candidate_abi"] == "candidate_abi.v1"
    assert result.telemetry["candidate_package_digest"] == (
        kernel_case["store"].candidate_abi_package.package_digest
    )
    assert result.telemetry["topk_reducer"] == "small_k_tree"
    assert result.telemetry["red5_reducer"] == "small_k_tree"


def test_fixed_seed_weight_matrices_match_every_rounded_score_cell(kernel_case):
    rng = np.random.default_rng(20_260_716)
    weights = np.ascontiguousarray(rng.uniform(-0.75, 0.75, size=(8, 32)))
    target_scores = np.zeros(8, dtype=np.float64)
    target_ids = np.zeros(8, dtype=np.int64)
    reference = NumpyReferenceBackend()
    numba = NumbaCpuBackend()
    for start in range(0, len(kernel_case["store"]), 777):
        end = min(start + 777, len(kernel_case["store"]))
        reference_tile = reference._tile(
            kernel_case["store"],
            kernel_case["state"],
            weights,
            start,
            end,
            target_scores,
            target_ids,
            False,
            np.uint64(0),
            False,
            KernelWorkspace(),
        )
        numba_tile = numba._tile(
            kernel_case["store"],
            kernel_case["state"],
            weights,
            start,
            end,
            target_scores,
            target_ids,
            False,
            np.uint64(0),
            False,
            KernelWorkspace(),
        )
        assert np.array_equal(numba_tile.scores, reference_tile.scores)
