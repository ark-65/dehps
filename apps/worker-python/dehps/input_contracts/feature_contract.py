from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dehps.contracts import ContractRef, canonical_digest
from dehps.input_contracts.candidate_abi import CANDIDATE_CONTRACT_V1
from dehps.input_contracts.history_window import WINDOW_CONTRACT_V1


FEATURE_CONTRACT_VERSION = "feature.v1.0.0"
FEATURE_COMPONENT_DTYPE = "float64"
FEATURE_VECTOR_LENGTH = 32


@dataclass(frozen=True)
class FeatureComponentSpec:
    index: int
    feature_id: str
    weight_field: str
    dtype: str
    shape: tuple[str, ...]
    unit: str
    value_contract: str
    dependencies: tuple[str, ...]
    formula: str
    missing_policy: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "feature_id": self.feature_id,
            "weight_field": self.weight_field,
            "dtype": self.dtype,
            "shape": list(self.shape),
            "unit": self.unit,
            "value_contract": self.value_contract,
            "dependencies": list(self.dependencies),
            "formula": self.formula,
            "missing_policy": self.missing_policy,
        }


def _component(
    index: int,
    feature_id: str,
    weight_field: str,
    dependencies: tuple[str, ...],
    formula: str,
    *,
    unit: str = "score_component",
    value_contract: str = "finite_float64",
    missing_policy: str = "reject_missing_dependency",
) -> FeatureComponentSpec:
    return FeatureComponentSpec(
        index=index,
        feature_id=feature_id,
        weight_field=weight_field,
        dtype=FEATURE_COMPONENT_DTYPE,
        shape=("N",),
        unit=unit,
        value_contract=value_contract,
        dependencies=dependencies,
        formula=formula,
        missing_policy=missing_policy,
    )


