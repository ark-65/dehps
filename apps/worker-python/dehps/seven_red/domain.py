from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from dehps.contracts import ContractRef, canonical_digest
from dehps.input_contracts.candidate_abi import (
    CANDIDATE_CONTRACT_V1,
    CandidateContractViolation,
    CandidateUniverseManifest,
    candidate_mask,
    candidate_rank,
    candidate_record_digest,
    validate_candidate_numbers,
)


LINE_KEY = "seven_red_compound_top10"
RESEARCH_ONLY = True
SEVEN_RED_DOMAIN_VERSION = "seven_red_domain.v1"
SEVEN_RED_EXPANSION_VERSION = "seven_red_expansion.v1"
SEVEN_RED_SETTLEMENT_VERSION = "seven_red_settlement.v1"

SEVEN_RED_UNIVERSE = CandidateUniverseManifest(domain_size=33, pick_count=7)
SIX_RED_UNIVERSE = CandidateUniverseManifest(domain_size=33, pick_count=6)

SEVEN_RED_NORMATIVE_DEFINITION = {
    "contract": "seven-red-domain.v1.0.0",
    "line_key": LINE_KEY,
    "research_only": RESEARCH_ONLY,
    "candidate_dependency": CANDIDATE_CONTRACT_V1.normative_identity(),
    "universes": {
        "seven_red": {
            "domain_size": 33,
            "pick_count": 7,
            "cardinality": 4_272_048,
        },
        "six_red": {
            "domain_size": 33,
            "pick_count": 6,
            "cardinality": 1_107_568,
        },
    },
    "candidate": {
        "numbers": "seven_unique_strictly_increasing_integers_in_[1,33]",
        "candidate_id": "full_domain_separated_sha256_candidate_record_digest",
        "red_mask": "uint64_number_minus_one_bit_mapping",
        "lex_id": "zero_based_full_universe_lexicographic_rank",
        "repair_policy": "reject_without_sorting_coercion_or_deduplication",
    },
    "expansion": {
        "rule": "all_C(7,6)_subsets",
        "order": "lexicographic_ascending_six_red_tuple",
        "count": 7,
        "provenance": [
            "source_candidate_id",
            "source_sorted_red_numbers",
            "ordinal",
            "omitted_red_number",
        ],
        "expanded_id": "full_domain_separated_sha256_over_provenance_and_six_red_id",
        "batch_duplicates": "fail_closed_on_duplicate_source_or_six_red_id",
    },
    "settlement": {
        "hit_count": "set_intersection_cardinality_between_predicted_7_and_actual_6",
        "expanded_match_count": "set_intersection_cardinality_for_each_expanded_6",
        "identity": "for_h_hits_h_expansions_have_h_minus_1_and_7_minus_h_have_h",
        "count_total": 7,
        "blue_ball_policy": "outside_contract",
    },
    "non_goals": [
        "no_scoring_model",
        "no_top10_selection",
        "no_production_topk_integration",
        "no_probability_or_profit_claim",
    ],
}

SEVEN_RED_GOLDEN_SUITE = {
    "suite": "seven_red_domain_golden.v1",
    "candidate": {
        "sorted_red_numbers": [1, 2, 3, 4, 5, 6, 7],
        "candidate_id": "c3784739f57481a0cdfeaf13d3888c69462740347b8592cc2b28c6173423e664",
        "red_mask": 127,
        "lex_id": 0,
    },
    "expansion": {
        "ordered_six_red_numbers": [
            [1, 2, 3, 4, 5, 6],
            [1, 2, 3, 4, 5, 7],
            [1, 2, 3, 4, 6, 7],
            [1, 2, 3, 5, 6, 7],
            [1, 2, 4, 5, 6, 7],
            [1, 3, 4, 5, 6, 7],
            [2, 3, 4, 5, 6, 7],
        ],
        "omitted_red_numbers": [7, 6, 5, 4, 3, 2, 1],
        "unique_count": 7,
    },
    "settlement": [
        {
            "actual_red_numbers": [1, 2, 3, 4, 5, 6],
            "hit_count": 6,
            "expanded_hit_counts": [0, 0, 0, 0, 0, 6, 1],
        },
        {
            "actual_red_numbers": [1, 2, 3, 4, 5, 8],
            "hit_count": 5,
            "expanded_hit_counts": [0, 0, 0, 0, 5, 2, 0],
        },
        {
            "actual_red_numbers": [1, 2, 3, 4, 8, 9],
            "hit_count": 4,
            "expanded_hit_counts": [0, 0, 0, 4, 3, 0, 0],
        },
    ],
}

