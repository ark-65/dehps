from __future__ import annotations

from dataclasses import replace
import itertools

import numpy as np
import pytest

from dehps.input_contracts import InputContractViolation
from dehps.models.frequency_ranker import FrequencyRankerConfig, train_frequency_stats
from dehps.optimization.walk_forward import (
    _components_for_matrix,
    _config_weight_matrix,
    _kernel_score_rank,
    _target_scores,
    build_ranked_universe,
    compile_score_config_grid_artifact,
    score_config_grid,
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
from dehps.scoring_kernel.full_score_artifact import (
    FullScoreGridArtifactCompilerV1,
    FullScoreGridArtifactVerifierV1,
    FullScoreGridViolation,
)
from dehps.scoring_kernel.runtime_input import default_runtime_input_compiler
from dehps.unified_runtime import RuntimeVerificationViolation
from scripts.run_forward_scoring_shadow import execute_verified_replay_pair


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


def test_full_score_grid_artifact_is_reference_exact_and_deterministic() -> None:
    default_runtime_input_compiler().cache.clear()
    matrix, history, configs, _target_numbers, stats, _scores = _case()
    expected = np.round(
        _components_for_matrix(matrix, stats) @ _config_weight_matrix(configs).T,
        8,
    )

    first = compile_score_config_grid_artifact(
        train_history=history,
        configs=configs,
        ranked_universe=matrix,
        target_issue="2025051",
    )
    second = compile_score_config_grid_artifact(
        train_history=history,
        configs=configs,
        ranked_universe=matrix,
        target_issue="2025051",
    )

    assert np.array_equal(first.scores, expected)
    assert first.scores.flags.writeable is False
    assert first.artifact_digest == second.artifact_digest
    assert first.payload_digest == second.payload_digest
    assert first.runtime_envelope.state.value == "artifact_produced"
    assert first.runtime_envelope.artifact_type == "full_score_grid"
    assert first.header.verified_runtime_id == matrix.cache_info["full_score_grid"][
        "runtime_input"
    ]["runtime_abi_cache"]["verified_runtime_id"]
    assert matrix.cache_info["full_score_grid"]["runtime_input"][
        "runtime_abi_cache"
    ]["runtime_cache_hit"] is True

    projected = score_config_grid(
        train_history=history,
        configs=configs,
        ranked_universe=matrix,
        target_issue="2025051",
    )
    assert np.array_equal(projected, expected)
    assert projected.flags.writeable is False


def test_full_score_grid_verifier_rejects_score_weight_and_envelope_drift() -> None:
    matrix, history, configs, _target_numbers, _stats, _scores = _case()
    store = candidate_store_from_matrix(matrix)
    runtime_inputs = default_runtime_input_compiler().compile_effective_history(
        history=history,
        candidate_store=store,
        tile_size=333,
        target_issue="2025051",
    )
    weights = WeightMatrix(
        np.ascontiguousarray(_config_weight_matrix(configs), dtype=np.float64)
    )
    artifact = FullScoreGridArtifactCompilerV1().compile(
        verified_runtime=runtime_inputs.verified_runtime,
        weights=weights,
        code_commit="a" * 40,
    )
    verifier = FullScoreGridArtifactVerifierV1()
    verifier.verify(
        artifact,
        verified_runtime=runtime_inputs.verified_runtime,
        weights=weights,
    )

    writable = artifact.scores.copy()
    with pytest.raises(FullScoreGridViolation, match="full_score_buffer_writable"):
        verifier.verify(
            replace(artifact, scores=writable),
            verified_runtime=runtime_inputs.verified_runtime,
            weights=weights,
        )

    mutated = artifact.scores.copy()
    mutated[0, 0] += 0.25
    mutated.setflags(write=False)
    with pytest.raises(
        FullScoreGridViolation,
        match="full_score_payload_digest_mismatch",
    ):
        verifier.verify(
            replace(artifact, scores=mutated),
            verified_runtime=runtime_inputs.verified_runtime,
            weights=weights,
        )

    wrong_weights = WeightMatrix(weights.values.copy())
    wrong_weights.values[0, 0] += 0.01
    with pytest.raises(
        FullScoreGridViolation,
        match="full_score_header_binding_mismatch",
    ):
        verifier.verify(
            artifact,
            verified_runtime=runtime_inputs.verified_runtime,
            weights=wrong_weights,
        )

    with pytest.raises(ValueError, match="runtime_backend_mismatch"):
        verifier.verify(
            replace(
                artifact,
                runtime_envelope=replace(
                    artifact.runtime_envelope,
                    backend="unverified_backend",
                ),
            ),
            verified_runtime=runtime_inputs.verified_runtime,
            weights=weights,
        )


def test_full_score_grid_compiler_rejects_raw_unverified_runtime() -> None:
    matrix, history, configs, _target_numbers, _stats, _scores = _case()
    store = candidate_store_from_matrix(matrix)
    runtime_inputs = default_runtime_input_compiler().compile_effective_history(
        history=history,
        candidate_store=store,
        tile_size=333,
        target_issue="2025051",
    )
    weights = WeightMatrix(
        np.ascontiguousarray(_config_weight_matrix(configs), dtype=np.float64)
    )

    with pytest.raises(RuntimeVerificationViolation, match="runtime_package_not_verified"):
        FullScoreGridArtifactCompilerV1().compile(
            verified_runtime=runtime_inputs.verified_runtime.runtime,  # type: ignore[arg-type]
            weights=weights,
            code_commit="a" * 40,
        )


def test_post_draw_shadow_replay_uses_one_verified_runtime_identity() -> None:
    matrix, history, configs, target_numbers, stats, scores = _case()
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
    )

    official, shadow, runtime_cache = execute_verified_replay_pair(
        history=history,
        store=store,
        target_draw_date=None,
        target_issue="2025051",
        weights=weights,
        request=request,
        code_commit="a" * 40,
    )
    legacy = _legacy_result(matrix, configs, target_numbers, stats, scores)

    assert official.telemetry["verified_runtime_id"] == shadow.telemetry[
        "verified_runtime_id"
    ]
    assert official.telemetry["verified_runtime_id"] == runtime_cache[
        "verified_runtime_id"
    ]
    assert np.array_equal(official.target_scores, shadow.target_scores)
    assert np.array_equal(official.exact_ranks, shadow.exact_ranks)
    assert np.array_equal(official.top_candidate_ids, shadow.top_candidate_ids)
    assert np.array_equal(official.red5_candidate_ids, shadow.red5_candidate_ids)
    _assert_result_exact(official, legacy)