FEATURE_COMPONENTS_V1: tuple[FeatureComponentSpec, ...] = (
    _component(0, "structural_score", "structural_weight", ("candidate",), "candidate.static_structural_score"),
    _component(1, "frequency_score", "frequency_weight", ("window", "candidate"), "sum(window.frequency_rate[n] for n in candidate.numbers)"),
    _component(2, "omission_score", "omission_weight", ("window", "candidate"), "mean(window.omission_rate[n] for n in candidate.numbers)"),
    _component(3, "previous_consecutive_score", "previous_consecutive_weight", ("window", "candidate"), "candidate_consecutive_score if previous_consecutive_pair_count>0 else 1-candidate_consecutive_score"),
    _component(4, "previous_overlap_score", "previous_overlap_weight", ("window", "candidate"), "popcount(candidate.mask & window.previous_number_mask)/6"),
    _component(5, "previous_parity_shape_score", "previous_parity_shape_weight", ("window", "candidate"), "1-abs(candidate.odd_count-window.previous_odd_count)/6"),
    _component(6, "dynamic_parity_transition_score", "dynamic_parity_transition_weight", ("window", "candidate"), "window.parity_transition[candidate.even_count]"),
    _component(7, "previous_zone_shape_score", "previous_zone_shape_weight", ("window", "candidate"), "1-sum(abs(candidate.zone_counts-window.previous_zone_counts))/12"),
    _component(8, "recent_neighbor_score", "recent_neighbor_weight", ("window", "candidate"), "mean(window.recent_neighbor_rate[n] for n in candidate.numbers)"),
    _component(9, "lagged_consecutive_score", "lagged_consecutive_weight", ("window", "candidate"), "popcount(candidate.mask & window.lagged_number_mask)/6"),
    _component(10, "recent_gap_shape_score", "recent_gap_shape_weight", ("window", "candidate"), "max(0,1-sum(abs(candidate.gaps-window.recent_average_gaps))/(5*32))"),
    _component(11, "recent_sum_span_score", "recent_sum_span_weight", ("window", "candidate"), "mean(max(0,1-abs(sum-recent_average_sum)/162),max(0,1-abs(span-recent_average_span)/32))"),
    _component(12, "qian_kun_pattern_score", "qian_kun_pattern_weight", ("window", "candidate"), "mean(window.qian_kun_rate[code],max_recent_qian_kun_similarity_if_available)"),
    _component(13, "first_last_sum_score", "first_last_sum_weight", ("window", "candidate"), "window.first_last_sum_rate[candidate.first_last_sum]"),
    _component(14, "span_trend_score", "span_trend_weight", ("window", "candidate"), "window.span_bucket_rate[candidate.span_bucket]"),
    _component(15, "sum_trend_score", "sum_trend_weight", ("window", "candidate"), "window.sum_bucket_rate[candidate.sum_bucket]"),
    _component(16, "ac_trend_score", "ac_trend_weight", ("window", "candidate"), "window.ac_rate[candidate.ac_value]"),
    _component(17, "zone_ratio_score", "zone_ratio_weight", ("window", "candidate"), "window.zone_rate[encode_base7(candidate.zone_counts)]"),
    _component(18, "big_small_ratio_score", "big_small_ratio_weight", ("window", "candidate"), "window.big_count_rate[candidate.big_count]"),
    _component(19, "parity_ratio_score", "parity_ratio_weight", ("window", "candidate"), "window.even_count_rate[candidate.even_count]"),
    _component(20, "prime_composite_score", "prime_composite_weight", ("window", "candidate"), "window.prime_count_rate[candidate.prime_count]"),
    _component(21, "mod012_score", "mod012_weight", ("window", "candidate"), "window.mod012_rate[encode_base7(candidate.mod012_counts)]"),
    _component(22, "tail_distribution_score", "tail_distribution_weight", ("window", "candidate"), "window.tail_unique_rate[candidate.tail_unique_count]"),
    _component(23, "sum_tail_score", "sum_tail_weight", ("window", "candidate"), "window.sum_tail_rate[candidate.sum_tail]"),
    _component(24, "red_omission_shape_score", "red_omission_shape_weight", ("window", "candidate"), "max(0,1-abs(omission_score-window.recent_average_omission))"),
    _component(25, "sum_span_omission_score", "sum_span_omission_weight", ("window", "candidate"), "mean(window.sum_bucket_omission[candidate.sum_bucket],window.span_bucket_omission[candidate.span_bucket])"),
    _component(26, "consecutive_trend_score", "consecutive_trend_weight", ("window", "candidate"), "window.consecutive_rate[candidate.consecutive_pair_count]"),
    _component(27, "repeat_trend_score", "repeat_trend_weight", ("window", "candidate"), "window.repeat_rate[previous_overlap_count]"),
    _component(28, "stable_range_score", "stable_range_weight", ("window", "candidate"), "mean(piecewise_range_membership(candidate.sum,span,ac,first_last_sum,max_gap,min_gap))"),
    _component(29, "weekday_trend_score", "weekday_trend_weight", ("window", "candidate"), "mean(13 weekday profile lookups) if weekday enabled else 0"),
    _component(30, "short_hot_frequency_score", "short_hot_frequency_weight", ("window", "candidate"), "mean(window.recent_frequency_rate[n] for n in candidate.numbers)"),
    _component(31, "long_omission_cooldown_score", "long_omission_cooldown_weight", ("window", "candidate"), "clip(1-mean(window.recent_omission_pressure[n]^1.5),0,1)"),
)


def feature_component_manifest() -> dict[str, Any]:
    return {
        "contract": FEATURE_CONTRACT_VERSION,
        "vector_length": FEATURE_VECTOR_LENGTH,
        "dtype": FEATURE_COMPONENT_DTYPE,
        "layout": {
            "organization": "component_vector",
            "axis_0": "candidate_row",
            "axis_1": "feature_component_index",
            "shape": ["N", FEATURE_VECTOR_LENGTH],
            "order": "C",
        },
        "dependencies": {
            "window_contract": WINDOW_CONTRACT_V1.as_dict(),
            "candidate_contract": CANDIDATE_CONTRACT_V1.as_dict(),
        },
        "components": [component.as_dict() for component in FEATURE_COMPONENTS_V1],
    }


FEATURE_COMPONENT_MANIFEST_DIGEST = canonical_digest(
    feature_component_manifest(),
    domain="dehps.feature-component-manifest.v1",
)

