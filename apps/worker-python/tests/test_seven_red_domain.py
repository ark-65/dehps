from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError
from itertools import combinations

import pytest

from dehps.input_contracts.candidate_abi import candidate_numbers_from_mask
from dehps.seven_red import (
    LINE_KEY,
    RESEARCH_ONLY,
    SEVEN_RED_DOMAIN_CONTRACT_V1,
    SEVEN_RED_UNIVERSE,
    SIX_RED_UNIVERSE,
    ExpandedSixRedHit,
    SevenRedCandidate,
    SevenRedContractViolation,
    SevenRedExpansionBatch,
    SevenRedSettlement,
    SixRedCombination,
    expand_seven_red_candidate,
)
from dehps.seven_red.domain import SEVEN_RED_GOLDEN_SUITE


def candidate() -> SevenRedCandidate:
    return SevenRedCandidate.from_numbers((1, 2, 3, 4, 5, 6, 7))


def test_domain_contract_freezes_research_line_and_combination_math() -> None:
    assert LINE_KEY == "seven_red_compound_top10"
    assert RESEARCH_ONLY is True
    assert SEVEN_RED_UNIVERSE.cardinality == math.comb(33, 7) == 4_272_048
    assert SIX_RED_UNIVERSE.cardinality == math.comb(33, 6) == 1_107_568
    assert math.comb(7, 6) == 7
    assert SEVEN_RED_DOMAIN_CONTRACT_V1.family == "seven-red-domain"
    assert SEVEN_RED_DOMAIN_CONTRACT_V1.semantic_version == "1.0.0"


def test_candidate_identity_mask_and_lex_id_match_the_golden_contract() -> None:
    case = SEVEN_RED_GOLDEN_SUITE["candidate"]
    first = SevenRedCandidate.from_numbers(case["sorted_red_numbers"])
    second = SevenRedCandidate.from_numbers(tuple(case["sorted_red_numbers"]))

    assert first == second
    assert first.sorted_red_numbers == tuple(case["sorted_red_numbers"])
    assert first.candidate_id == case["candidate_id"]
    assert first.red_mask == case["red_mask"]
    assert first.lex_id == case["lex_id"]
    assert candidate_numbers_from_mask(first.red_mask, universe=SEVEN_RED_UNIVERSE) == (
        1,
        2,
        3,
        4,
        5,
        6,
        7,
    )
    assert json.dumps(first.as_dict(), sort_keys=True, separators=(",", ":")) == json.dumps(
        second.as_dict(), sort_keys=True, separators=(",", ":")
    )
    with pytest.raises(FrozenInstanceError):
        first.lex_id = 1  # type: ignore[misc]


def test_candidate_identity_covers_the_last_legal_seven_red_row() -> None:
    last = SevenRedCandidate.from_numbers((27, 28, 29, 30, 31, 32, 33))

    assert last.lex_id == SEVEN_RED_UNIVERSE.cardinality - 1 == 4_272_047
    assert last.red_mask == 8_522_825_728
    assert (
        last.candidate_id
        == "010120b6b749a48490a0ec81d2bda26d8c52a9ec1bbc9a20ac58e11ee9cb05ef"
    )
    assert candidate_numbers_from_mask(last.red_mask, universe=SEVEN_RED_UNIVERSE) == (
        27,
        28,
        29,
        30,
        31,
        32,
        33,
    )


@pytest.mark.parametrize(
    ("numbers", "cause"),
    [
        ((2, 1, 3, 4, 5, 6, 7), "noncanonical_candidate_numbers"),
        ((1, 2, 3, 4, 5, 6, 6), "noncanonical_candidate_numbers"),
        ((0, 2, 3, 4, 5, 6, 7), "candidate_number_out_of_range"),
        ((1, 2, 3, 4, 5, 6, 34), "candidate_number_out_of_range"),
        ((1, 2, 3, 4, 5, 6), "invalid_candidate_shape"),
        ((1, 2, 3, 4, 5, 6, True), "invalid_candidate_number_type"),
        ((1, 2, 3, 4, 5, 6, 7.0), "invalid_candidate_number_type"),
    ],
)
def test_candidate_rejects_invalid_or_noncanonical_values_without_repair(
    numbers: tuple[object, ...],
    cause: str,
) -> None:
    with pytest.raises(SevenRedContractViolation) as error:
        SevenRedCandidate.from_numbers(numbers)
    assert error.value.code == "invalid_seven_red_candidate"
    assert error.value.context["cause"] == cause

    if len(numbers) == 7:
        with pytest.raises(SevenRedContractViolation):
            SevenRedCandidate(numbers)  # type: ignore[arg-type]


def test_stored_value_representation_is_fail_closed() -> None:
    with pytest.raises(SevenRedContractViolation) as seven_error:
        SevenRedCandidate([1, 2, 3, 4, 5, 6, 7])  # type: ignore[arg-type]
    assert seven_error.value.code == "seven_red_value_type_invalid"

    with pytest.raises(SevenRedContractViolation) as six_error:
        SixRedCombination([1, 2, 3, 4, 5, 6])  # type: ignore[arg-type]
    assert six_error.value.code == "six_red_value_type_invalid"


