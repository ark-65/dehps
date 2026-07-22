from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from functools import reduce
from itertools import combinations
from math import comb, gcd
from typing import Any

from dehps.contracts import ContractRef, canonical_digest
from dehps.seven_red.diversity import (
    SEVEN_RED_DIVERSITY_AUDIT_CONTRACT_V1,
    SevenRedDiversityAuditSnapshot,
    SevenRedGeometryMetrics,
)
from dehps.seven_red.domain import (
    LINE_KEY,
    RESEARCH_ONLY,
    SevenRedCandidate,
    expand_seven_red_candidate,
)
from dehps.seven_red.raw_top10 import (
    RAW_TOP10_RANKING_CONTRACT,
    ScoredSevenRedCandidate,
)


DIVERSIFIED_TOP10_SIZE = 10
DIVERSIFIED_TOP10_SNAPSHOT_VERSION = "seven_red_diversified_top10_snapshot.v1"
DIVERSIFIED_TOP10_SELECTOR_CONTRACT = (
    "seven_red_diversified_top10.exact_fraction_greedy_unique70.v1"
)
WEIGHT_FIELDS = (
    "source_quality_weight",
    "pair_coverage_weight",
    "triple_coverage_weight",
    "exposure_balance_weight",
)

PAIR_COVERAGE_DENOMINATOR = min(comb(33, 2), DIVERSIFIED_TOP10_SIZE * comb(7, 2))
TRIPLE_COVERAGE_DENOMINATOR = min(
    comb(33, 3),
    DIVERSIFIED_TOP10_SIZE * comb(7, 3),
)
EXPOSURE_SQUARE_DENOMINATOR = (DIVERSIFIED_TOP10_SIZE * 7) ** 2

SEVEN_RED_DIVERSIFIED_NORMATIVE_DEFINITION = {
    "contract": "seven-red-diversified-top10.v1.0.0",
    "line_key": LINE_KEY,
    "research_only": RESEARCH_ONLY,
    "dependencies": {
        "seven_red_diversity_audit": (
            SEVEN_RED_DIVERSITY_AUDIT_CONTRACT_V1.normative_identity()
        ),
    },
    "configuration": {
        "fields": list(WEIGHT_FIELDS),
        "type": "explicit_non_negative_integers",
        "canonical_scale": "greatest_common_divisor_of_nonzero_vector_equals_one",
        "all_zero": "forbidden",
        "default": "absent",
        "recommendation": "absent",
    },
    "source_rank": {
        "contract": RAW_TOP10_RANKING_CONTRACT,
        "quality": "q=(N-source_rank+1)/N_as_exact_fraction",
        "stored_score_mutation": "forbidden",
    },
    "set_utility": {
        "budget": DIVERSIFIED_TOP10_SIZE,
        "arithmetic": "exact_rational",
        "quality": "wq*sum(q)/B",
        "pair_coverage": "w2*unique_pair_cores/min(C(33,2),21B)",
        "triple_coverage": "w3*unique_triple_cores/min(C(33,3),35B)",
        "exposure_penalty": "-we*sum(number_occurrence_squared)/(7B)^2",
        "total": "quality+pair_coverage+triple_coverage+exposure_penalty",
    },
    "greedy_selection": {
        "candidate_feasibility": "adds_exactly_seven_previously_unseen_six_red_expansions",
        "primary_order": "largest_exact_marginal_total_utility",
        "tie_breaks": ["higher_exact_source_quality", "lower_seven_red_lex_id"],
        "selection_order": "marginal_choice_order",
        "infeasible_completion": "fail_closed_without_partial_snapshot",
        "global_optimality": "not_claimed",
    },
    "output": {
        "size": DIVERSIFIED_TOP10_SIZE,
        "unique_expansion_slots": 70,
        "step_evidence": "exact_marginal_and_cumulative_component_fractions",
        "final_geometry": "seven_red_diversity_audit_metrics",
        "identity": "source_audit_config_steps_rows_and_final_geometry_digest",
        "seed": "absent",
        "outcome_input": "forbidden",
    },
    "non_goals": [
        "no_default_or_trained_weights",
        "no_global_optimality",
        "no_random_or_alternative_selector",
        "no_candidate_scoring_or_generation",
        "no_walk_forward_or_statistical_claim",
        "no_production_integration",
    ],
}

