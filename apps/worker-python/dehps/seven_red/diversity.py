from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import combinations
from math import comb
from typing import Any

from dehps.contracts import ContractRef, canonical_digest
from dehps.seven_red.domain import (
    LINE_KEY,
    RESEARCH_ONLY,
    SEVEN_RED_DOMAIN_CONTRACT_V1,
    SevenRedCandidate,
    SixRedCombination,
    expand_seven_red_candidate,
)
from dehps.seven_red.raw_top10 import (
    RAW_TOP10_SIZE,
    SEVEN_RED_RAW_TOP10_CONTRACT_V1,
    PreScoredSevenRedCandidateList,
    RawSevenRedTop10Snapshot,
)


SEVEN_RED_DIVERSITY_AUDIT_VERSION = "seven_red_diversity_audit_snapshot.v1"
SEVEN_RED_DIVERSITY_METRIC_CONTRACT = (
    "seven_red_diversity.exact_subset_incidence_and_expansion_collision.v1"
)
DECIMAL_SUMMARY_DIGITS = 10

SEVEN_RED_DIVERSITY_NORMATIVE_DEFINITION = {
    "contract": "seven-red-diversity-audit.v1.0.0",
    "line_key": LINE_KEY,
    "research_only": RESEARCH_ONLY,
    "dependencies": {
        "seven_red_domain": SEVEN_RED_DOMAIN_CONTRACT_V1.normative_identity(),
        "seven_red_raw_top10": SEVEN_RED_RAW_TOP10_CONTRACT_V1.normative_identity(),
    },
    "inputs": {
        "candidate_pool": "pre_scored_seven_red_candidate_list.v1",
        "raw_top10": "seven_red_raw_top10_snapshot.v1",
        "source_binding": "raw_top10_source_must_equal_candidate_pool",
    },
    "metrics": {
        "contract": SEVEN_RED_DIVERSITY_METRIC_CONTRACT,
        "scopes": ["complete_candidate_pool", "frozen_raw_top10"],
        "candidate_set_identity": "canonical_lex_id_ordered_candidate_identity_digest",
        "number_exposure": "exact_occurrence_counts_over_33_red_numbers",
        "pairwise_overlap": "exact_histogram_for_intersection_cardinality_0_through_6",
        "core_coverage": "exact_unique_and_max_multiplicity_for_pairs_and_triples",
        "expansion_geometry": (
            "exact_unique_duplicate_and_collision_counts_over_all_7_to_6_expansions"
        ),
        "decimal_policy": "round_half_even_python_round_to_10_digits_derivative_only",
        "normative_evidence": "integer_counts_histograms_numerators_and_denominators",
    },
    "algorithm": {
        "subset_incidence": (
            "S_k=sum_over_k_cores_C(multiplicity,2)="
            "sum_over_intersections_j_ge_k_C(j,k)*H_j"
        ),
        "overlap_recovery": "descending_binomial_inversion_for_H_6_through_H_1",
        "zero_overlap": "H_0=C(B,2)-sum(H_1_through_H_6)",
        "expansion_collision": "six_red_core_multiplicity_greater_than_one",
        "seed": "absent",
        "outcome_input": "forbidden",
    },
    "interpretation": {
        "status": "observational_only",
        "threshold": "absent",
        "selection_intervention": "forbidden",
        "performance_claim": "forbidden",
    },
    "non_goals": [
        "no_diversified_selector",
        "no_score_or_rank_mutation",
        "no_random_baseline",
        "no_target_draw_or_settlement",
        "no_walk_forward_or_statistical_test",
        "no_production_integration",
    ],
}

