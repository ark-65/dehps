from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, timedelta
import itertools
import threading

import numpy as np
import pytest

import dehps.feature_runtime.cache as runtime_cache_module
from dehps.feature_runtime import (
    FeatureABICompiler,
    FeatureABIRuntime,
    FeatureABIVerifier,
    FeatureCompileRequest,
    FeatureCompiler,
    FeatureRuntimeViolation,
    RuntimeABICache,
)
from dehps.input_contracts import HistorySnapshotArtifact, WindowMode, WindowSpec
from dehps.models.frequency_ranker import FrequencyRankerConfig, train_frequency_stats
from dehps.optimization.walk_forward import _config_weight_matrix, build_ranked_universe
from dehps.scoring_kernel import (
    KernelPlanner,
    KernelRequest,
    WeightMatrix,
    candidate_store_from_matrix,
    numbers_mask,
    pack_window_state,
)
from dehps.scoring_kernel.numpy_backend import component_tile
from dehps.unified_runtime import UnifiedRuntimeVerifier


CODE_COMMIT = "a" * 40


def _case(candidate_count: int = 600):
    combinations = list(
        itertools.islice(itertools.combinations(range(1, 34), 6), candidate_count)
    )
    matrix = build_ranked_universe(
        combinations,
        use_cache=False,
        include_hard_filter_exclusions=True,
    )
    store = candidate_store_from_matrix(matrix)
    start_date = date(2026, 1, 1)
    history = [
        (
            f"2025{index:03d}",
            start_date + timedelta(days=index),
            tuple(int(number) for number in row),
        )
        for index, row in enumerate(matrix.numbers[50:450:20], start=1)
    ]
    snapshot = HistorySnapshotArtifact.from_history(history)
    window = WindowSpec(
        mode=WindowMode.EXPANDING,
        as_of_issue=history[-1][0],
        include_as_of=True,
        size=None,
        target_issue="2026051",
    ).materialize(snapshot)
    return snapshot, window, store


def _direct_runtime(snapshot, window, store, *, tile_size: int) -> FeatureABIRuntime:
    tiles = []
    for start in range(0, max(1, len(store)), tile_size):
        artifact = FeatureCompiler().compile(
            FeatureCompileRequest(
                window=window,
                candidate_store=store,
                start=start,
                end=min(start + tile_size, len(store)),
            )
        )
        tiles.append(FeatureABICompiler().compile(artifact))
    return FeatureABIRuntime(
        history_snapshot=snapshot,
        window_artifact=window,
        candidate_package=store.candidate_abi_package,
        feature_tiles=tuple(tiles),
    )


def test_runtime_abi_cache_reuses_read_only_feature_buffers_and_verified_runtime() -> None:
    snapshot, window, store = _case()
    cache = RuntimeABICache(max_entries=8, max_payload_bytes=8 * 1024 * 1024)

    first = cache.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=200,
    )
    second = cache.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=200,
    )

    assert first.runtime_cache_hit is False
    assert second.runtime_cache_hit is True
    assert second.all_feature_cache_hits is True
    assert second.verification_strategy == "assembled_runtime_transaction"
    assert second.feature_payload_verification_passes == 0
    assert second.runtime_payload_verification_passes == 1
    assert second.transaction_recovered is False
    assert second.as_dict()["verification_strategy"] == "assembled_runtime_transaction"
    assert second.verified_runtime is first.verified_runtime
    assert second.verified_runtime.verified_runtime_id == first.verified_runtime.verified_runtime_id
    for left, right in zip(first.feature_receipts, second.feature_receipts):
        assert right.cache_hit is True
        assert right.package is left.package
        assert right.package.values is left.package.values
        assert right.package.values.flags.writeable is False
    assert cache.stats().as_dict() == {
        "protocol": "runtime_abi_cache.v1",
        "feature_hits": 3,
        "feature_misses": 3,
        "runtime_hits": 1,
        "runtime_misses": 1,
        "invalidations": 0,
        "evictions": 0,
        "feature_entries": 3,
        "runtime_entries": 1,
        "payload_bytes": 600 * 32 * 8,
        "max_entries": 8,
        "max_payload_bytes": 8 * 1024 * 1024,
    }