SEVEN_RED_DOMAIN_CONTRACT_V1 = ContractRef.from_definition(
    family="seven-red-domain",
    semantic_version="1.0.0",
    schema_version="dehps.seven-red-domain.schema.v1",
    normative_definition=SEVEN_RED_NORMATIVE_DEFINITION,
    golden_suite=SEVEN_RED_GOLDEN_SUITE,
)


class SevenRedContractViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _reject(code: str, message: str, **context: Any) -> None:
    raise SevenRedContractViolation(code, message, **context)


def _validate_numbers(
    numbers: Sequence[object],
    *,
    universe: CandidateUniverseManifest,
    code: str,
    label: str,
) -> tuple[int, ...]:
    try:
        return validate_candidate_numbers(numbers, universe=universe)
    except CandidateContractViolation as exc:
        raise SevenRedContractViolation(
            code,
            f"{label} violate the canonical Candidate Contract",
            cause=exc.code,
        ) from exc


def _require_digest(value: object, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _reject(
            "invalid_seven_red_digest",
            f"{field_name} must be a full lowercase sha256 digest",
            field=field_name,
        )
    return value


@dataclass(frozen=True)
class SevenRedCandidate:
    sorted_red_numbers: tuple[int, ...]
    candidate_id: str = field(init=False)
    red_mask: int = field(init=False)
    lex_id: int = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.sorted_red_numbers, tuple):
            _reject(
                "seven_red_value_type_invalid",
                "stored seven-red numbers must use the immutable tuple representation",
            )
        canonical = _validate_numbers(
            self.sorted_red_numbers,
            universe=SEVEN_RED_UNIVERSE,
            code="invalid_seven_red_candidate",
            label="seven-red candidate numbers",
        )
        object.__setattr__(
            self,
            "candidate_id",
            candidate_record_digest(canonical, universe=SEVEN_RED_UNIVERSE),
        )
        object.__setattr__(
            self,
            "red_mask",
            candidate_mask(canonical, universe=SEVEN_RED_UNIVERSE),
        )
        object.__setattr__(
            self,
            "lex_id",
            candidate_rank(canonical, universe=SEVEN_RED_UNIVERSE),
        )

    @classmethod
    def from_numbers(cls, numbers: Sequence[object]) -> SevenRedCandidate:
        canonical = _validate_numbers(
            numbers,
            universe=SEVEN_RED_UNIVERSE,
            code="invalid_seven_red_candidate",
            label="seven-red candidate numbers",
        )
        return cls(sorted_red_numbers=canonical)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sorted_red_numbers": list(self.sorted_red_numbers),
            "red_mask": self.red_mask,
            "lex_id": self.lex_id,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": SEVEN_RED_DOMAIN_CONTRACT_V1.normative_identity(),
            **self.identity_payload(),
        }


@dataclass(frozen=True)
class SixRedCombination:
    sorted_red_numbers: tuple[int, ...]
    combination_id: str = field(init=False)
    red_mask: int = field(init=False)
    lex_id: int = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.sorted_red_numbers, tuple):
            _reject(
                "six_red_value_type_invalid",
                "stored six-red numbers must use the immutable tuple representation",
            )
        canonical = _validate_numbers(
            self.sorted_red_numbers,
            universe=SIX_RED_UNIVERSE,
            code="invalid_six_red_combination",
            label="six-red combination numbers",
        )
        object.__setattr__(
            self,
            "combination_id",
            candidate_record_digest(canonical, universe=SIX_RED_UNIVERSE),
        )
        object.__setattr__(
            self,
            "red_mask",
            candidate_mask(canonical, universe=SIX_RED_UNIVERSE),
        )
        object.__setattr__(
            self,
            "lex_id",
            candidate_rank(canonical, universe=SIX_RED_UNIVERSE),
        )

    @classmethod
    def from_numbers(cls, numbers: Sequence[object]) -> SixRedCombination:
        canonical = _validate_numbers(
            numbers,
            universe=SIX_RED_UNIVERSE,
            code="invalid_six_red_combination",
            label="six-red combination numbers",
        )
        return cls(sorted_red_numbers=canonical)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "combination_id": self.combination_id,
            "sorted_red_numbers": list(self.sorted_red_numbers),
            "red_mask": self.red_mask,
            "lex_id": self.lex_id,
        }


