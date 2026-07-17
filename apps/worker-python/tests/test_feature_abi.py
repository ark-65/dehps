from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from dehps.feature_runtime import (
    FEATURE_ABI_GOLDEN_SUITE,
    FEATURE_ABI_LAYOUT_DEFINITION,
    FEATURE_ABI_LAYOUT_DIGEST,
    FEATURE_ABI_VERSION,
    FeatureABICompiler,
    FeatureABIVerifier,
    FeatureCompileRequest,
    FeatureCompiler,
    FeatureRuntimeViolation,
)
from dehps.feature_runtime.compiler import (
    FEATURE_ARTIFACT_VERSION,
    FEATURE_COMPILER_VERSION,
    CompiledFeatureArtifact,
    FeatureArtifactHeader,
    feature_array_digest,
)
from dehps.input_contracts import (
    FEATURE_COMPONENT_MANIFEST_DIGEST,
    FEATURE_CONTRACT_V1,
    FEATURE_GOLDEN_SUITE,
    FEATURE_VECTOR_LENGTH,
    HistorySnapshotArtifact,
    WindowMode,
    WindowSpec,
)
from dehps.optimization.walk_forward import build_ranked_universe
from dehps.scoring_kernel import candidate_store_from_matrix


def _runtime_inputs():
    golden = FEATURE_GOLDEN_SUITE["golden_vector"]
    history = [
        (str(issue), tuple(int(number) for number in numbers))
        for issue, numbers in golden["history"]
    ]
    snapshot = HistorySnapshotArtifact.from_history(history)
    window = WindowSpec(
        mode=WindowMode.EXPANDING,
        as_of_issue=history[-1][0],
        include_as_of=True,
        size=None,
        target_issue="2026005",
    ).materialize(snapshot)
    matrix = build_ranked_universe(
        [
            (1, 2, 3, 4, 5, 6),
            tuple(int(number) for number in golden["candidate"]),
            (28, 29, 30, 31, 32, 33),
        ],
        use_cache=False,
        include_hard_filter_exclusions=True,
    )
    return window, candidate_store_from_matrix(matrix)


def _golden_source_artifact() -> CompiledFeatureArtifact:
    case = FEATURE_ABI_GOLDEN_SUITE["buffer_case"]
    values = np.asarray(
        [FEATURE_GOLDEN_SUITE["golden_vector"]["values"]],
        dtype=np.dtype("<f8"),
    )
    source = case["source_digests"]
    header = FeatureArtifactHeader(
        artifact_version=FEATURE_ARTIFACT_VERSION,
        compiler_version=FEATURE_COMPILER_VERSION,
        feature_contract=FEATURE_CONTRACT_V1,
        component_manifest_digest=FEATURE_COMPONENT_MANIFEST_DIGEST,
        window_artifact_digest=source["window_artifact_digest"],
        candidate_package_digest=source["candidate_package_digest"],
        candidate_static_digest=source["candidate_static_digest"],
        target_context_digest=source["target_context_digest"],
        start=0,
        end=1,
        row_count=1,
        component_count=FEATURE_VECTOR_LENGTH,
        dtype="float64",
        values_digest=feature_array_digest(values, domain="dehps.feature-artifact.values.v1"),
    )
    return CompiledFeatureArtifact(header=header, values=values)


def test_feature_abi_layout_is_frozen_and_manifest_bound() -> None:
    values = FEATURE_ABI_LAYOUT_DEFINITION["buffers"]["values"]

    assert FEATURE_ABI_VERSION == "feature_abi.v1"
    assert FEATURE_ABI_GOLDEN_SUITE["expected_layout_digest"] == FEATURE_ABI_LAYOUT_DIGEST
    assert FEATURE_ABI_LAYOUT_DEFINITION["component_axis"]["component_manifest_digest"] == (
        FEATURE_COMPONENT_MANIFEST_DIGEST
    )
    assert values == {
        "dtype": "float64",
        "endianness": "little",
        "shape": ["R", 32],
        "strides_bytes": {"nonempty": [256, 8], "empty": [0, 0]},
        "order": "C",
        "alignment": 8,
        "finite_values": "required",
    }