def test_runtime_abi_cache_warm_transaction_coalesces_payload_verification(
    monkeypatch,
) -> None:
    snapshot, window, store = _case()

    class CountingFeatureVerifier(FeatureABIVerifier):
        calls = 0

        def verify(self, *args, **kwargs):
            type(self).calls += 1
            return super().verify(*args, **kwargs)

    class CountingRuntimeVerifier(UnifiedRuntimeVerifier):
        def __init__(self):
            self.verify_calls = 0
            self.verify_package_calls = 0

        def verify(self, runtime):
            self.verify_calls += 1
            return super().verify(runtime)

        def verify_package(self, package):
            self.verify_package_calls += 1
            return super().verify_package(package)

    monkeypatch.setattr(
        runtime_cache_module,
        "FeatureABIVerifier",
        CountingFeatureVerifier,
    )
    runtime_verifier = CountingRuntimeVerifier()
    cache = RuntimeABICache(runtime_verifier=runtime_verifier)

    cache.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=200,
    )
    cold_feature_passes = CountingFeatureVerifier.calls
    warm = cache.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=200,
    )

    assert cold_feature_passes == 3
    assert CountingFeatureVerifier.calls == cold_feature_passes
    assert runtime_verifier.verify_calls == 1
    assert runtime_verifier.verify_package_calls == 1
    assert warm.feature_payload_verification_passes == 0
    assert warm.runtime_payload_verification_passes == 1


def test_runtime_abi_cache_rejects_history_window_mismatch_before_partial_insert() -> None:
    _, window, store = _case()
    other_snapshot = HistorySnapshotArtifact.from_history(
        [
            ("2025001", date(2025, 1, 1), (1, 2, 3, 4, 5, 6)),
            ("2025002", date(2025, 1, 2), (2, 3, 4, 5, 6, 7)),
        ]
    )
    cache = RuntimeABICache()

    with pytest.raises(
        FeatureRuntimeViolation,
        match="feature_runtime_history_window_binding_mismatch",
    ):
        cache.compile_runtime(
            history_snapshot=other_snapshot,
            window=window,
            candidate_store=store,
            tile_size=200,
        )

    assert cache.stats().feature_entries == 0
    assert cache.stats().runtime_entries == 0