SEVEN_RED_DIVERSITY_GOLDEN_SUITE = {
    "suite": "seven_red_diversity_audit_golden.v1",
    "source": "seven_red_raw_top10_golden.v1",
    "pool": {
        "candidate_count": 12,
        "pair_count": 66,
        "overlap_histogram_0_through_6": [0, 0, 0, 0, 0, 0, 66],
        "shared_core_pair_counts_1_through_6": [396, 990, 1320, 990, 396, 66],
        "unique_expansion_count": 73,
        "duplicate_expansion_slot_count": 11,
    },
    "raw_top10": {
        "candidate_count": RAW_TOP10_SIZE,
        "pair_count": 45,
        "overlap_histogram_0_through_6": [0, 0, 0, 0, 0, 0, 45],
        "shared_core_pair_counts_1_through_6": [270, 675, 900, 675, 270, 45],
        "unique_expansion_count": 61,
        "duplicate_expansion_slot_count": 9,
    },
    "expected_pool_candidate_set_digest": (
        "d2214aa750b3f38a185976c325207e9ad5a9cca4623847124df158868f69b9ad"
    ),
    "expected_raw_candidate_set_digest": (
        "548abab8c72590a7249933b5549019c3182d7d313cdb523bc44b215bee9ab697"
    ),
    "expected_audit_digest": (
        "bbf9b9f79465bde31277f2b59235041d93ebe8f3e8a20a8bb0f05ea6363b6287"
    ),
    "stochastic": False,
}

SEVEN_RED_DIVERSITY_AUDIT_CONTRACT_V1 = ContractRef.from_definition(
    family="seven-red-diversity-audit",
    semantic_version="1.0.0",
    schema_version="dehps.seven-red-diversity-audit.schema.v1",
    normative_definition=SEVEN_RED_DIVERSITY_NORMATIVE_DEFINITION,
    golden_suite=SEVEN_RED_DIVERSITY_GOLDEN_SUITE,
)


class SevenRedDiversityAuditViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _reject(code: str, message: str, **context: Any) -> None:
    raise SevenRedDiversityAuditViolation(code, message, **context)


def _rounded_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    value = round(numerator / denominator, DECIMAL_SUMMARY_DIGITS)
    return 0.0 if value == 0.0 else value


def _require_nonnegative_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        _reject(
            "seven_red_diversity_integer_invalid",
            f"{field_name} must be a non-negative integer",
            field=field_name,
        )
    return value


