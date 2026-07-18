from __future__ import annotations

from dataclasses import replace
import itertools

import numpy as np
import pytest
from numba import config as numba_config

from dehps.feature_runtime import (
    FeatureABICompiler,
    FeatureABIRuntime,
    FeatureCompileRequest,
    FeatureCompiler,
    FeatureRuntimeViolation,
)
from dehps.input_contracts import HistorySnapshotArtifact, WindowMode, WindowSpec
from dehps.models.frequency_ranker import FrequencyRankerConfig, train_frequency_stats
from dehps.optimization.walk_forward import _config_weight_matrix, build_ranked_universe
from dehps.scoring_kernel import (
    KernelPlanner,
    KernelRequest,
    KernelWorkspace,
    WeightMatrix,
    candidate_store_from_matrix,
    compare_kernel_results,
    numbers_mask,
    pack_window_state,
)
from dehps.scoring_kernel.numpy_backend import NumpyReferenceBackend, component_tile
from dehps.scoring_kernel.feature_abi_backend import kernel_result_payload_digest
from dehps.runtime_envelope import (
    RuntimeEnvelopeCompiler,
    RuntimeEnvelopeV1,
    RuntimeEnvelopeVerifier,
    RuntimeEnvelopeViolation,
    RuntimeState,
)
from dehps.runtime_provenance import project_runtime_envelope
from dehps.unified_runtime import (
    RuntimeVerificationViolation,
    UnifiedRuntimeVerifier,
    VerifiedRuntimePackage,
)


TEST_CODE_COMMIT = "a" * 40


@pytest.fixture(scope="module")
def feature_runtime_case():
    candidates = list(itertools.islice(itertools.combinations(range(1, 34), 6), 3_000))
    matrix = build_ranked_universe(
        candidates,
        use_cache=False,
        include_hard_filter_exclusions=True,
    )
    history = [
        (f"2025{index:03d}", tuple(int(number) for number in row))
        for index, row in enumerate(matrix.numbers[100:2_100:40], start=1)
    ]
    snapshot = HistorySnapshotArtifact.from_history(history)
    window = WindowSpec(
        mode=WindowMode.EXPANDING,
        as_of_issue=history[-1][0],
        include_as_of=True,
        size=None,
        target_issue="2026051",
    ).materialize(snapshot)
    store = candidate_store_from_matrix(matrix)
    stats = train_frequency_stats([record.as_history_draw() for record in window.records])
    state = pack_window_state(stats)
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
            short_hot_frequency_weight=0.11,
            long_omission_cooldown_weight=-0.07,
        ),
    )
    weights = WeightMatrix(np.ascontiguousarray(_config_weight_matrix(configs)))
    target_id = len(store) // 2
    target_scores = np.ascontiguousarray(
        np.round(component_tile(store, state, target_id, target_id + 1)[0] @ weights.values.T, 8),
        dtype=np.float64,
    )
    target_numbers = tuple(int(number) for number in store.numbers[target_id])
    request = KernelRequest(
        target_scores=target_scores,
        target_lex_id=target_id,
        target_mask=numbers_mask(target_numbers),
        top_k=127,
        chunk_size=333,
        worker_count=1,
        exact_rank=True,
        red5=True,
        window_id=91,
    )
    return {
        "snapshot": snapshot,
        "window": window,
        "store": store,
        "state": state,
        "weights": weights,
        "request": request,
    }


def _runtime(case, *, tile_size: int) -> FeatureABIRuntime:
    store = case["store"]
    tiles = []
    for start in range(0, len(store), tile_size):
        artifact = FeatureCompiler().compile(
            FeatureCompileRequest(
                window=case["window"],
                candidate_store=store,
                start=start,
                end=min(start + tile_size, len(store)),
            )
        )
        tiles.append(FeatureABICompiler().compile(artifact))
    assert store.candidate_abi_package is not None
    return FeatureABIRuntime(
        history_snapshot=case["snapshot"],
        window_artifact=case["window"],
        candidate_package=store.candidate_abi_package,
        feature_tiles=tuple(tiles),
    )


