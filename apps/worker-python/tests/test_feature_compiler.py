from __future__ import annotations

from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from dehps.feature_runtime import (
    FEATURE_COMPILER_VERSION,
    FeatureArtifactVerifier,
    FeatureCompileRequest,
    FeatureCompiler,
    FeatureRuntimeViolation,
)
from dehps.input_contracts import (
    FEATURE_GOLDEN_SUITE,
    HistorySnapshotArtifact,
    WindowMode,
    WindowSpec,
)
from dehps.models.frequency_ranker import train_frequency_stats
from dehps.optimization.walk_forward import build_ranked_universe
from dehps.scoring_kernel import candidate_store_from_matrix, pack_window_state
from dehps.scoring_kernel.numpy_backend import component_tile


def _window_and_store(*, with_dates: bool = False):
    golden = FEATURE_GOLDEN_SUITE["golden_vector"]
    dates = (date(2026, 1, 1), date(2026, 1, 4), date(2026, 1, 6), date(2026, 1, 8))
    history = [
        (str(issue), dates[index] if with_dates else None, tuple(int(number) for number in numbers))
        for index, (issue, numbers) in enumerate(golden["history"])
    ]
    snapshot = HistorySnapshotArtifact.from_history(history)
    window = WindowSpec(
        mode=WindowMode.EXPANDING,
        as_of_issue=history[-1][0],
        include_as_of=True,
        size=None,
        target_issue="2026005",
    ).materialize(snapshot)
    candidates = [
        (1, 2, 3, 4, 5, 6),
        tuple(int(number) for number in golden["candidate"]),
        (28, 29, 30, 31, 32, 33),
    ]
    matrix = build_ranked_universe(
        candidates,
        use_cache=False,
        include_hard_filter_exclusions=True,
    )
    return window, candidate_store_from_matrix(matrix)


def test_feature_compiler_matches_reference_and_binds_inputs() -> None:
    window, store = _window_and_store()
    request = FeatureCompileRequest(window=window, candidate_store=store)

    artifact = FeatureCompiler().compile(request)
    history = [record.as_history_draw() for record in window.records]
    reference = component_tile(store, pack_window_state(train_frequency_stats(history)), 0, len(store))

    assert artifact.header.compiler_version == FEATURE_COMPILER_VERSION
    assert artifact.header.window_artifact_digest == window.artifact_digest
    assert artifact.header.candidate_package_digest == store.candidate_abi_package.package_digest
    assert artifact.values.dtype == np.float64
    assert artifact.values.flags.c_contiguous
    assert np.array_equal(artifact.values, reference)
    FeatureArtifactVerifier().verify(artifact, request=request)


def test_feature_compiler_golden_row_is_strictly_stable() -> None:
    window, store = _window_and_store()

    artifact = FeatureCompiler().compile(
        FeatureCompileRequest(window=window, candidate_store=store, start=1, end=2)
    )

    expected = np.asarray(FEATURE_GOLDEN_SUITE["golden_vector"]["values"], dtype=np.float64)
    assert artifact.values.shape == (1, 32)
    assert np.allclose(artifact.values[0], expected, atol=1e-12)


def test_feature_compiler_is_deterministic_for_identical_inputs() -> None:
    window, store = _window_and_store()
    request = FeatureCompileRequest(window=window, candidate_store=store, start=0, end=2)

    first = FeatureCompiler().compile(request)
    second = FeatureCompiler().compile(request)

    assert first.header == second.header
    assert first.artifact_digest == second.artifact_digest
    assert np.array_equal(first.values, second.values)


def test_feature_artifact_verifier_rejects_payload_mutation() -> None:
    window, store = _window_and_store()
    artifact = FeatureCompiler().compile(FeatureCompileRequest(window=window, candidate_store=store))
    artifact.values[0, 0] += 1.0

    with pytest.raises(FeatureRuntimeViolation, match="feature_values_digest_mismatch"):
        FeatureArtifactVerifier().verify(artifact)


def test_feature_artifact_verifier_rejects_dependency_mismatch() -> None:
    window, store = _window_and_store()
    request = FeatureCompileRequest(window=window, candidate_store=store, start=0, end=2)
    artifact = FeatureCompiler().compile(request)
    wrong_header = replace(artifact.header, candidate_package_digest="0" * 64)

    with pytest.raises(FeatureRuntimeViolation, match="feature_candidate_binding_mismatch"):
        FeatureArtifactVerifier().verify(replace(artifact, header=wrong_header), request=request)


def test_feature_artifact_verifier_detects_candidate_static_input_mutation() -> None:
    window, store = _window_and_store()
    request = FeatureCompileRequest(window=window, candidate_store=store)
    artifact = FeatureCompiler().compile(request)
    store.structural_score[0] += 0.125

    with pytest.raises(FeatureRuntimeViolation, match="feature_candidate_static_binding_mismatch"):
        FeatureArtifactVerifier().verify(artifact, request=request)


def test_feature_compiler_rejects_invalid_row_range() -> None:
    window, store = _window_and_store()

    with pytest.raises(FeatureRuntimeViolation, match="invalid_feature_row_range"):
        FeatureCompiler().compile(
            FeatureCompileRequest(window=window, candidate_store=store, start=0, end=len(store) + 1)
        )


def test_target_context_is_explicit_and_changes_artifact_identity() -> None:
    window, store = _window_and_store(with_dates=True)
    tuesday = FeatureCompileRequest(
        window=window,
        candidate_store=store,
        target_draw_date=date(2026, 1, 13),
    )
    thursday = FeatureCompileRequest(
        window=window,
        candidate_store=store,
        target_draw_date=date(2026, 1, 15),
    )

    tuesday_artifact = FeatureCompiler().compile(tuesday)
    thursday_artifact = FeatureCompiler().compile(thursday)

    assert tuesday.target_context_digest != thursday.target_context_digest
    assert tuesday_artifact.artifact_digest != thursday_artifact.artifact_digest
    assert not np.array_equal(tuesday_artifact.values[:, 29], thursday_artifact.values[:, 29])


def test_feature_compiler_rejects_target_date_leakage() -> None:
    window, store = _window_and_store(with_dates=True)

    with pytest.raises(FeatureRuntimeViolation, match="feature_target_date_leakage"):
        FeatureCompiler().compile(
            FeatureCompileRequest(
                window=window,
                candidate_store=store,
                target_draw_date=date(2026, 1, 8),
            )
        )


def test_feature_artifact_is_reference_evidence_not_kernel_state() -> None:
    window, store = _window_and_store()
    artifact = FeatureCompiler().compile(FeatureCompileRequest(window=window, candidate_store=store))

    assert "abi" not in artifact.header.artifact_version
    assert not hasattr(store, "feature_artifact")