def test_runtime_abi_cache_key_changes_with_range_context_and_candidate_static_input() -> None:
    snapshot, window, store = _case()
    cache = RuntimeABICache()
    target_date = max(record.draw_date for record in window.records) + timedelta(days=1)
    first_request = FeatureCompileRequest(
        window=window,
        candidate_store=store,
        start=0,
        end=100,
        target_draw_date=target_date,
    )
    first = cache.compile_feature(first_request)
    repeated = cache.compile_feature(first_request)
    other_range = cache.compile_feature(
        FeatureCompileRequest(
            window=window,
            candidate_store=store,
            start=100,
            end=200,
            target_draw_date=target_date,
        )
    )
    other_date = cache.compile_feature(
        FeatureCompileRequest(
            window=window,
            candidate_store=store,
            start=0,
            end=100,
            target_draw_date=target_date + timedelta(days=2),
        )
    )
    rolling_window = WindowSpec(
        mode=WindowMode.ROLLING,
        size=10,
        as_of_issue=window.spec.as_of_issue,
        include_as_of=True,
        target_issue=window.spec.target_issue,
    ).materialize(snapshot)
    other_window = cache.compile_feature(
        FeatureCompileRequest(
            window=rolling_window,
            candidate_store=store,
            start=0,
            end=100,
            target_draw_date=target_date,
        )
    )
    extended_snapshot = HistorySnapshotArtifact.from_history(
        [record.as_history_draw() for record in snapshot.records]
        + [
            (
                "2025021",
                target_date,
                tuple(int(value) for value in store.numbers[451]),
            )
        ]
    )
    extended_window = WindowSpec(
        mode=WindowMode.EXPANDING,
        as_of_issue="2025021",
        include_as_of=True,
        size=None,
        target_issue="2026051",
    ).materialize(extended_snapshot)
    other_history = cache.compile_feature(
        FeatureCompileRequest(
            window=extended_window,
            candidate_store=store,
            start=0,
            end=100,
            target_draw_date=target_date + timedelta(days=1),
        )
    )
    store.structural_score[0] += 0.125
    changed_static = cache.compile_feature(first_request)

    assert repeated.cache_hit is True
    assert other_range.cache_hit is False
    assert other_date.cache_hit is False
    assert other_window.cache_hit is False
    assert other_history.cache_hit is False
    assert changed_static.cache_hit is False
    assert len(
        {
            first.key.cache_key_digest,
            other_range.key.cache_key_digest,
            other_date.key.cache_key_digest,
            other_window.key.cache_key_digest,
            other_history.key.cache_key_digest,
            changed_static.key.cache_key_digest,
        }
    ) == 6
    assert first.key.history_snapshot_digest == window.envelope.history_snapshot_digest
    assert other_window.key.history_snapshot_digest == first.key.history_snapshot_digest
    assert other_window.key.window_artifact_digest != first.key.window_artifact_digest
    assert other_history.key.history_snapshot_digest != first.key.history_snapshot_digest
    assert first.key.feature_layout_digest == first.package.header.layout_digest
    assert replace(first.key, feature_contract_digest="0" * 64).cache_key_digest != (
        first.key.cache_key_digest
    )
    assert replace(first.key, feature_layout_digest="0" * 64).cache_key_digest != (
        first.key.cache_key_digest
    )
    assert replace(first.key, feature_compiler_version="compiler.v2").cache_key_digest != (
        first.key.cache_key_digest
    )


def test_runtime_abi_cache_invalidates_mutated_cached_feature_buffer() -> None:
    _, window, store = _case()
    cache = RuntimeABICache()
    request = FeatureCompileRequest(window=window, candidate_store=store, start=0, end=100)
    first = cache.compile_feature(request)
    canonical = first.package.values.copy()

    first.package.values.setflags(write=True)
    first.package.values[0, 0] += 1.0
    recovered = cache.compile_feature(request)

    assert recovered.cache_hit is False
    assert recovered.package is not first.package
    assert recovered.package.values.flags.writeable is False
    assert np.array_equal(recovered.package.values, canonical)
    assert cache.stats().invalidations == 1

    object.__setattr__(
        recovered.package,
        "header",
        replace(recovered.package.header, source_artifact_digest="f" * 64),
    )
    header_recovered = cache.compile_feature(request)
    assert header_recovered.cache_hit is False
    assert header_recovered.package.header.source_artifact_digest != "f" * 64
    assert cache.stats().invalidations == 2


def test_runtime_abi_cache_invalidates_mutated_verified_runtime_seal() -> None:
    snapshot, window, store = _case()
    cache = RuntimeABICache()
    first = cache.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=200,
    )
    object.__setattr__(
        first.verified_runtime,
        "verification_digest",
        "f" * 64,
    )

    recovered = cache.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=200,
    )

    assert recovered.runtime_cache_hit is False
    assert recovered.verified_runtime is not first.verified_runtime
    assert recovered.verified_runtime.verification_digest != "f" * 64
    assert recovered.verification_strategy == "transaction_fallback_recovery"
    assert recovered.feature_payload_verification_passes == 3
    assert recovered.runtime_payload_verification_passes == 1
    assert recovered.transaction_recovered is True
    assert cache.stats().invalidations == 1