def _legacy_result(case):
    backend = NumpyReferenceBackend()
    return backend.score_rank(
        backend.prepare(case["store"]),
        case["state"],
        case["weights"],
        case["request"],
        KernelWorkspace(),
    )


def _verified(runtime: FeatureABIRuntime) -> VerifiedRuntimePackage:
    return UnifiedRuntimeVerifier().verify(runtime)


def _result_payload_digest(result, *, top_candidate_ids=None) -> str:
    return kernel_result_payload_digest(
        target_scores=result.target_scores,
        exact_ranks=result.exact_ranks,
        top_candidate_ids=(
            result.top_candidate_ids if top_candidate_ids is None else top_candidate_ids
        ),
        top_scores=result.top_scores,
        red5_candidate_ids=result.red5_candidate_ids,
        red5_scores=result.red5_scores,
        red5_ranks=result.red5_ranks,
    )


@pytest.mark.parametrize("tile_size", [127, 777])
def test_feature_abi_runtime_matches_existing_reference_score_rank_topk_and_red5(
    feature_runtime_case,
    tile_size,
) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=tile_size)
    planner = KernelPlanner("numpy_reference")

    result = planner.score_rank_feature_abi(
        planner.prepare_feature_abi(_verified(runtime), code_commit=TEST_CODE_COMMIT),
        feature_runtime_case["weights"],
        feature_runtime_case["request"],
        KernelWorkspace(),
    )
    legacy = _legacy_result(feature_runtime_case)

    assert result.backend == "feature_abi_numpy_reference"
    assert np.array_equal(result.target_scores, legacy.target_scores)
    assert np.array_equal(result.exact_ranks, legacy.exact_ranks)
    assert np.array_equal(result.top_candidate_ids, legacy.top_candidate_ids)
    assert np.array_equal(result.top_scores, legacy.top_scores)
    assert np.array_equal(result.red5_candidate_ids, legacy.red5_candidate_ids)
    assert np.array_equal(result.red5_scores, legacy.red5_scores)
    assert np.array_equal(result.red5_ranks, legacy.red5_ranks)
    assert result.telemetry["feature_abi"] == "feature_abi.v1"
    assert result.telemetry["candidate_identity_id_kind"] == "candidate_abi_row_index"
    assert (
        result.telemetry["candidate_digest"]
        == runtime.candidate_package.header.candidate_digest
    )
    assert (
        result.telemetry["candidate_layout_digest"]
        == runtime.candidate_package.header.layout_digest
    )
    assert result.telemetry["candidate_abi_verification_id"].startswith(
        "verified_candidate.v1-"
    )
    assert result.telemetry["feature_runtime_digest"] == runtime.runtime_digest
    assert result.telemetry["runtime_verifier_version"] == "unified_runtime_verifier.v1"
    assert result.telemetry["runtime_verification_digest"] == (
        _verified(runtime).verification_digest
    )
    assert result.telemetry["verified_runtime_id"] == _verified(runtime).verified_runtime_id
    envelope = RuntimeEnvelopeV1.from_dict(result.runtime_envelope)
    assert envelope.state is RuntimeState.ARTIFACT_PRODUCED
    assert envelope.state_path == tuple(RuntimeState)
    assert envelope.history_snapshot_digest == runtime.window_artifact.envelope.history_snapshot_digest
    assert envelope.window_artifact_digest == runtime.window_artifact.artifact_digest
    assert envelope.candidate_package_digest == runtime.candidate_package.package_digest
    assert envelope.feature_runtime_digest == runtime.runtime_digest
    assert envelope.code_commit == TEST_CODE_COMMIT
    assert result.telemetry["runtime_envelope_digest"] == envelope.envelope_digest
    RuntimeEnvelopeVerifier().verify_artifact_payload(
        envelope,
        payload_digest=_result_payload_digest(result),
        runtime=runtime,
        expected_backend="feature_abi_numpy_reference",
    )
    projection = project_runtime_envelope(
        result.runtime_envelope,
        unavailable_reason="not_used",
    ).as_dict()
    assert projection["status"] == "verified"
    assert projection["reason"] is None
    assert projection["envelope"]["envelope_digest"] == envelope.envelope_digest