@dataclass(frozen=True)
class ExpandedSixRedCombination:
    source_candidate_id: str
    source_sorted_red_numbers: tuple[int, ...]
    ordinal: int
    omitted_red_number: int
    six_red: SixRedCombination
    expansion_id: str = field(init=False)

    def __post_init__(self) -> None:
        _require_digest(self.source_candidate_id, field_name="source_candidate_id")
        if not isinstance(self.source_sorted_red_numbers, tuple):
            _reject(
                "expansion_source_type_invalid",
                "expansion source numbers must use the immutable tuple representation",
            )
        source = SevenRedCandidate(self.source_sorted_red_numbers)
        if self.source_candidate_id != source.candidate_id:
            _reject(
                "expansion_source_identity_mismatch",
                "source candidate ID does not match source numbers",
            )
        if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool) or not 1 <= self.ordinal <= 7:
            _reject(
                "expansion_ordinal_invalid",
                "expansion ordinal must be an integer in [1,7]",
                ordinal=self.ordinal,
            )
        if not isinstance(self.six_red, SixRedCombination):
            _reject(
                "expansion_six_red_type_invalid",
                "expansion must contain a canonical SixRedCombination",
            )
        expected_rows = tuple(combinations(source.sorted_red_numbers, 6))
        expected_numbers = expected_rows[self.ordinal - 1]
        if self.six_red.sorted_red_numbers != expected_numbers:
            _reject(
                "expansion_order_or_value_mismatch",
                "expanded six-red numbers do not match the source and ordinal",
                ordinal=self.ordinal,
            )
        omitted = next(
            number
            for number in source.sorted_red_numbers
            if number not in self.six_red.sorted_red_numbers
        )
        if self.omitted_red_number != omitted:
            _reject(
                "expansion_omission_mismatch",
                "omitted red number does not match the expanded six-red subset",
                expected=omitted,
                actual=self.omitted_red_number,
            )
        object.__setattr__(
            self,
            "expansion_id",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.expanded-six-red.v1",
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_EXPANSION_VERSION,
            "source_candidate_id": self.source_candidate_id,
            "source_sorted_red_numbers": list(self.source_sorted_red_numbers),
            "ordinal": self.ordinal,
            "omitted_red_number": self.omitted_red_number,
            "six_red": self.six_red.identity_payload(),
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "expansion_id": self.expansion_id}


def expand_seven_red_candidate(
    candidate: SevenRedCandidate,
) -> tuple[ExpandedSixRedCombination, ...]:
    if not isinstance(candidate, SevenRedCandidate):
        _reject(
            "seven_red_candidate_type_invalid",
            "expansion requires a SevenRedCandidate",
        )
    expanded: list[ExpandedSixRedCombination] = []
    for ordinal, numbers in enumerate(combinations(candidate.sorted_red_numbers, 6), start=1):
        omitted = next(number for number in candidate.sorted_red_numbers if number not in numbers)
        expanded.append(
            ExpandedSixRedCombination(
                source_candidate_id=candidate.candidate_id,
                source_sorted_red_numbers=candidate.sorted_red_numbers,
                ordinal=ordinal,
                omitted_red_number=omitted,
                six_red=SixRedCombination(numbers),
            )
        )
    result = tuple(expanded)
    if len(result) != 7 or len({item.six_red.combination_id for item in result}) != 7:
        _reject(
            "seven_red_expansion_invariant_failed",
            "one seven-red candidate must expand to exactly seven unique six-red combinations",
        )
    return result