def test_runtime_abi_cache_transaction_recovers_mutated_feature_payload() -> None:
    snapshot, window, store = _case()
    cache = RuntimeABICache()
    first = cache.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=200,
    )
    canonical = first.feature_receipts[0].package.values.copy()
    first.feature_receipts[0].package.values.setflags(write=True)
    first.feature_receipts[0].package.values[0, 0] += 1.0
    first.feature_receipts[0].package.values.setflags(write=False)

    recovered = cache.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=200,
    )

    assert recovered.runtime_cache_hit is False
    assert recovered.verification_strategy == "transaction_fallback_recovery"
    assert recovered.feature_payload_verification_passes == 3
    assert recovered.runtime_payload_verification_passes == 2
    assert recovered.transaction_recovered is True
    assert recovered.feature_receipts[0].cache_hit is False
    assert np.array_equal(recovered.feature_receipts[0].package.values, canonical)
    assert cache.stats().invalidations == 1
    assert cache.stats().evictions == 1


def test_runtime_abi_cache_transaction_rekeys_changed_candidate_static_input() -> None:
    snapshot, window, store = _case()
    cache = RuntimeABICache()
    first = cache.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=200,
    )
    first_keys = tuple(
        receipt.key.cache_key_digest for receipt in first.feature_receipts
    )

    store.structural_score[0] += 0.125
    changed = cache.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=200,
    )

    assert changed.runtime_cache_hit is False
    assert changed.transaction_recovered is False
    assert changed.verification_strategy == "per_feature_verification"
    assert changed.feature_payload_verification_passes == 3
    assert changed.runtime_payload_verification_passes == 1
    assert changed.feature_receipts[0].key.cache_key_digest != first_keys[0]
    assert tuple(
        receipt.key.cache_key_digest for receipt in changed.feature_receipts[1:]
    ) == first_keys[1:]


def test_runtime_abi_cache_serializes_concurrent_identical_compilation() -> None:
    _, window, store = _case()

    class CountingCompiler(FeatureCompiler):
        def __init__(self):
            self.calls = 0
            self.lock = threading.Lock()

        def compile(self, request):
            with self.lock:
                self.calls += 1
            return super().compile(request)

    compiler = CountingCompiler()
    cache = RuntimeABICache(feature_compiler=compiler)
    request = FeatureCompileRequest(window=window, candidate_store=store, start=0, end=200)

    with ThreadPoolExecutor(max_workers=4) as executor:
        receipts = list(executor.map(lambda _index: cache.compile_feature(request), range(4)))

    assert compiler.calls == 1
    assert sum(receipt.cache_hit for receipt in receipts) == 3
    assert len({id(receipt.package) for receipt in receipts}) == 1