def _require_digest(value: object, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _reject(
            "seven_red_diversity_digest_invalid",
            f"{field_name} must be a full lowercase sha256 digest",
            field=field_name,
        )
    return value


@dataclass(frozen=True)
class SevenRedCoreCoverage:
    core_size: int
    unique_count: int
    legal_universe_count: int
    occurrence_count: int
    attainable_count: int
    maximum_multiplicity: int
    maximum_cores: tuple[tuple[int, ...], ...]

    def __post_init__(self) -> None:
        if self.core_size not in (2, 3):
            _reject(
                "seven_red_diversity_core_size_invalid",
                "core coverage is defined only for pairs and triples",
            )
        for field_name in (
            "unique_count",
            "legal_universe_count",
            "occurrence_count",
            "attainable_count",
            "maximum_multiplicity",
        ):
            _require_nonnegative_int(getattr(self, field_name), field_name=field_name)
        if not isinstance(self.maximum_cores, tuple):
            _reject(
                "seven_red_diversity_core_storage_invalid",
                "maximum cores must use an immutable tuple",
            )
        canonical = tuple(sorted(self.maximum_cores))
        if self.maximum_cores != canonical or len(set(self.maximum_cores)) != len(canonical):
            _reject(
                "seven_red_diversity_core_order_invalid",
                "maximum cores must be unique and lexicographically ordered",
            )
        if any(
            not isinstance(core, tuple)
            or len(core) != self.core_size
            or tuple(sorted(core)) != core
            or len(set(core)) != self.core_size
            or any(not isinstance(number, int) or isinstance(number, bool) for number in core)
            or any(not 1 <= number <= 33 for number in core)
            for core in self.maximum_cores
        ):
            _reject(
                "seven_red_diversity_core_value_invalid",
                "maximum cores must use canonical legal red-number tuples",
            )
        expected_legal = comb(33, self.core_size)
        if self.legal_universe_count != expected_legal:
            _reject(
                "seven_red_diversity_core_universe_mismatch",
                "legal core universe count is inconsistent",
            )
        if not 0 <= self.unique_count <= min(self.legal_universe_count, self.occurrence_count):
            _reject(
                "seven_red_diversity_core_count_invalid",
                "unique core count is outside its exact bounds",
            )
        if self.attainable_count != min(self.legal_universe_count, self.occurrence_count):
            _reject(
                "seven_red_diversity_core_attainable_mismatch",
                "attainable core count is inconsistent",
            )
        per_candidate = comb(7, self.core_size)
        if self.occurrence_count < per_candidate or self.occurrence_count % per_candidate:
            _reject(
                "seven_red_diversity_core_occurrence_mismatch",
                "core occurrences must represent a positive whole candidate count",
            )
        candidate_count = self.occurrence_count // per_candidate
        if (
            self.maximum_multiplicity > candidate_count
            or len(self.maximum_cores) > self.unique_count
        ):
            _reject(
                "seven_red_diversity_core_maximum_mismatch",
                "maximum core evidence exceeds candidate or unique-core bounds",
            )
        if self.unique_count == 0:
            if self.maximum_multiplicity != 0 or self.maximum_cores:
                _reject(
                    "seven_red_diversity_core_maximum_mismatch",
                    "empty core coverage cannot have maximum cores",
                )
        elif self.maximum_multiplicity < 1 or not self.maximum_cores:
            _reject(
                "seven_red_diversity_core_maximum_mismatch",
                "non-empty core coverage requires positive tied maxima",
            )

    @classmethod
    def build(
        cls,
        counts: Mapping[tuple[int, ...], int],
        *,
        candidate_count: int,
        core_size: int,
    ) -> SevenRedCoreCoverage:
        maximum = max(counts.values(), default=0)
        maximum_cores = tuple(
            core for core, count in sorted(counts.items()) if count == maximum
        )
        occurrence_count = candidate_count * comb(7, core_size)
        return cls(
            core_size=core_size,
            unique_count=len(counts),
            legal_universe_count=comb(33, core_size),
            occurrence_count=occurrence_count,
            attainable_count=min(comb(33, core_size), occurrence_count),
            maximum_multiplicity=maximum,
            maximum_cores=maximum_cores,
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "core_size": self.core_size,
            "unique_count": self.unique_count,
            "legal_universe_count": self.legal_universe_count,
            "legal_coverage_numerator": self.unique_count,
            "legal_coverage_denominator": self.legal_universe_count,
            "occurrence_count": self.occurrence_count,
            "attainable_count": self.attainable_count,
            "attainable_coverage_numerator": self.unique_count,
            "attainable_coverage_denominator": self.attainable_count,
            "maximum_multiplicity": self.maximum_multiplicity,
            "maximum_concentration_numerator": self.maximum_multiplicity,
            "maximum_concentration_denominator": (
                self.occurrence_count // comb(7, self.core_size)
            ),
            "maximum_cores": [list(core) for core in self.maximum_cores],
            "derivative_decimal_summaries": {
                "legal_coverage": _rounded_ratio(
                    self.unique_count,
                    self.legal_universe_count,
                ),
                "attainable_coverage": _rounded_ratio(
                    self.unique_count,
                    self.attainable_count,
                ),
                "maximum_concentration": _rounded_ratio(
                    self.maximum_multiplicity,
                    self.occurrence_count // comb(7, self.core_size),
                ),
            },
        }


@dataclass(frozen=True)
class SevenRedExpansionCollision:
    six_red: SixRedCombination
    multiplicity: int
    source_candidate_lex_ids: tuple[int, ...]
    source_candidate_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.six_red, SixRedCombination):
            _reject(
                "seven_red_diversity_collision_core_invalid",
                "collision core must be a canonical SixRedCombination",
            )
        if (
            not isinstance(self.multiplicity, int)
            or isinstance(self.multiplicity, bool)
            or self.multiplicity < 2
        ):
            _reject(
                "seven_red_diversity_collision_multiplicity_invalid",
                "collision multiplicity must be an integer of at least two",
            )
        if (
            not isinstance(self.source_candidate_lex_ids, tuple)
            or not isinstance(self.source_candidate_ids, tuple)
            or len(self.source_candidate_lex_ids) != self.multiplicity
            or len(self.source_candidate_ids) != self.multiplicity
            or tuple(sorted(self.source_candidate_lex_ids)) != self.source_candidate_lex_ids
            or len(set(self.source_candidate_lex_ids)) != self.multiplicity
            or len(set(self.source_candidate_ids)) != self.multiplicity
            or any(
                not isinstance(lex_id, int)
                or isinstance(lex_id, bool)
                or not 0 <= lex_id < comb(33, 7)
                for lex_id in self.source_candidate_lex_ids
            )
        ):
            _reject(
                "seven_red_diversity_collision_sources_invalid",
                "collision sources must be unique and ordered by candidate lex_id",
            )
        for candidate_id in self.source_candidate_ids:
            _require_digest(candidate_id, field_name="source_candidate_id")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "six_red": self.six_red.identity_payload(),
            "multiplicity": self.multiplicity,
            "source_candidate_lex_ids": list(self.source_candidate_lex_ids),
            "source_candidate_ids": list(self.source_candidate_ids),
        }