SEVEN_RED_DIVERSIFIED_GOLDEN_SUITE = {
    "suite": "seven_red_diversified_top10_golden.v1",
    "source_candidates": [
        [1, 2, 3, 4, 5, 6, 7],
        [1, 2, 3, 4, 5, 6, 8],
        [1, 2, 3, 4, 5, 6, 9],
        [1, 2, 3, 4, 5, 6, 10],
        [1, 2, 3, 4, 11, 12, 13],
        [1, 2, 3, 5, 14, 15, 16],
        [1, 2, 4, 5, 17, 18, 19],
        [1, 3, 4, 5, 20, 21, 22],
        [2, 3, 4, 5, 23, 24, 25],
        [1, 2, 3, 26, 27, 28, 29],
        [4, 5, 6, 26, 30, 31, 32],
        [7, 8, 9, 10, 11, 12, 13],
        [14, 15, 16, 17, 18, 19, 20],
        [21, 22, 23, 24, 25, 26, 27],
        [1, 8, 14, 21, 28, 32, 33],
        [2, 9, 15, 22, 29, 30, 33],
    ],
    "normalized_scores_descending": [
        0.99,
        0.98,
        0.97,
        0.96,
        0.90,
        0.89,
        0.88,
        0.87,
        0.86,
        0.85,
        0.84,
        0.83,
        0.82,
        0.81,
        0.80,
        0.79,
    ],
    "weights": {
        "source_quality_weight": 1,
        "pair_coverage_weight": 1,
        "triple_coverage_weight": 1,
        "exposure_balance_weight": 1,
    },
    "expected_selected_lex_ids": [
        0,
        1883,
        5790,
        27335,
        2253759,
        30001,
        4270332,
        3384018,
        172823,
        716958,
    ],
    "expected_configuration_digest": (
        "3fff1bf6e92ab83a43d2a363ebb196a8b71b3dbe2b2e6f600dfa39ab93f22a15"
    ),
    "expected_snapshot_digest": (
        "df94359201cd9f431da5880fe17a222b70b098812c3c82ef28dbec947ac567cf"
    ),
    "stochastic": False,
}

SEVEN_RED_DIVERSIFIED_TOP10_CONTRACT_V1 = ContractRef.from_definition(
    family="seven-red-diversified-top10",
    semantic_version="1.0.0",
    schema_version="dehps.seven-red-diversified-top10.schema.v1",
    normative_definition=SEVEN_RED_DIVERSIFIED_NORMATIVE_DEFINITION,
    golden_suite=SEVEN_RED_DIVERSIFIED_GOLDEN_SUITE,
)


class SevenRedDiversifiedTop10Violation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _reject(code: str, message: str, **context: Any) -> None:
    raise SevenRedDiversifiedTop10Violation(code, message, **context)


def _fraction_payload(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _require_fraction(value: object, *, field_name: str) -> Fraction:
    if type(value) is not Fraction:
        _reject(
            "seven_red_diversified_fraction_invalid",
            f"{field_name} must use the canonical Fraction representation",
            field=field_name,
        )
    return value


@dataclass(frozen=True)
class SevenRedDiversificationWeights:
    source_quality_weight: int
    pair_coverage_weight: int
    triple_coverage_weight: int
    exposure_balance_weight: int
    configuration_digest: str = field(init=False)

    def __post_init__(self) -> None:
        values = tuple(getattr(self, name) for name in WEIGHT_FIELDS)
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in values
        ):
            _reject(
                "seven_red_diversified_weight_invalid",
                "all weights must be canonical non-negative integers",
            )
        if not any(values):
            _reject(
                "seven_red_diversified_weight_vector_zero",
                "at least one weight must be positive",
            )
        if reduce(gcd, values) != 1:
            _reject(
                "seven_red_diversified_weight_vector_nonprimitive",
                "weight vector must have greatest common divisor one",
            )
        object.__setattr__(
            self,
            "configuration_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.diversified-top10-config.v1",
            ),
        )

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, object],
    ) -> SevenRedDiversificationWeights:
        if not isinstance(values, Mapping):
            _reject(
                "seven_red_diversified_weight_mapping_invalid",
                "weight configuration must be a mapping",
            )
        actual = set(values)
        expected = set(WEIGHT_FIELDS)
        if actual != expected:
            _reject(
                "seven_red_diversified_weight_fields_invalid",
                "weight configuration fields must match the frozen contract exactly",
                missing=sorted(expected - actual, key=str),
                unexpected=sorted(actual - expected, key=str),
            )
        return cls(**{name: values[name] for name in WEIGHT_FIELDS})  # type: ignore[arg-type]

    def identity_payload(self) -> dict[str, Any]:
        return {
            "selector_contract": DIVERSIFIED_TOP10_SELECTOR_CONTRACT,
            **{name: getattr(self, name) for name in WEIGHT_FIELDS},
            "canonical_scale": "primitive_integer_vector_gcd_1",
            "default_policy": None,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "configuration_digest": self.configuration_digest,
        }