@dataclass(frozen=True)
class SevenRedExpansionBatch:
    candidates: tuple[SevenRedCandidate, ...]
    expansions: tuple[ExpandedSixRedCombination, ...]
    batch_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.candidates, tuple) or not self.candidates:
            _reject(
                "seven_red_batch_candidates_invalid",
                "expansion batch requires a non-empty tuple of SevenRedCandidate values",
            )
        if any(not isinstance(candidate, SevenRedCandidate) for candidate in self.candidates):
            _reject(
                "seven_red_batch_candidate_type_invalid",
                "expansion batch contains a non-SevenRedCandidate value",
            )
        candidate_ids = tuple(candidate.candidate_id for candidate in self.candidates)
        if len(set(candidate_ids)) != len(candidate_ids):
            _reject(
                "duplicate_seven_red_candidate",
                "expansion batch contains duplicate seven-red candidates",
            )
        expected_expansions = tuple(
            expansion
            for candidate in self.candidates
            for expansion in expand_seven_red_candidate(candidate)
        )
        if not isinstance(self.expansions, tuple) or self.expansions != expected_expansions:
            _reject(
                "seven_red_batch_expansion_mismatch",
                "batch expansions must exactly match deterministic source expansion order",
            )
        first_source_by_six_red: dict[str, str] = {}
        for expansion in self.expansions:
            six_red_id = expansion.six_red.combination_id
            previous_source = first_source_by_six_red.get(six_red_id)
            if previous_source is not None:
                _reject(
                    "duplicate_expanded_six_red",
                    "different seven-red candidates produced duplicate six-red coverage",
                    six_red_id=six_red_id,
                    first_source_candidate_id=previous_source,
                    duplicate_source_candidate_id=expansion.source_candidate_id,
                )
            first_source_by_six_red[six_red_id] = expansion.source_candidate_id
        object.__setattr__(
            self,
            "batch_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.expansion-batch.v1",
            ),
        )

    @classmethod
    def build(
        cls,
        candidates: Sequence[SevenRedCandidate],
    ) -> SevenRedExpansionBatch:
        frozen_candidates = tuple(candidates)
        expansions = tuple(
            expansion
            for candidate in frozen_candidates
            for expansion in expand_seven_red_candidate(candidate)
        )
        return cls(candidates=frozen_candidates, expansions=expansions)

    @property
    def expanded_unique_count(self) -> int:
        return len({item.six_red.combination_id for item in self.expansions})

    @property
    def effective_coverage_ratio(self) -> float:
        return self.expanded_unique_count / (len(self.candidates) * 7)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": "seven_red_expansion_batch.v1",
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": SEVEN_RED_DOMAIN_CONTRACT_V1.normative_identity(),
            "source_candidate_ids": [candidate.candidate_id for candidate in self.candidates],
            "expansion_ids": [expansion.expansion_id for expansion in self.expansions],
            "expanded_unique_count": self.expanded_unique_count,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "effective_coverage_ratio": self.effective_coverage_ratio,
            "expansions": [expansion.as_dict() for expansion in self.expansions],
            "batch_digest": self.batch_digest,
        }


@dataclass(frozen=True)
class ExpandedSixRedHit:
    expansion: ExpandedSixRedCombination
    matched_red_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.expansion, ExpandedSixRedCombination):
            _reject(
                "expanded_hit_expansion_type_invalid",
                "expanded hit must reference an ExpandedSixRedCombination",
            )
        if (
            not isinstance(self.matched_red_count, int)
            or isinstance(self.matched_red_count, bool)
            or not 0 <= self.matched_red_count <= 6
        ):
            _reject(
                "expanded_hit_count_invalid",
                "expanded six-red hit count must be an integer in [0,6]",
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "expansion_id": self.expansion.expansion_id,
            "six_red_id": self.expansion.six_red.combination_id,
            "sorted_red_numbers": list(self.expansion.six_red.sorted_red_numbers),
            "matched_red_count": self.matched_red_count,
        }