@pytest.mark.parametrize("backend_name", ["numpy_reference", "numba_cpu"])
def test_feature_abi_topk_reduction_is_worker_invariant(
    feature_runtime_case,
    backend_name,
) -> None:
    requested_workers = 3
    runtime = _runtime(feature_runtime_case, tile_size=333)
    planner = KernelPlanner(backend_name)
    prepared = planner.prepare_feature_abi(_verified(runtime), code_commit=TEST_CODE_COMMIT)
    serial = planner.score_rank_feature_abi(
        prepared,
        feature_runtime_case["weights"],
        replace(feature_runtime_case["request"], worker_count=1),
    )
    parallel = planner.score_rank_feature_abi(
        prepared,
        feature_runtime_case["weights"],
        replace(feature_runtime_case["request"], worker_count=requested_workers),
    )

    assert np.array_equal(parallel.exact_ranks, serial.exact_ranks)
    assert np.array_equal(parallel.top_candidate_ids, serial.top_candidate_ids)
    assert np.array_equal(parallel.top_scores, serial.top_scores)
    assert np.array_equal(parallel.red5_candidate_ids, serial.red5_candidate_ids)
    assert np.array_equal(parallel.red5_scores, serial.red5_scores)
    assert np.array_equal(parallel.red5_ranks, serial.red5_ranks)
    expected_workers = (
        requested_workers
        if backend_name == "numpy_reference"
        else min(requested_workers, int(numba_config.NUMBA_NUM_THREADS))
    )
    assert parallel.telemetry["worker_count"] == expected_workers
    assert parallel.telemetry["topk_reduction_workers"] == expected_workers


def test_feature_abi_runtime_preflight_is_deterministic(feature_runtime_case) -> None:
    first = _runtime(feature_runtime_case, tile_size=500)
    second = _runtime(feature_runtime_case, tile_size=500)

    first.verify()
    second.verify()
    assert first.runtime_digest == second.runtime_digest


def test_feature_abi_runtime_rejects_incomplete_or_misbound_tiles(feature_runtime_case) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=500)

    with pytest.raises(FeatureRuntimeViolation, match="feature_runtime_incomplete_coverage"):
        replace(runtime, feature_tiles=runtime.feature_tiles[:-1]).verify()

    first = runtime.feature_tiles[0]
    wrong_header = replace(first.header, candidate_package_digest="0" * 64)
    wrong_first = replace(first, header=wrong_header)
    with pytest.raises(FeatureRuntimeViolation, match="feature_runtime_candidate_binding_mismatch"):
        replace(runtime, feature_tiles=(wrong_first, *runtime.feature_tiles[1:])).verify()


def test_feature_abi_runtime_rejects_context_drift_between_tiles(feature_runtime_case) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=500)
    second = runtime.feature_tiles[1]
    wrong_header = replace(second.header, target_context_digest="5" * 64)

    with pytest.raises(FeatureRuntimeViolation, match="feature_runtime_context_mismatch"):
        replace(
            runtime,
            feature_tiles=(runtime.feature_tiles[0], replace(second, header=wrong_header), *runtime.feature_tiles[2:]),
        ).verify()