@dataclass(frozen=True)
class ExactUtilityComponents:
    source_quality: Fraction
    pair_coverage: Fraction
    triple_coverage: Fraction
    exposure_penalty: Fraction
    total: Fraction

    def __post_init__(self) -> None:
        for field_name in (
            "source_quality",
            "pair_coverage",
            "triple_coverage",
            "exposure_penalty",
            "total",
        ):
            _require_fraction(getattr(self, field_name), field_name=field_name)
        if self.source_quality < 0 or self.pair_coverage < 0 or self.triple_coverage < 0:
            _reject(
                "seven_red_diversified_utility_sign_invalid",
                "quality and coverage utility components must be non-negative",
            )
        if self.exposure_penalty > 0:
            _reject(
                "seven_red_diversified_utility_sign_invalid",
                "exposure penalty must be non-positive",
            )
        if self.total != (
            self.source_quality
            + self.pair_coverage
            + self.triple_coverage
            + self.exposure_penalty
        ):
            _reject(
                "seven_red_diversified_utility_total_mismatch",
                "utility total must equal the exact component sum",
            )

    @classmethod
    def from_terms(
        cls,
        *,
        source_quality: Fraction,
        pair_coverage: Fraction,
        triple_coverage: Fraction,
        exposure_penalty: Fraction,
    ) -> ExactUtilityComponents:
        return cls(
            source_quality=source_quality,
            pair_coverage=pair_coverage,
            triple_coverage=triple_coverage,
            exposure_penalty=exposure_penalty,
            total=(
                source_quality
                + pair_coverage
                + triple_coverage
                + exposure_penalty
            ),
        )

    def minus(self, other: ExactUtilityComponents) -> ExactUtilityComponents:
        return ExactUtilityComponents.from_terms(
            source_quality=self.source_quality - other.source_quality,
            pair_coverage=self.pair_coverage - other.pair_coverage,
            triple_coverage=self.triple_coverage - other.triple_coverage,
            exposure_penalty=self.exposure_penalty - other.exposure_penalty,
        )

    def identity_payload(self) -> dict[str, dict[str, int]]:
        return {
            field_name: _fraction_payload(getattr(self, field_name))
            for field_name in (
                "source_quality",
                "pair_coverage",
                "triple_coverage",
                "exposure_penalty",
                "total",
            )
        }