@dataclass(frozen=True)
class SevenRedExpansionGeometry:
    candidate_count: int
    total_expansion_slots: int
    unique_expansion_count: int
    duplicate_expansion_slot_count: int
    multiplicity_histogram: tuple[int, ...]
    maximum_multiplicity: int
    collisions: tuple[SevenRedExpansionCollision, ...]
    collision_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for field_name in (
            "candidate_count",
            "total_expansion_slots",
            "unique_expansion_count",
            "duplicate_expansion_slot_count",
            "maximum_multiplicity",
        ):
            _require_nonnegative_int(getattr(self, field_name), field_name=field_name)
        if self.candidate_count < 1:
            _reject(
                "seven_red_diversity_candidate_count_invalid",
                "expansion geometry requires at least one candidate",
            )
        if self.total_expansion_slots != 7 * self.candidate_count:
            _reject(
                "seven_red_diversity_expansion_slot_mismatch",
                "total expansion slots must equal seven times candidate count",
            )
        if (
            not isinstance(self.multiplicity_histogram, tuple)
            or len(self.multiplicity_histogram) != self.candidate_count + 1
            or any(
                not isinstance(count, int) or isinstance(count, bool) or count < 0
                for count in self.multiplicity_histogram
            )
            or self.multiplicity_histogram[0] != 0
        ):
            _reject(
                "seven_red_diversity_multiplicity_histogram_invalid",
                "multiplicity histogram must have canonical support 0 through candidate count",
            )
        if sum(self.multiplicity_histogram) != self.unique_expansion_count:
            _reject(
                "seven_red_diversity_expansion_unique_mismatch",
                "multiplicity histogram does not reproduce unique expansion count",
            )
        if (
            sum(index * count for index, count in enumerate(self.multiplicity_histogram))
            != self.total_expansion_slots
        ):
            _reject(
                "seven_red_diversity_expansion_occurrence_mismatch",
                "multiplicity histogram does not reproduce total expansion slots",
            )
        if (
            self.duplicate_expansion_slot_count
            != self.total_expansion_slots - self.unique_expansion_count
        ):
            _reject(
                "seven_red_diversity_expansion_duplicate_mismatch",
                "duplicate expansion slots are inconsistent",
            )
        expected_maximum = max(
            (index for index, count in enumerate(self.multiplicity_histogram) if count),
            default=0,
        )
        if self.maximum_multiplicity != expected_maximum:
            _reject(
                "seven_red_diversity_expansion_maximum_mismatch",
                "maximum expansion multiplicity is inconsistent",
            )
        if (
            not isinstance(self.collisions, tuple)
            or any(not isinstance(item, SevenRedExpansionCollision) for item in self.collisions)
            or tuple(sorted(self.collisions, key=lambda item: item.six_red.lex_id))
            != self.collisions
            or len({item.six_red.combination_id for item in self.collisions})
            != len(self.collisions)
        ):
            _reject(
                "seven_red_diversity_collision_order_invalid",
                "collisions must be unique and ordered by six-red lex_id",
            )
        if Counter(item.multiplicity for item in self.collisions) != Counter(
            {
                multiplicity: count
                for multiplicity, count in enumerate(self.multiplicity_histogram)
                if multiplicity >= 2 and count
            }
        ):
            _reject(
                "seven_red_diversity_collision_histogram_mismatch",
                "collision rows do not match multiplicity histogram",
            )
        object.__setattr__(
            self,
            "collision_digest",
            canonical_digest(
                [item.identity_payload() for item in self.collisions],
                domain="dehps.seven-red.expansion-collisions.v1",
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "candidate_count": self.candidate_count,
            "total_expansion_slots": self.total_expansion_slots,
            "unique_expansion_count": self.unique_expansion_count,
            "duplicate_expansion_slot_count": self.duplicate_expansion_slot_count,
            "effective_unique_coverage_numerator": self.unique_expansion_count,
            "effective_unique_coverage_denominator": self.total_expansion_slots,
            "multiplicity_histogram": {
                str(index): count
                for index, count in enumerate(self.multiplicity_histogram)
            },
            "maximum_multiplicity": self.maximum_multiplicity,
            "collision_core_count": len(self.collisions),
            "collisions": [item.identity_payload() for item in self.collisions],
            "collision_digest": self.collision_digest,
            "derivative_decimal_summaries": {
                "effective_unique_coverage": _rounded_ratio(
                    self.unique_expansion_count,
                    self.total_expansion_slots,
                ),
            },
        }


def _core_counts(
    candidates: Sequence[SevenRedCandidate],
) -> tuple[Counter[tuple[int, ...]], ...]:
    counters: list[Counter[tuple[int, ...]]] = []
    for core_size in range(1, 7):
        counters.append(
            Counter(
                core
                for candidate in candidates
                for core in combinations(candidate.sorted_red_numbers, core_size)
            )
        )
    return tuple(counters)


def _recover_overlap_histogram(
    *,
    candidate_count: int,
    shared_core_pair_counts: Sequence[int],
) -> tuple[int, ...]:
    histogram = [0] * 7
    for intersection_size in range(6, 0, -1):
        incidence = shared_core_pair_counts[intersection_size - 1]
        already_attributed = sum(
            comb(larger, intersection_size) * histogram[larger]
            for larger in range(intersection_size + 1, 7)
        )
        histogram[intersection_size] = incidence - already_attributed
        if histogram[intersection_size] < 0:
            _reject(
                "seven_red_diversity_overlap_inversion_invalid",
                "subset incidence inversion produced a negative overlap count",
                intersection_size=intersection_size,
            )
    histogram[0] = comb(candidate_count, 2) - sum(histogram[1:])
    if histogram[0] < 0:
        _reject(
            "seven_red_diversity_overlap_inversion_invalid",
            "subset incidence inversion produced a negative zero-overlap count",
        )
    return tuple(histogram)


def _build_expansion_geometry(
    candidates: Sequence[SevenRedCandidate],
) -> SevenRedExpansionGeometry:
    expansions_by_core: dict[
        tuple[int, ...],
        list[tuple[int, str, SixRedCombination]],
    ] = defaultdict(list)
    for candidate in candidates:
        for expansion in expand_seven_red_candidate(candidate):
            expansions_by_core[expansion.six_red.sorted_red_numbers].append(
                (candidate.lex_id, candidate.candidate_id, expansion.six_red)
            )
    multiplicities = Counter(len(sources) for sources in expansions_by_core.values())
    histogram = tuple(
        0 if multiplicity == 0 else multiplicities[multiplicity]
        for multiplicity in range(len(candidates) + 1)
    )
    collisions: list[SevenRedExpansionCollision] = []
    for sources in expansions_by_core.values():
        if len(sources) < 2:
            continue
        ordered = tuple(sorted(sources, key=lambda item: item[0]))
        collisions.append(
            SevenRedExpansionCollision(
                six_red=ordered[0][2],
                multiplicity=len(ordered),
                source_candidate_lex_ids=tuple(item[0] for item in ordered),
                source_candidate_ids=tuple(item[1] for item in ordered),
            )
        )
    ordered_collisions = tuple(sorted(collisions, key=lambda item: item.six_red.lex_id))
    total_slots = 7 * len(candidates)
    unique_count = len(expansions_by_core)
    return SevenRedExpansionGeometry(
        candidate_count=len(candidates),
        total_expansion_slots=total_slots,
        unique_expansion_count=unique_count,
        duplicate_expansion_slot_count=total_slots - unique_count,
        multiplicity_histogram=histogram,
        maximum_multiplicity=max(multiplicities, default=0),
        collisions=ordered_collisions,
    )


@dataclass(frozen=True)
class SevenRedGeometryMetrics:
    candidate_count: int
    candidate_set_digest: str
    pair_count: int
    overlap_histogram: tuple[int, ...]
    shared_core_pair_counts: tuple[int, ...]
    red_number_occurrences: tuple[int, ...]
    maximum_number_occurrence: int
    maximum_numbers: tuple[int, ...]
    pair_core_coverage: SevenRedCoreCoverage
    triple_core_coverage: SevenRedCoreCoverage
    expansion_geometry: SevenRedExpansionGeometry

    def __post_init__(self) -> None:
        if (
            not isinstance(self.candidate_count, int)
            or isinstance(self.candidate_count, bool)
            or self.candidate_count < 1
        ):
            _reject(
                "seven_red_diversity_candidate_count_invalid",
                "geometry metrics require at least one candidate",
            )
        _require_digest(self.candidate_set_digest, field_name="candidate_set_digest")
        if self.pair_count != comb(self.candidate_count, 2):
            _reject(
                "seven_red_diversity_pair_count_mismatch",
                "pair count must equal C(candidate_count,2)",
            )
        if (
            not isinstance(self.overlap_histogram, tuple)
            or len(self.overlap_histogram) != 7
            or any(
                not isinstance(count, int) or isinstance(count, bool) or count < 0
                for count in self.overlap_histogram
            )
            or sum(self.overlap_histogram) != self.pair_count
        ):
            _reject(
                "seven_red_diversity_overlap_histogram_invalid",
                "overlap histogram must exactly cover all candidate pairs",
            )
        if (
            not isinstance(self.shared_core_pair_counts, tuple)
            or len(self.shared_core_pair_counts) != 6
            or any(
                not isinstance(count, int) or isinstance(count, bool) or count < 0
                for count in self.shared_core_pair_counts
            )
        ):
            _reject(
                "seven_red_diversity_incidence_counts_invalid",
                "shared core pair counts must cover core sizes one through six",
            )
        for core_size in range(1, 7):
            expected = sum(
                comb(intersection_size, core_size)
                * self.overlap_histogram[intersection_size]
                for intersection_size in range(core_size, 7)
            )
            if self.shared_core_pair_counts[core_size - 1] != expected:
                _reject(
                    "seven_red_diversity_incidence_identity_failed",
                    "overlap histogram violates the exact subset-incidence identity",
                    core_size=core_size,
                )
        if (
            not isinstance(self.red_number_occurrences, tuple)
            or len(self.red_number_occurrences) != 33
            or any(
                not isinstance(count, int) or isinstance(count, bool) or count < 0
                for count in self.red_number_occurrences
            )
            or sum(self.red_number_occurrences) != 7 * self.candidate_count
        ):
            _reject(
                "seven_red_diversity_number_occurrences_invalid",
                "red-number occurrences must exactly cover seven slots per candidate",
            )
        if self.maximum_number_occurrence != max(self.red_number_occurrences):
            _reject(
                "seven_red_diversity_number_maximum_mismatch",
                "maximum red-number occurrence is inconsistent",
            )
        expected_maximum_numbers = tuple(
            number
            for number, count in enumerate(self.red_number_occurrences, start=1)
            if count == self.maximum_number_occurrence
        )
        if self.maximum_numbers != expected_maximum_numbers:
            _reject(
                "seven_red_diversity_number_maximum_mismatch",
                "maximum red-number identities are inconsistent",
            )
        if (
            not isinstance(self.pair_core_coverage, SevenRedCoreCoverage)
            or self.pair_core_coverage.core_size != 2
            or self.pair_core_coverage.occurrence_count != 21 * self.candidate_count
            or not isinstance(self.triple_core_coverage, SevenRedCoreCoverage)
            or self.triple_core_coverage.core_size != 3
            or self.triple_core_coverage.occurrence_count != 35 * self.candidate_count
        ):
            _reject(
                "seven_red_diversity_core_coverage_mismatch",
                "pair or triple core coverage does not match candidate count",
            )
        if (
            not isinstance(self.expansion_geometry, SevenRedExpansionGeometry)
            or self.expansion_geometry.candidate_count != self.candidate_count
        ):
            _reject(
                "seven_red_diversity_expansion_geometry_mismatch",
                "expansion geometry does not match candidate count",
            )
        collision_pairs = sum(
            comb(collision.multiplicity, 2)
            for collision in self.expansion_geometry.collisions
        )
        if collision_pairs != self.overlap_histogram[6]:
            _reject(
                "seven_red_diversity_expansion_collision_identity_failed",
                "six-red expansion collisions do not match overlap-six candidate pairs",
            )

    @classmethod
    def build(
        cls,
        candidates: Sequence[SevenRedCandidate],
    ) -> SevenRedGeometryMetrics:
        frozen = tuple(candidates)
        if not frozen or any(not isinstance(item, SevenRedCandidate) for item in frozen):
            _reject(
                "seven_red_diversity_candidates_invalid",
                "metrics require canonical SevenRedCandidate values",
            )
        ordered = tuple(sorted(frozen, key=lambda item: item.lex_id))
        if len({item.candidate_id for item in ordered}) != len(ordered):
            _reject(
                "seven_red_diversity_duplicate_candidate",
                "metrics require distinct seven-red candidates",
            )
        counts_by_size = _core_counts(ordered)
        shared_core_pair_counts = tuple(
            sum(comb(multiplicity, 2) for multiplicity in counts.values())
            for counts in counts_by_size
        )
        overlap_histogram = _recover_overlap_histogram(
            candidate_count=len(ordered),
            shared_core_pair_counts=shared_core_pair_counts,
        )
        number_counts = Counter(
            number for candidate in ordered for number in candidate.sorted_red_numbers
        )
        occurrences = tuple(number_counts[number] for number in range(1, 34))
        maximum_occurrence = max(occurrences)
        expansion_geometry = _build_expansion_geometry(ordered)
        six_core_counts = counts_by_size[5]
        if Counter(six_core_counts.values()) != Counter(
            {
                multiplicity: count
                for multiplicity, count in enumerate(
                    expansion_geometry.multiplicity_histogram
                )
                if multiplicity and count
            }
        ):
            _reject(
                "seven_red_diversity_expansion_core_mismatch",
                "domain expansion multiplicities differ from six-core incidence counts",
            )
        return cls(
            candidate_count=len(ordered),
            candidate_set_digest=canonical_digest(
                [candidate.identity_payload() for candidate in ordered],
                domain="dehps.seven-red.diversity-candidate-set.v1",
            ),
            pair_count=comb(len(ordered), 2),
            overlap_histogram=overlap_histogram,
            shared_core_pair_counts=shared_core_pair_counts,
            red_number_occurrences=occurrences,
            maximum_number_occurrence=maximum_occurrence,
            maximum_numbers=tuple(
                number
                for number, count in enumerate(occurrences, start=1)
                if count == maximum_occurrence
            ),
            pair_core_coverage=SevenRedCoreCoverage.build(
                counts_by_size[1],
                candidate_count=len(ordered),
                core_size=2,
            ),
            triple_core_coverage=SevenRedCoreCoverage.build(
                counts_by_size[2],
                candidate_count=len(ordered),
                core_size=3,
            ),
            expansion_geometry=expansion_geometry,
        )

    def identity_payload(self) -> dict[str, Any]:
        overlap_numerator = sum(
            overlap * count for overlap, count in enumerate(self.overlap_histogram)
        )
        return {
            "metric_contract": SEVEN_RED_DIVERSITY_METRIC_CONTRACT,
            "candidate_count": self.candidate_count,
            "candidate_set_digest": self.candidate_set_digest,
            "pair_count": self.pair_count,
            "pairwise_overlap": {
                "histogram": {
                    str(overlap): count
                    for overlap, count in enumerate(self.overlap_histogram)
                },
                "sum_numerator": overlap_numerator,
                "mean_denominator": self.pair_count,
                "derivative_decimal_mean": _rounded_ratio(
                    overlap_numerator,
                    self.pair_count,
                ),
            },
            "shared_core_pair_counts": {
                str(core_size): self.shared_core_pair_counts[core_size - 1]
                for core_size in range(1, 7)
            },
            "number_exposure": {
                "occurrences": [
                    {"number": number, "count": count}
                    for number, count in enumerate(self.red_number_occurrences, start=1)
                ],
                "maximum_count": self.maximum_number_occurrence,
                "maximum_numbers": list(self.maximum_numbers),
                "maximum_exposure_numerator": self.maximum_number_occurrence,
                "maximum_exposure_denominator": self.candidate_count,
                "derivative_decimal_maximum_exposure": _rounded_ratio(
                    self.maximum_number_occurrence,
                    self.candidate_count,
                ),
            },
            "pair_core_coverage": self.pair_core_coverage.identity_payload(),
            "triple_core_coverage": self.triple_core_coverage.identity_payload(),
            "expansion_geometry": self.expansion_geometry.identity_payload(),
        }


@dataclass(frozen=True)
class SevenRedDiversityAuditSnapshot:
    source_candidate_pool: PreScoredSevenRedCandidateList
    source_raw_top10: RawSevenRedTop10Snapshot
    pool_metrics: SevenRedGeometryMetrics
    raw_top10_metrics: SevenRedGeometryMetrics
    snapshot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_candidate_pool, PreScoredSevenRedCandidateList):
            _reject(
                "seven_red_diversity_source_pool_invalid",
                "source pool must be a PreScoredSevenRedCandidateList",
            )
        if not isinstance(self.source_raw_top10, RawSevenRedTop10Snapshot):
            _reject(
                "seven_red_diversity_source_raw_invalid",
                "source Raw Top10 must be a RawSevenRedTop10Snapshot",
            )
        if self.source_raw_top10.source != self.source_candidate_pool:
            _reject(
                "seven_red_diversity_source_binding_mismatch",
                "Raw Top10 source must equal the audited candidate pool",
            )
        if (
            not isinstance(self.pool_metrics, SevenRedGeometryMetrics)
            or not isinstance(self.raw_top10_metrics, SevenRedGeometryMetrics)
        ):
            _reject(
                "seven_red_diversity_metrics_type_invalid",
                "audit metrics must use canonical SevenRedGeometryMetrics values",
            )
        expected_pool = SevenRedGeometryMetrics.build(
            tuple(row.candidate for row in self.source_candidate_pool.rows)
        )
        expected_raw = SevenRedGeometryMetrics.build(
            tuple(
                entry.scored_candidate.candidate
                for entry in self.source_raw_top10.entries
            )
        )
        if self.pool_metrics != expected_pool:
            _reject(
                "seven_red_diversity_pool_metrics_mismatch",
                "pool metrics do not exactly match the complete source pool",
            )
        if self.raw_top10_metrics != expected_raw:
            _reject(
                "seven_red_diversity_raw_metrics_mismatch",
                "Raw Top10 metrics do not exactly match the frozen source snapshot",
            )
        object.__setattr__(
            self,
            "snapshot_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.diversity-audit-snapshot.v1",
            ),
        )

    @classmethod
    def build(
        cls,
        source_candidate_pool: PreScoredSevenRedCandidateList,
        source_raw_top10: RawSevenRedTop10Snapshot,
    ) -> SevenRedDiversityAuditSnapshot:
        if not isinstance(source_candidate_pool, PreScoredSevenRedCandidateList):
            _reject(
                "seven_red_diversity_source_pool_invalid",
                "source pool must be a PreScoredSevenRedCandidateList",
            )
        if not isinstance(source_raw_top10, RawSevenRedTop10Snapshot):
            _reject(
                "seven_red_diversity_source_raw_invalid",
                "source Raw Top10 must be a RawSevenRedTop10Snapshot",
            )
        pool_candidates = tuple(row.candidate for row in source_candidate_pool.rows)
        raw_candidates = tuple(
            entry.scored_candidate.candidate for entry in source_raw_top10.entries
        )
        return cls(
            source_candidate_pool=source_candidate_pool,
            source_raw_top10=source_raw_top10,
            pool_metrics=SevenRedGeometryMetrics.build(pool_candidates),
            raw_top10_metrics=SevenRedGeometryMetrics.build(raw_candidates),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_DIVERSITY_AUDIT_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": SEVEN_RED_DIVERSITY_AUDIT_CONTRACT_V1.normative_identity(),
            "seven_red_domain_contract": SEVEN_RED_DOMAIN_CONTRACT_V1.normative_identity(),
            "seven_red_raw_top10_contract": (
                SEVEN_RED_RAW_TOP10_CONTRACT_V1.normative_identity()
            ),
            "metric_contract": SEVEN_RED_DIVERSITY_METRIC_CONTRACT,
            "deterministic": True,
            "seed_policy": None,
            "outcome_inputs": None,
            "interpretation": "observational_only",
            "threshold_policy": None,
            "source_candidate_list_digest": (
                self.source_candidate_pool.artifact_digest
            ),
            "source_raw_top10_snapshot_digest": (
                self.source_raw_top10.snapshot_digest
            ),
            "source_raw_top10_entries": [
                entry.as_dict() for entry in self.source_raw_top10.entries
            ],
            "pool_metrics": self.pool_metrics.identity_payload(),
            "raw_top10_metrics": self.raw_top10_metrics.identity_payload(),
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "snapshot_digest": self.snapshot_digest}