@pytest.mark.parametrize("tile_size", [127, 777])
def test_numba_feature_abi_runtime_matches_reference_exactly(
    feature_runtime_case,
    tile_size,
) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=tile_size)
    verified = _verified(runtime)
    reference_planner = KernelPlanner("numpy_reference")
    numba_planner = KernelPlanner("numba_cpu")

    reference = reference_planner.score_rank_feature_abi(
        reference_planner.prepare_feature_abi(
            verified,
            code_commit=TEST_CODE_COMMIT,
        ),
        feature_runtime_case["weights"],
        feature_runtime_case["request"],
    )
    numba = numba_planner.score_rank_feature_abi(
        numba_planner.prepare_feature_abi(
            verified,
            code_commit=TEST_CODE_COMMIT,
        ),
        feature_runtime_case["weights"],
        feature_runtime_case["request"],
    )

    assert numba.backend == "feature_abi_numba_cpu"
    assert np.array_equal(numba.target_scores, reference.target_scores)
    assert np.array_equal(numba.exact_ranks, reference.exact_ranks)
    assert np.array_equal(numba.top_candidate_ids, reference.top_candidate_ids)
    assert np.array_equal(numba.top_scores, reference.top_scores)
    assert np.array_equal(numba.red5_candidate_ids, reference.red5_candidate_ids)
    assert np.array_equal(numba.red5_scores, reference.red5_scores)
    assert np.array_equal(numba.red5_ranks, reference.red5_ranks)
    assert numba.telemetry["verified_runtime_id"] == reference.telemetry[
        "verified_runtime_id"
    ]
    assert numba.telemetry["runtime_verification_digest"] == reference.telemetry[
        "runtime_verification_digest"
    ]
    envelope = RuntimeEnvelopeV1.from_dict(numba.runtime_envelope)
    assert envelope.backend == "feature_abi_numba_cpu"
    RuntimeEnvelopeVerifier().verify_artifact_payload(
        envelope,
        payload_digest=_result_payload_digest(numba),
        runtime=runtime,
        expected_backend="feature_abi_numba_cpu",
    )


def test_feature_abi_planner_rejects_cross_backend_prepared_runtime(
    feature_runtime_case,
) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=1_000)
    prepared = KernelPlanner("numpy_reference").prepare_feature_abi(
        _verified(runtime),
        code_commit=TEST_CODE_COMMIT,
    )

    with pytest.raises(FeatureRuntimeViolation, match="feature_abi_prepared_backend_mismatch"):
        KernelPlanner("numba_cpu").score_rank_feature_abi(
            prepared,
            feature_runtime_case["weights"],
            feature_runtime_case["request"],
        )


def test_planner_rejects_prepared_runtime_from_another_backend(feature_runtime_case) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=1_000)
    planner = KernelPlanner("numpy_reference")
    prepared = planner.prepare_feature_abi(_verified(runtime), code_commit=TEST_CODE_COMMIT)

    with pytest.raises(FeatureRuntimeViolation, match="feature_abi_prepared_backend_mismatch"):
        planner.score_rank_feature_abi(
            replace(prepared, backend_name="unverified_backend"),
            feature_runtime_case["weights"],
            feature_runtime_case["request"],
        )


@pytest.mark.parametrize("backend_name", ["numpy_reference", "numba_cpu"])
def test_feature_abi_runtime_preserves_strict_tie_order(
    feature_runtime_case,
    backend_name,
) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=700)
    planner = KernelPlanner(backend_name)
    target_id = feature_runtime_case["request"].target_lex_id
    weights = WeightMatrix(np.zeros((1, 32), dtype=np.float64))
    request = replace(
        feature_runtime_case["request"],
        target_scores=np.zeros(1, dtype=np.float64),
        top_k=10,
        red5=False,
    )

    result = planner.score_rank_feature_abi(
        planner.prepare_feature_abi(_verified(runtime), code_commit=TEST_CODE_COMMIT),
        weights,
        request,
    )

    assert result.exact_ranks.tolist() == [target_id + 1]
    assert result.top_candidate_ids.tolist() == [list(range(10))]
    assert result.top_scores.tolist() == [[0.0] * 10]


def test_runtime_envelope_state_machine_is_sequential_and_fail_closed(
    feature_runtime_case,
) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=750)
    ready = RuntimeEnvelopeCompiler().compile_kernel_ready(
        _verified(runtime),
        backend="feature_abi_numpy_reference",
        code_commit=TEST_CODE_COMMIT,
    )

    assert ready.state is RuntimeState.KERNEL_READY
    assert ready.state_path == tuple(RuntimeState)[:3]
    RuntimeEnvelopeVerifier().verify(ready, runtime=runtime)

    with pytest.raises(RuntimeEnvelopeViolation, match="invalid_runtime_state_transition"):
        ready.transition(RuntimeState.ARTIFACT_PRODUCED)

    executing = ready.transition(RuntimeState.KERNEL_EXECUTING)
    with pytest.raises(RuntimeEnvelopeViolation, match="artifact_digest_required_for_transition"):
        executing.transition(RuntimeState.ARTIFACT_PRODUCED)

    produced = executing.produce_artifact("9" * 64)
    assert produced.state_path == tuple(RuntimeState)
    RuntimeEnvelopeVerifier().verify_artifact_payload(
        produced,
        payload_digest="9" * 64,
        runtime=runtime,
    )