@dataclass(frozen=True)
class DiversifiedSevenRedTop10Step:
    diversified_rank: int
    source_rank: int
    scored_candidate: ScoredSevenRedCandidate
    source_quality: Fraction
    new_pair_core_count: int
    new_triple_core_count: int
    new_expansion_count: int
    number_square_increment: int
    marginal_utility: ExactUtilityComponents
    cumulative_utility: ExactUtilityComponents

    def __post_init__(self) -> None:
        for field_name, upper in (
            ("diversified_rank", DIVERSIFIED_TOP10_SIZE),
            ("source_rank", None),
        ):
            value = getattr(self, field_name)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 1
                or (upper is not None and value > upper)
            ):
                _reject(
                    "seven_red_diversified_rank_invalid",
                    f"{field_name} is outside the canonical range",
                    field=field_name,
                )
        if not isinstance(self.scored_candidate, ScoredSevenRedCandidate):
            _reject(
                "seven_red_diversified_row_invalid",
                "selection step must bind a ScoredSevenRedCandidate",
            )
        _require_fraction(self.source_quality, field_name="source_quality")
        if not 0 < self.source_quality <= 1:
            _reject(
                "seven_red_diversified_source_quality_invalid",
                "source quality must be an exact fraction in (0,1]",
            )
        for field_name in (
            "new_pair_core_count",
            "new_triple_core_count",
            "new_expansion_count",
            "number_square_increment",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                _reject(
                    "seven_red_diversified_step_count_invalid",
                    f"{field_name} must be a non-negative integer",
                    field=field_name,
                )
        if self.new_pair_core_count > 21 or self.new_triple_core_count > 35:
            _reject(
                "seven_red_diversified_step_core_gain_invalid",
                "step core gains exceed one seven-red candidate",
            )
        if self.new_expansion_count != 7:
            _reject(
                "seven_red_diversified_step_expansion_gain_invalid",
                "every selected candidate must add exactly seven unique expansions",
            )
        if not isinstance(self.marginal_utility, ExactUtilityComponents) or not isinstance(
            self.cumulative_utility,
            ExactUtilityComponents,
        ):
            _reject(
                "seven_red_diversified_step_utility_invalid",
                "step utilities must use exact canonical components",
            )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "diversified_rank": self.diversified_rank,
            "source_rank": self.source_rank,
            "source_quality": _fraction_payload(self.source_quality),
            "row": self.scored_candidate.as_dict(),
            "new_pair_core_count": self.new_pair_core_count,
            "new_triple_core_count": self.new_triple_core_count,
            "new_expansion_count": self.new_expansion_count,
            "number_square_increment": self.number_square_increment,
            "marginal_utility": self.marginal_utility.identity_payload(),
            "cumulative_utility": self.cumulative_utility.identity_payload(),
        }


def _ranked_source_rows(
    source_audit: SevenRedDiversityAuditSnapshot,
) -> tuple[ScoredSevenRedCandidate, ...]:
    return tuple(
        sorted(
            source_audit.source_candidate_pool.rows,
            key=lambda row: (-row.ranking_score, row.candidate.lex_id),
        )
    )


def _candidate_expansion_ids(candidate: SevenRedCandidate) -> frozenset[str]:
    return frozenset(
        expansion.six_red.combination_id
        for expansion in expand_seven_red_candidate(candidate)
    )


def _core_set(
    selected: Sequence[ScoredSevenRedCandidate],
    *,
    core_size: int,
) -> set[tuple[int, ...]]:
    return {
        core
        for row in selected
        for core in combinations(row.candidate.sorted_red_numbers, core_size)
    }


def _number_square_sum(selected: Sequence[ScoredSevenRedCandidate]) -> int:
    counts = Counter(
        number
        for row in selected
        for number in row.candidate.sorted_red_numbers
    )
    return sum(count * count for count in counts.values())


def _set_utility(
    selected: Sequence[ScoredSevenRedCandidate],
    *,
    source_ranks: Mapping[str, int],
    source_count: int,
    weights: SevenRedDiversificationWeights,
) -> ExactUtilityComponents:
    quality_sum = sum(
        (
            Fraction(
                source_count - source_ranks[row.candidate.candidate_id] + 1,
                source_count,
            )
            for row in selected
        ),
        start=Fraction(0),
    )
    quality = (
        weights.source_quality_weight
        * quality_sum
        / DIVERSIFIED_TOP10_SIZE
    )
    pair_coverage = Fraction(
        weights.pair_coverage_weight * len(_core_set(selected, core_size=2)),
        PAIR_COVERAGE_DENOMINATOR,
    )
    triple_coverage = Fraction(
        weights.triple_coverage_weight * len(_core_set(selected, core_size=3)),
        TRIPLE_COVERAGE_DENOMINATOR,
    )
    exposure_penalty = Fraction(
        -weights.exposure_balance_weight * _number_square_sum(selected),
        EXPOSURE_SQUARE_DENOMINATOR,
    )
    return ExactUtilityComponents.from_terms(
        source_quality=quality,
        pair_coverage=pair_coverage,
        triple_coverage=triple_coverage,
        exposure_penalty=exposure_penalty,
    )