@dataclass(frozen=True)
class SevenRedSettlement:
    candidate: SevenRedCandidate
    actual: SixRedCombination
    expanded_hits: tuple[ExpandedSixRedHit, ...]
    hit_count: int = field(init=False)
    expanded_hit_counts: tuple[int, ...] = field(init=False)
    settlement_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, SevenRedCandidate):
            _reject(
                "settlement_candidate_type_invalid",
                "settlement requires a SevenRedCandidate",
            )
        if not isinstance(self.actual, SixRedCombination):
            _reject(
                "settlement_actual_type_invalid",
                "settlement requires a canonical SixRedCombination actual outcome",
            )
        expected_expansions = expand_seven_red_candidate(self.candidate)
        if not isinstance(self.expanded_hits, tuple) or len(self.expanded_hits) != 7:
            _reject(
                "settlement_expanded_hits_invalid",
                "settlement requires exactly seven expanded hit records",
            )
        actual_set = set(self.actual.sorted_red_numbers)
        counts = [0] * 7
        for expected, observed in zip(expected_expansions, self.expanded_hits):
            if not isinstance(observed, ExpandedSixRedHit) or observed.expansion != expected:
                _reject(
                    "settlement_expansion_mismatch",
                    "settlement expanded hits do not match deterministic expansion order",
                )
            expected_count = len(actual_set.intersection(expected.six_red.sorted_red_numbers))
            if observed.matched_red_count != expected_count:
                _reject(
                    "settlement_hit_count_mismatch",
                    "expanded hit count does not match the actual outcome",
                    expansion_id=expected.expansion_id,
                    expected=expected_count,
                    actual=observed.matched_red_count,
                )
            counts[expected_count] += 1
        hit_count = len(actual_set.intersection(self.candidate.sorted_red_numbers))
        expected_counts = [0] * 7
        expected_counts[hit_count] += 7 - hit_count
        if hit_count > 0:
            expected_counts[hit_count - 1] += hit_count
        if counts != expected_counts or sum(counts) != 7:
            _reject(
                "settlement_combinatorial_identity_failed",
                "expanded settlement does not satisfy the seven-to-six omission identity",
                hit_count=hit_count,
                expected=expected_counts,
                actual=counts,
            )
        object.__setattr__(self, "hit_count", hit_count)
        object.__setattr__(self, "expanded_hit_counts", tuple(counts))
        object.__setattr__(
            self,
            "settlement_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.settlement.v1",
            ),
        )

    @classmethod
    def evaluate(
        cls,
        *,
        candidate: SevenRedCandidate,
        actual_red_numbers: Sequence[object],
    ) -> SevenRedSettlement:
        actual = SixRedCombination.from_numbers(actual_red_numbers)
        actual_set = set(actual.sorted_red_numbers)
        expanded_hits = tuple(
            ExpandedSixRedHit(
                expansion=expansion,
                matched_red_count=len(
                    actual_set.intersection(expansion.six_red.sorted_red_numbers)
                ),
            )
            for expansion in expand_seven_red_candidate(candidate)
        )
        return cls(candidate=candidate, actual=actual, expanded_hits=expanded_hits)

    def expanded_count(self, matched_red_count: int) -> int:
        if (
            not isinstance(matched_red_count, int)
            or isinstance(matched_red_count, bool)
            or not 0 <= matched_red_count <= 6
        ):
            _reject(
                "settlement_count_query_invalid",
                "matched_red_count query must be an integer in [0,6]",
            )
        return self.expanded_hit_counts[matched_red_count]

    @property
    def expanded_red6_count(self) -> int:
        return self.expanded_hit_counts[6]

    @property
    def expanded_red5_count(self) -> int:
        return self.expanded_hit_counts[5]

    @property
    def expanded_red4_count(self) -> int:
        return self.expanded_hit_counts[4]

    @property
    def expanded_red3_count(self) -> int:
        return self.expanded_hit_counts[3]

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_SETTLEMENT_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": SEVEN_RED_DOMAIN_CONTRACT_V1.normative_identity(),
            "candidate_id": self.candidate.candidate_id,
            "actual_combination_id": self.actual.combination_id,
            "actual_red_numbers": list(self.actual.sorted_red_numbers),
            "hit_count": self.hit_count,
            "expanded_hit_counts": list(self.expanded_hit_counts),
            "expanded_hits": [hit.as_dict() for hit in self.expanded_hits],
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "settlement_digest": self.settlement_digest}