def test_shadow_comparison_ignores_only_the_expected_runtime_backend_field(
    feature_runtime_case,
) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=750)
    planner = KernelPlanner("numpy_reference")
    official = planner.score_rank_feature_abi(
        planner.prepare_feature_abi(_verified(runtime), code_commit=TEST_CODE_COMMIT),
        feature_runtime_case["weights"],
        feature_runtime_case["request"],
    )
    shadow_ready = RuntimeEnvelopeCompiler().compile_kernel_ready(
        _verified(runtime),
        backend="numba_cpu",
        code_commit=TEST_CODE_COMMIT,
    )
    shadow_envelope = shadow_ready.transition(
        RuntimeState.KERNEL_EXECUTING
    ).produce_artifact(_result_payload_digest(official))
    shadow = replace(
        official,
        backend="numba_cpu",
        telemetry={**official.telemetry, "backend": "numba_cpu"},
        runtime_envelope=shadow_envelope.as_dict(),
    )

    evidence = compare_kernel_results(
        target_issue="2026082",
        line_key="static_100",
        config_fingerprint="feature-runtime-fixture",
        candidate_store_version="candidate-store.v1",
        official=official,
        shadow=shadow,
    )

    assert evidence["comparison_status"] == "exact"
    assert evidence["runtime_envelope_mismatch_count"] == 0
    assert evidence["runtime_identity_mismatch_count"] == 0
    assert evidence["verified_runtime_id"] == official.telemetry["verified_runtime_id"]

    misbound_cache = compare_kernel_results(
        target_issue="2026082",
        line_key="static_100",
        config_fingerprint="feature-runtime-fixture",
        candidate_store_version="candidate-store.v1",
        official=official,
        shadow=shadow,
        runtime_abi_cache={
            "verified_runtime_id": "verified_runtime.v1-wrong",
            "runtime_verification_digest": official.telemetry[
                "runtime_verification_digest"
            ],
        },
    )

    assert misbound_cache["comparison_status"] == "mismatch"
    assert misbound_cache["runtime_identity_mismatch_count"] == 1


def test_runtime_envelope_rejects_invalid_commit_binding_and_serialized_tampering(
    feature_runtime_case,
) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=750)

    with pytest.raises(RuntimeEnvelopeViolation, match="runtime_code_commit_invalid"):
        RuntimeEnvelopeCompiler().compile_kernel_ready(
            _verified(runtime),
            backend="feature_abi_numpy_reference",
            code_commit="short-sha",
        )

    ready = RuntimeEnvelopeCompiler().compile_kernel_ready(
        _verified(runtime),
        backend="feature_abi_numpy_reference",
        code_commit=TEST_CODE_COMMIT,
    )
    serialized = ready.as_dict()
    serialized["candidate"] = {
        **serialized["candidate"],
        "package_digest": "0" * 64,
    }
    with pytest.raises(RuntimeEnvelopeViolation, match="runtime_envelope_digest_mismatch"):
        RuntimeEnvelopeV1.from_dict(serialized)

    without_digest = ready.as_dict()
    del without_digest["envelope_digest"]
    with pytest.raises(RuntimeEnvelopeViolation, match="runtime_envelope_digest_missing"):
        RuntimeEnvelopeV1.from_dict(without_digest)