def _greedy_steps(
    source_audit: SevenRedDiversityAuditSnapshot,
    weights: SevenRedDiversificationWeights,
) -> tuple[DiversifiedSevenRedTop10Step, ...]:
    ranked_rows = _ranked_source_rows(source_audit)
    source_count = len(ranked_rows)
    source_ranks = {
        row.candidate.candidate_id: rank
        for rank, row in enumerate(ranked_rows, start=1)
    }
    expansion_ids = {
        row.candidate.candidate_id: _candidate_expansion_ids(row.candidate)
        for row in ranked_rows
    }
    selected: list[ScoredSevenRedCandidate] = []
    selected_ids: set[str] = set()
    used_expansions: set[str] = set()
    steps: list[DiversifiedSevenRedTop10Step] = []
    cumulative = _set_utility(
        (),
        source_ranks=source_ranks,
        source_count=source_count,
        weights=weights,
    )
    for diversified_rank in range(1, DIVERSIFIED_TOP10_SIZE + 1):
        feasible: list[
            tuple[
                Fraction,
                Fraction,
                int,
                ScoredSevenRedCandidate,
                ExactUtilityComponents,
                ExactUtilityComponents,
            ]
        ] = []
        for row in ranked_rows:
            candidate_id = row.candidate.candidate_id
            if candidate_id in selected_ids or expansion_ids[candidate_id] & used_expansions:
                continue
            after = _set_utility(
                (*selected, row),
                source_ranks=source_ranks,
                source_count=source_count,
                weights=weights,
            )
            marginal = after.minus(cumulative)
            quality = Fraction(
                source_count - source_ranks[candidate_id] + 1,
                source_count,
            )
            feasible.append(
                (
                    marginal.total,
                    quality,
                    -row.candidate.lex_id,
                    row,
                    marginal,
                    after,
                )
            )
        if not feasible:
            _reject(
                "seven_red_diversified_infeasible_pool",
                "greedy selector cannot complete ten expansion-compatible candidates",
                selected_count=len(selected),
                required=DIVERSIFIED_TOP10_SIZE,
                source_count=source_count,
                configuration_digest=weights.configuration_digest,
            )
        _, quality, _, chosen, marginal, after = max(
            feasible,
            key=lambda item: (item[0], item[1], item[2]),
        )
        prior_pairs = len(_core_set(selected, core_size=2))
        prior_triples = len(_core_set(selected, core_size=3))
        prior_square_sum = _number_square_sum(selected)
        selected.append(chosen)
        selected_ids.add(chosen.candidate.candidate_id)
        used_expansions.update(expansion_ids[chosen.candidate.candidate_id])
        steps.append(
            DiversifiedSevenRedTop10Step(
                diversified_rank=diversified_rank,
                source_rank=source_ranks[chosen.candidate.candidate_id],
                scored_candidate=chosen,
                source_quality=quality,
                new_pair_core_count=(
                    len(_core_set(selected, core_size=2)) - prior_pairs
                ),
                new_triple_core_count=(
                    len(_core_set(selected, core_size=3)) - prior_triples
                ),
                new_expansion_count=len(expansion_ids[chosen.candidate.candidate_id]),
                number_square_increment=(
                    _number_square_sum(selected) - prior_square_sum
                ),
                marginal_utility=marginal,
                cumulative_utility=after,
            )
        )
        cumulative = after
    return tuple(steps)