FEATURE_NORMATIVE_DEFINITION = {
    "contract": FEATURE_CONTRACT_VERSION,
    "feature_function": "Feature = F(WindowArtifact, CandidateABIPackage)",
    "kernel_boundary": "kernel_consumes_compiled_feature_abi_not_feature_names_or_formulas",
    "component_manifest_digest": FEATURE_COMPONENT_MANIFEST_DIGEST,
    "component_count": FEATURE_VECTOR_LENGTH,
    "dtype": FEATURE_COMPONENT_DTYPE,
    "nan_policy": "reject_nan_and_infinite_values",
    "ordering": "component_index_is_stable_and_weight_field_mapping_is_normative",
    "dependencies": {
        "window_contract": WINDOW_CONTRACT_V1.normative_identity(),
        "candidate_contract": CANDIDATE_CONTRACT_V1.normative_identity(),
    },
    "non_goals": [
        "no_feature_abi_layout",
        "no_kernel_runtime_migration",
        "no_formula_change",
        "no_weight_change",
    ],
}

FEATURE_GOLDEN_SUITE = {
    "suite": "feature_contract_golden.v1",
    "component_count": FEATURE_VECTOR_LENGTH,
    "dtype": FEATURE_COMPONENT_DTYPE,
    "component_ids": [component.feature_id for component in FEATURE_COMPONENTS_V1],
    "weight_fields": [component.weight_field for component in FEATURE_COMPONENTS_V1],
    "component_manifest_digest": FEATURE_COMPONENT_MANIFEST_DIGEST,
    "golden_vector": {
        "history": [
            ["2026001", [1, 2, 3, 4, 5, 6]],
            ["2026002", [3, 8, 12, 18, 25, 33]],
            ["2026003", [5, 9, 14, 19, 24, 29]],
            ["2026004", [6, 11, 16, 21, 26, 31]],
        ],
        "candidate": [3, 8, 12, 18, 25, 33],
        "shape": [1, FEATURE_VECTOR_LENGTH],
        "dtype": FEATURE_COMPONENT_DTYPE,
        "values": [
            0.675,
            0.291666666667,
            0.5,
            1.0,
            0.0,
            1.0,
            1.0,
            1.0,
            0.310606060606,
            0.0,
            0.94375,
            0.809220679012,
            1.0,
            1.0,
            0.5,
            1.0,
            0.5,
            1.0,
            1.0,
            1.0,
            0.5,
            0.5,
            1.0,
            0.5,
            0.8125,
            0.5,
            1.0,
            1.0,
            1.0,
            0.0,
            0.291666666667,
            0.993914193805,
        ],
    },
}

FEATURE_CONTRACT_V1 = ContractRef.from_definition(
    family="feature",
    semantic_version="1.0.0",
    schema_version="dehps.feature.schema.v1",
    normative_definition=FEATURE_NORMATIVE_DEFINITION,
    golden_suite=FEATURE_GOLDEN_SUITE,
)


class FeatureContractViolation(ValueError):
    pass


class FeatureContractVerifier:
    def verify_manifest(self, manifest: dict[str, Any] | None = None) -> None:
        payload = feature_component_manifest() if manifest is None else manifest
        components = payload.get("components")
        if not isinstance(components, list) or len(components) != FEATURE_VECTOR_LENGTH:
            raise FeatureContractViolation("feature manifest must contain 32 components")
        seen_ids: set[str] = set()
        seen_weights: set[str] = set()
        for expected_index, component in enumerate(components):
            if component.get("index") != expected_index:
                raise FeatureContractViolation("feature component indexes must be contiguous")
            feature_id = component.get("feature_id")
            weight_field = component.get("weight_field")
            if not isinstance(feature_id, str) or feature_id in seen_ids:
                raise FeatureContractViolation("feature_id must be unique")
            if not isinstance(weight_field, str) or weight_field in seen_weights:
                raise FeatureContractViolation("weight_field must be unique")
            if component.get("dtype") != FEATURE_COMPONENT_DTYPE:
                raise FeatureContractViolation("feature component dtype must be float64")
            if component.get("shape") != ["N"]:
                raise FeatureContractViolation("feature component shape must be [N]")
            if component.get("value_contract") != "finite_float64":
                raise FeatureContractViolation("feature components must reject non-finite values")
            seen_ids.add(feature_id)
            seen_weights.add(weight_field)
        digest = canonical_digest(payload, domain="dehps.feature-component-manifest.v1")
        if digest != FEATURE_COMPONENT_MANIFEST_DIGEST:
            raise FeatureContractViolation("feature component manifest digest mismatch")