def test_runtime_envelope_detects_detached_kernel_result_mutation(feature_runtime_case) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=750)
    planner = KernelPlanner("numpy_reference")
    result = planner.score_rank_feature_abi(
        planner.prepare_feature_abi(_verified(runtime), code_commit=TEST_CODE_COMMIT),
        feature_runtime_case["weights"],
        feature_runtime_case["request"],
    )
    envelope = RuntimeEnvelopeV1.from_dict(result.runtime_envelope)
    mutated_ids = result.top_candidate_ids.copy()
    mutated_ids[0, 0] += 1

    with pytest.raises(RuntimeEnvelopeViolation, match="runtime_artifact_payload_mismatch"):
        RuntimeEnvelopeVerifier().verify_artifact_payload(
            envelope,
            payload_digest=_result_payload_digest(result, top_candidate_ids=mutated_ids),
            runtime=runtime,
            expected_backend="feature_abi_numpy_reference",
        )


def test_runtime_envelope_backend_binding_is_rechecked_at_execution(
    feature_runtime_case,
) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=750)
    planner = KernelPlanner("numpy_reference")
    prepared = planner.prepare_feature_abi(_verified(runtime), code_commit=TEST_CODE_COMMIT)
    wrong_envelope = replace(prepared.runtime_envelope, backend="other_backend")

    with pytest.raises(RuntimeEnvelopeViolation, match="runtime_backend_mismatch"):
        planner.score_rank_feature_abi(
            replace(prepared, runtime_envelope=wrong_envelope),
            feature_runtime_case["weights"],
            feature_runtime_case["request"],
        )


def test_feature_runtime_rejects_history_window_snapshot_mismatch(feature_runtime_case) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=750)
    shorter = HistorySnapshotArtifact.from_history(
        [record.as_history_draw() for record in runtime.history_snapshot.records[:-1]]
    )

    with pytest.raises(FeatureRuntimeViolation, match="feature_runtime_history_window_binding_mismatch"):
        replace(runtime, history_snapshot=shorter).verify()


def test_unified_runtime_verifier_mints_a_deterministic_sealed_package(
    feature_runtime_case,
) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=750)

    first = UnifiedRuntimeVerifier().verify(runtime)
    second = UnifiedRuntimeVerifier().verify(runtime)

    assert first.verification_digest == second.verification_digest
    assert first.verified_runtime_id == second.verified_runtime_id
    assert first.as_dict() == second.as_dict()
    assert first.as_dict()["runtime_digest"] == runtime.runtime_digest
    UnifiedRuntimeVerifier().verify_package(first)


@pytest.mark.parametrize("backend_name", ["numpy_reference", "numba_cpu"])
def test_kernel_and_envelope_compilers_reject_raw_unverified_runtime(
    feature_runtime_case,
    backend_name,
) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=750)

    with pytest.raises(RuntimeVerificationViolation, match="runtime_package_not_verified"):
        KernelPlanner(backend_name).prepare_feature_abi(
            runtime,  # type: ignore[arg-type]
            code_commit=TEST_CODE_COMMIT,
        )

    with pytest.raises(RuntimeVerificationViolation, match="runtime_package_not_verified"):
        RuntimeEnvelopeCompiler().compile_kernel_ready(
            runtime,  # type: ignore[arg-type]
            backend="feature_abi_numpy_reference",
            code_commit=TEST_CODE_COMMIT,
        )


def test_unified_runtime_verifier_rejects_seal_and_payload_drift(
    feature_runtime_case,
) -> None:
    runtime = _runtime(feature_runtime_case, tile_size=750)
    verified = _verified(runtime)

    with pytest.raises(RuntimeVerificationViolation, match="runtime_verification_seal_mismatch"):
        UnifiedRuntimeVerifier().verify_package(
            replace(verified, verification_digest="0" * 64)
        )

    runtime.feature_tiles[0].values[0, 0] += 0.25
    with pytest.raises(RuntimeVerificationViolation, match="runtime_stage_verification_failed"):
        UnifiedRuntimeVerifier().verify_package(verified)


def test_unified_runtime_seal_cannot_be_reused_for_another_runtime(
    feature_runtime_case,
) -> None:
    first = _verified(_runtime(feature_runtime_case, tile_size=750))
    other_runtime = _runtime(feature_runtime_case, tile_size=600)

    with pytest.raises(RuntimeVerificationViolation, match="runtime_verification_seal_mismatch"):
        UnifiedRuntimeVerifier().verify_package(replace(first, runtime=other_runtime))