@dataclass(frozen=True)
class DiversifiedSevenRedTop10Snapshot:
    source_audit: SevenRedDiversityAuditSnapshot
    weights: SevenRedDiversificationWeights
    steps: tuple[DiversifiedSevenRedTop10Step, ...]
    final_metrics: SevenRedGeometryMetrics
    snapshot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_audit, SevenRedDiversityAuditSnapshot):
            _reject(
                "seven_red_diversified_source_audit_invalid",
                "selector source must be a SevenRedDiversityAuditSnapshot",
            )
        if not isinstance(self.weights, SevenRedDiversificationWeights):
            _reject(
                "seven_red_diversified_weights_invalid",
                "selector weights must use the canonical configuration",
            )
        if (
            not isinstance(self.steps, tuple)
            or len(self.steps) != DIVERSIFIED_TOP10_SIZE
            or any(not isinstance(step, DiversifiedSevenRedTop10Step) for step in self.steps)
        ):
            _reject(
                "seven_red_diversified_steps_invalid",
                "snapshot must contain exactly ten immutable selection steps",
            )
        expected_steps = _greedy_steps(self.source_audit, self.weights)
        if self.steps != expected_steps:
            _reject(
                "seven_red_diversified_steps_mismatch",
                "selection steps do not match the frozen exact greedy contract",
            )
        selected = tuple(step.scored_candidate.candidate for step in self.steps)
        if len({candidate.candidate_id for candidate in selected}) != DIVERSIFIED_TOP10_SIZE:
            _reject(
                "seven_red_diversified_duplicate_candidate",
                "Diversified Top10 must contain ten distinct candidates",
            )
        expected_metrics = SevenRedGeometryMetrics.build(selected)
        if not isinstance(self.final_metrics, SevenRedGeometryMetrics) or (
            self.final_metrics != expected_metrics
        ):
            _reject(
                "seven_red_diversified_final_metrics_mismatch",
                "final geometry does not match the selected candidates",
            )
        expansion = self.final_metrics.expansion_geometry
        if (
            expansion.total_expansion_slots != 70
            or expansion.unique_expansion_count != 70
            or expansion.duplicate_expansion_slot_count != 0
            or self.final_metrics.overlap_histogram[6] != 0
        ):
            _reject(
                "seven_red_diversified_unique70_invariant_failed",
                "Diversified Top10 must produce exactly 70 unique six-red expansions",
            )
        object.__setattr__(
            self,
            "snapshot_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.diversified-top10-snapshot.v1",
            ),
        )

    @classmethod
    def build(
        cls,
        source_audit: SevenRedDiversityAuditSnapshot,
        weights: SevenRedDiversificationWeights,
    ) -> DiversifiedSevenRedTop10Snapshot:
        if not isinstance(source_audit, SevenRedDiversityAuditSnapshot):
            _reject(
                "seven_red_diversified_source_audit_invalid",
                "selector source must be a SevenRedDiversityAuditSnapshot",
            )
        if not isinstance(weights, SevenRedDiversificationWeights):
            _reject(
                "seven_red_diversified_weights_invalid",
                "selector weights must use the canonical configuration",
            )
        steps = _greedy_steps(source_audit, weights)
        final_metrics = SevenRedGeometryMetrics.build(
            tuple(step.scored_candidate.candidate for step in steps)
        )
        return cls(
            source_audit=source_audit,
            weights=weights,
            steps=steps,
            final_metrics=final_metrics,
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": DIVERSIFIED_TOP10_SNAPSHOT_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": SEVEN_RED_DIVERSIFIED_TOP10_CONTRACT_V1.normative_identity(),
            "seven_red_diversity_audit_contract": (
                SEVEN_RED_DIVERSITY_AUDIT_CONTRACT_V1.normative_identity()
            ),
            "selector_contract": DIVERSIFIED_TOP10_SELECTOR_CONTRACT,
            "source_ranking_contract": RAW_TOP10_RANKING_CONTRACT,
            "utility_contract": {
                "arithmetic": "exact_fraction",
                "budget": DIVERSIFIED_TOP10_SIZE,
                "pair_coverage_denominator": PAIR_COVERAGE_DENOMINATOR,
                "triple_coverage_denominator": TRIPLE_COVERAGE_DENOMINATOR,
                "exposure_square_denominator": EXPOSURE_SQUARE_DENOMINATOR,
                "expansion_constraint": "each_step_adds_exactly_7_new_six_red_tickets",
                "tie_breaks": ["higher_source_quality", "lower_lex_id"],
            },
            "selection_status": "parameterized_research_backend_not_trained_configuration",
            "global_optimality_claim": False,
            "deterministic": True,
            "seed_policy": None,
            "outcome_inputs": None,
            "source_diversity_audit_digest": self.source_audit.snapshot_digest,
            "source_candidate_list_digest": (
                self.source_audit.source_candidate_pool.artifact_digest
            ),
            "source_raw_top10_snapshot_digest": (
                self.source_audit.source_raw_top10.snapshot_digest
            ),
            "configuration": self.weights.as_dict(),
            "candidate_count": len(self.steps),
            "steps": [step.identity_payload() for step in self.steps],
            "selected_row_digests": [
                step.scored_candidate.row_digest for step in self.steps
            ],
            "final_metrics": self.final_metrics.identity_payload(),
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "snapshot_digest": self.snapshot_digest}