def test_feature_abi_compiler_wraps_reference_artifact_without_copy() -> None:
    window, store = _runtime_inputs()
    artifact = FeatureCompiler().compile(
        FeatureCompileRequest(window=window, candidate_store=store)
    )

    package = FeatureABICompiler().compile(artifact)

    assert package.values is artifact.values
    assert np.shares_memory(package.values, artifact.values)
    assert package.header.start == 0
    assert package.header.end == len(store)
    assert package.header.buffer.shape == (len(store), 32)
    assert package.header.buffer.strides == (256, 8)
    assert package.runtime_envelope.feature_abi == FEATURE_ABI_VERSION
    assert package.runtime_envelope.candidate_package_digest == (
        store.candidate_abi_package.package_digest
    )
    FeatureABIVerifier().verify(package, source_artifact=artifact)


def test_feature_abi_golden_digests_are_cross_implementation_oracles() -> None:
    artifact = _golden_source_artifact()
    package = FeatureABICompiler().compile(artifact)
    case = FEATURE_ABI_GOLDEN_SUITE["buffer_case"]

    assert package.header.buffer.buffer_digest == case["expected_buffer_digest"]
    assert package.header.payload_digest == case["expected_payload_digest"]
    assert package.header.header_digest == case["expected_header_digest"]
    assert package.package_digest == case["expected_package_digest"]


def test_feature_abi_is_deterministic_for_same_source_artifact() -> None:
    artifact = _golden_source_artifact()

    first = FeatureABICompiler().compile(artifact)
    second = FeatureABICompiler().compile(artifact)

    assert first.header == second.header
    assert first.package_digest == second.package_digest
    assert np.array_equal(first.values, second.values)


def test_feature_abi_verifier_rejects_payload_mutation() -> None:
    package = FeatureABICompiler().compile(_golden_source_artifact())
    package.values[0, 0] += 0.25

    with pytest.raises(FeatureRuntimeViolation, match="feature_abi_buffer_metadata_mismatch"):
        FeatureABIVerifier().verify(package)


def test_feature_abi_verifier_rejects_layout_and_buffer_drift() -> None:
    package = FeatureABICompiler().compile(_golden_source_artifact())
    wrong_layout = replace(package.header, layout_digest="0" * 64)

    with pytest.raises(FeatureRuntimeViolation, match="feature_abi_layout_mismatch"):
        FeatureABIVerifier().verify(replace(package, header=wrong_layout))

    non_contiguous = package.values[:, ::-1]
    with pytest.raises(FeatureRuntimeViolation, match="feature_abi_buffer_not_contiguous"):
        FeatureABIVerifier().verify(replace(package, values=non_contiguous))


def test_feature_abi_verifier_rejects_wrong_source_binding() -> None:
    window, store = _runtime_inputs()
    first = FeatureCompiler().compile(
        FeatureCompileRequest(window=window, candidate_store=store, start=0, end=1)
    )
    second = FeatureCompiler().compile(
        FeatureCompileRequest(window=window, candidate_store=store, start=1, end=2)
    )
    package = FeatureABICompiler().compile(first)

    with pytest.raises(FeatureRuntimeViolation, match="feature_abi_source_binding_mismatch"):
        FeatureABIVerifier().verify(package, source_artifact=second)


def test_feature_abi_tile_boundaries_do_not_change_component_values() -> None:
    window, store = _runtime_inputs()
    full = FeatureCompiler().compile(
        FeatureCompileRequest(window=window, candidate_store=store)
    )
    left = FeatureCompiler().compile(
        FeatureCompileRequest(window=window, candidate_store=store, start=0, end=1)
    )
    right = FeatureCompiler().compile(
        FeatureCompileRequest(window=window, candidate_store=store, start=1, end=3)
    )

    full_package = FeatureABICompiler().compile(full)
    left_package = FeatureABICompiler().compile(left)
    right_package = FeatureABICompiler().compile(right)

    assert np.array_equal(
        full_package.values,
        np.concatenate((left_package.values, right_package.values), axis=0),
    )
    assert full_package.package_digest != left_package.package_digest


def test_feature_abi_has_a_canonical_empty_tile_layout() -> None:
    source = _golden_source_artifact()
    values = np.empty((0, FEATURE_VECTOR_LENGTH), dtype=np.dtype("<f8"))
    header = replace(
        source.header,
        start=0,
        end=0,
        row_count=0,
        values_digest=feature_array_digest(values, domain="dehps.feature-artifact.values.v1"),
    )
    artifact = CompiledFeatureArtifact(header=header, values=values)

    package = FeatureABICompiler().compile(artifact)

    assert package.values.strides == (0, 0)
    assert package.header.buffer.strides == (0, 0)
    FeatureABIVerifier().verify(package, source_artifact=artifact)
