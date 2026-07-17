from __future__ import annotations

import numpy as np
import pytest

from dehps.input_contracts import (
    FEATURE_COMPONENT_MANIFEST_DIGEST,
    FEATURE_COMPONENTS_V1,
    FEATURE_CONTRACT_V1,
    FEATURE_CONTRACT_VERSION,
    FEATURE_GOLDEN_SUITE,
    FEATURE_VECTOR_LENGTH,
    FeatureContractVerifier,
    FeatureContractViolation,
    feature_component_manifest,
)
from dehps.models.frequency_ranker import train_frequency_stats
from dehps.optimization.walk_forward import CONFIG_WEIGHT_FIELDS, build_ranked_universe
from dehps.scoring_kernel import candidate_store_from_matrix, pack_window_state
from dehps.scoring_kernel.numpy_backend import COMPONENT_COUNT, component_tile


def test_feature_contract_freezes_component_order_and_weight_mapping() -> None:
    assert FEATURE_CONTRACT_V1.key == FEATURE_CONTRACT_VERSION
    assert FEATURE_VECTOR_LENGTH == COMPONENT_COUNT == 32
    assert tuple(component.index for component in FEATURE_COMPONENTS_V1) == tuple(range(32))
    assert tuple(component.weight_field for component in FEATURE_COMPONENTS_V1) == CONFIG_WEIGHT_FIELDS
    assert len({component.feature_id for component in FEATURE_COMPONENTS_V1}) == 32
    assert len({component.weight_field for component in FEATURE_COMPONENTS_V1}) == 32


def test_feature_manifest_carries_dependencies_dtype_shape_and_digest() -> None:
    manifest = feature_component_manifest()

    FeatureContractVerifier().verify_manifest(manifest)
    assert manifest["contract"] == FEATURE_CONTRACT_VERSION
    assert manifest["vector_length"] == 32
    assert manifest["dtype"] == "float64"
    assert manifest["layout"]["shape"] == ["N", 32]
    assert manifest["dependencies"]["window_contract"]["contract_key"] == "window.v1.0.0"
    assert manifest["dependencies"]["candidate_contract"]["contract_key"] == "candidate.v1.0.0"
    assert FEATURE_GOLDEN_SUITE["component_manifest_digest"] == FEATURE_COMPONENT_MANIFEST_DIGEST


def test_feature_contract_rejects_manifest_drift() -> None:
    manifest = feature_component_manifest()
    manifest["components"][0] = {
        **manifest["components"][0],
        "feature_id": manifest["components"][1]["feature_id"],
    }

    with pytest.raises(FeatureContractViolation, match="feature_id must be unique"):
        FeatureContractVerifier().verify_manifest(manifest)


def test_feature_component_specs_reject_non_finite_value_policy_drift() -> None:
    manifest = feature_component_manifest()
    manifest["components"][0] = {
        **manifest["components"][0],
        "value_contract": "allow_nan",
    }

    with pytest.raises(FeatureContractViolation, match="reject non-finite"):
        FeatureContractVerifier().verify_manifest(manifest)


def test_feature_golden_vector_matches_current_reference_component_tile() -> None:
    golden = FEATURE_GOLDEN_SUITE["golden_vector"]
    history = [
        (str(issue), tuple(int(number) for number in numbers))
        for issue, numbers in golden["history"]
    ]
    candidate = tuple(int(number) for number in golden["candidate"])
    matrix = build_ranked_universe(
        [candidate],
        use_cache=False,
        include_hard_filter_exclusions=True,
    )
    stats = train_frequency_stats(history)
    store = candidate_store_from_matrix(matrix)
    state = pack_window_state(stats)

    actual = component_tile(store, state, 0, 1)

    assert actual.dtype == np.float64
    assert actual.shape == (1, FEATURE_VECTOR_LENGTH)
    assert np.allclose(actual[0], np.asarray(golden["values"], dtype=np.float64), atol=1e-12)