def test_expansion_is_complete_unique_lexicographic_and_provenance_bound() -> None:
    source = candidate()
    first = expand_seven_red_candidate(source)
    second = expand_seven_red_candidate(source)
    golden = SEVEN_RED_GOLDEN_SUITE["expansion"]

    assert first == second
    assert len(first) == math.comb(7, 6) == 7
    assert [item.six_red.sorted_red_numbers for item in first] == list(
        combinations(source.sorted_red_numbers, 6)
    )
    assert [list(item.six_red.sorted_red_numbers) for item in first] == golden[
        "ordered_six_red_numbers"
    ]
    assert [item.omitted_red_number for item in first] == golden["omitted_red_numbers"]
    assert [item.ordinal for item in first] == list(range(1, 8))
    assert len({item.six_red.combination_id for item in first}) == golden["unique_count"]
    assert len({item.expansion_id for item in first}) == 7
    assert all(item.source_candidate_id == source.candidate_id for item in first)
    assert all(item.source_sorted_red_numbers == source.sorted_red_numbers for item in first)


def test_batch_is_digest_addressed_and_fails_closed_on_duplicate_coverage() -> None:
    left = candidate()
    right = SevenRedCandidate.from_numbers((8, 9, 10, 11, 12, 13, 14))
    first = SevenRedExpansionBatch.build((left, right))
    second = SevenRedExpansionBatch.build([left, right])

    assert first == second
    assert first.batch_digest == second.batch_digest
    assert len(first.expansions) == 14
    assert first.expanded_unique_count == 14
    assert first.effective_coverage_ratio == 1.0
    assert json.loads(json.dumps(first.as_dict()))["batch_digest"] == first.batch_digest

    with pytest.raises(SevenRedContractViolation) as duplicate_candidate:
        SevenRedExpansionBatch.build((left, left))
    assert duplicate_candidate.value.code == "duplicate_seven_red_candidate"

    shared_six_core = SevenRedCandidate.from_numbers((1, 2, 3, 4, 5, 6, 8))
    with pytest.raises(SevenRedContractViolation) as duplicate_expansion:
        SevenRedExpansionBatch.build((left, shared_six_core))
    assert duplicate_expansion.value.code == "duplicate_expanded_six_red"
    assert duplicate_expansion.value.context["first_source_candidate_id"] == left.candidate_id
    assert (
        duplicate_expansion.value.context["duplicate_source_candidate_id"]
        == shared_six_core.candidate_id
    )


@pytest.mark.parametrize(
    ("actual", "hit_count", "expanded_counts"),
    [
        ((1, 2, 3, 4, 5, 6), 6, (0, 0, 0, 0, 0, 6, 1)),
        ((1, 2, 3, 4, 5, 8), 5, (0, 0, 0, 0, 5, 2, 0)),
        ((1, 2, 3, 4, 8, 9), 4, (0, 0, 0, 4, 3, 0, 0)),
        ((8, 9, 10, 11, 12, 13), 0, (7, 0, 0, 0, 0, 0, 0)),
    ],
)
def test_settlement_proves_each_seven_to_six_hit_identity(
    actual: tuple[int, ...],
    hit_count: int,
    expanded_counts: tuple[int, ...],
) -> None:
    first = SevenRedSettlement.evaluate(candidate=candidate(), actual_red_numbers=actual)
    second = SevenRedSettlement.evaluate(candidate=candidate(), actual_red_numbers=list(actual))

    assert first == second
    assert first.settlement_digest == second.settlement_digest
    assert first.hit_count == hit_count
    assert first.expanded_hit_counts == expanded_counts
    assert sum(first.expanded_hit_counts) == 7
    assert first.expanded_red6_count == expanded_counts[6]
    assert first.expanded_red5_count == expanded_counts[5]
    assert first.expanded_red4_count == expanded_counts[4]
    assert first.expanded_red3_count == expanded_counts[3]
    assert [first.expanded_count(value) for value in range(7)] == list(expanded_counts)
    assert json.loads(json.dumps(first.as_dict()))["settlement_digest"] == first.settlement_digest


def test_required_settlement_cases_match_the_executable_golden_suite() -> None:
    for case in SEVEN_RED_GOLDEN_SUITE["settlement"]:
        result = SevenRedSettlement.evaluate(
            candidate=candidate(),
            actual_red_numbers=case["actual_red_numbers"],
        )
        assert result.hit_count == case["hit_count"]
        assert list(result.expanded_hit_counts) == case["expanded_hit_counts"]


def test_settlement_rejects_invalid_actual_and_tampered_expanded_counts() -> None:
    with pytest.raises(SevenRedContractViolation) as invalid_actual:
        SevenRedSettlement.evaluate(
            candidate=candidate(),
            actual_red_numbers=(1, 2, 3, 4, 5, 5),
        )
    assert invalid_actual.value.code == "invalid_six_red_combination"

    actual = SixRedCombination.from_numbers((1, 2, 3, 4, 5, 6))
    expansions = expand_seven_red_candidate(candidate())
    correct = tuple(
        ExpandedSixRedHit(
            expansion=expansion,
            matched_red_count=len(
                set(actual.sorted_red_numbers).intersection(expansion.six_red.sorted_red_numbers)
            ),
        )
        for expansion in expansions
    )
    tampered = (
        ExpandedSixRedHit(expansion=correct[0].expansion, matched_red_count=5),
        *correct[1:],
    )
    with pytest.raises(SevenRedContractViolation) as mismatch:
        SevenRedSettlement(candidate=candidate(), actual=actual, expanded_hits=tampered)
    assert mismatch.value.code == "settlement_hit_count_mismatch"