def test_runtime_abi_cache_serializes_concurrent_identical_runtime_compilation() -> None:
    snapshot, window, store = _case()

    class CountingCompiler(FeatureCompiler):
        def __init__(self):
            self.calls = 0
            self.lock = threading.Lock()

        def compile(self, request):
            with self.lock:
                self.calls += 1
            return super().compile(request)

    compiler = CountingCompiler()
    cache = RuntimeABICache(feature_compiler=compiler)

    def compile_runtime(_index):
        return cache.compile_runtime(
            history_snapshot=snapshot,
            window=window,
            candidate_store=store,
            tile_size=200,
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        compilations = list(executor.map(compile_runtime, range(4)))

    assert compiler.calls == 3
    assert sum(compilation.runtime_cache_hit for compilation in compilations) == 3
    assert len({id(compilation.verified_runtime) for compilation in compilations}) == 1
    assert cache.stats().runtime_hits == 3
    assert cache.stats().runtime_misses == 1


def test_runtime_abi_cache_lru_and_byte_limits_are_deterministic() -> None:
    snapshot, window, store = _case()
    cache = RuntimeABICache(max_entries=2, max_payload_bytes=10 * 1024 * 1024)
    requests = [
        FeatureCompileRequest(
            window=window,
            candidate_store=store,
            start=start,
            end=start + 50,
        )
        for start in (0, 50, 100)
    ]
    receipts = [cache.compile_feature(request) for request in requests]

    assert all(receipt.stored for receipt in receipts)
    assert cache.stats().feature_entries == 2
    assert cache.stats().evictions == 1
    assert cache.compile_feature(requests[0]).cache_hit is False

    uncached = RuntimeABICache(max_entries=2, max_payload_bytes=1)
    receipt = uncached.compile_feature(requests[0])
    assert receipt.stored is False
    assert uncached.stats().feature_entries == 0
    assert uncached.stats().payload_bytes == 0

    bounded = RuntimeABICache(max_entries=3, max_payload_bytes=10 * 1024 * 1024)
    bounded.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=200,
    )
    assert bounded.stats().runtime_entries == 1
    bounded.compile_feature(
        FeatureCompileRequest(
            window=window,
            candidate_store=store,
            start=0,
            end=50,
        )
    )
    assert bounded.stats().feature_entries == 3
    assert bounded.stats().runtime_entries == 0
    assert bounded.stats().payload_bytes <= bounded.stats().max_payload_bytes

    too_small = RuntimeABICache(max_entries=8, max_payload_bytes=1)
    compilation = too_small.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=200,
    )
    assert compilation.runtime_cache_hit is False
    assert too_small.stats().feature_entries == 0
    assert too_small.stats().runtime_entries == 0


def test_cached_and_uncached_numpy_numba_results_are_strictly_identical() -> None:
    snapshot, window, store = _case(candidate_count=1_000)
    cache = RuntimeABICache(max_entries=16)
    cached = cache.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=257,
    ).verified_runtime
    direct = UnifiedRuntimeVerifier().verify(
        _direct_runtime(snapshot, window, store, tile_size=257)
    )
    configs = (
        FrequencyRankerConfig(),
        FrequencyRankerConfig(
            structural_weight=0.0,
            frequency_weight=0.45,
            omission_weight=0.35,
            previous_overlap_weight=-0.1,
        ),
    )
    weights = WeightMatrix(np.ascontiguousarray(_config_weight_matrix(configs)))
    history = [record.as_history_draw() for record in window.records]
    state = pack_window_state(train_frequency_stats(history))
    target_id = len(store) // 2
    target_scores = np.ascontiguousarray(
        np.round(
            component_tile(store, state, target_id, target_id + 1)[0]
            @ weights.values.T,
            8,
        ),
        dtype=np.float64,
    )
    request = KernelRequest(
        target_scores=target_scores,
        target_lex_id=target_id,
        target_mask=numbers_mask(tuple(int(value) for value in store.numbers[target_id])),
        top_k=100,
        chunk_size=211,
        worker_count=2,
        exact_rank=True,
        red5=True,
        window_id=1,
    )

    for backend_name in ("numpy_reference", "numba_cpu"):
        planner = KernelPlanner(backend_name)
        cached_result = planner.score_rank_feature_abi(
            planner.prepare_feature_abi(cached, code_commit=CODE_COMMIT),
            weights,
            request,
        )
        direct_result = planner.score_rank_feature_abi(
            planner.prepare_feature_abi(direct, code_commit=CODE_COMMIT),
            weights,
            request,
        )
        assert np.array_equal(cached_result.target_scores, direct_result.target_scores)
        assert np.array_equal(cached_result.exact_ranks, direct_result.exact_ranks)
        assert np.array_equal(
            cached_result.top_candidate_ids,
            direct_result.top_candidate_ids,
        )
        assert np.array_equal(cached_result.top_scores, direct_result.top_scores)
        assert np.array_equal(
            cached_result.red5_candidate_ids,
            direct_result.red5_candidate_ids,
        )
        assert np.array_equal(cached_result.red5_scores, direct_result.red5_scores)
        assert np.array_equal(cached_result.red5_ranks, direct_result.red5_ranks)
