from __future__ import annotations

import json
from collections import Counter
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
from itertools import combinations
from math import comb

import pytest

from dehps.seven_red import (
    DIVERSIFIED_TOP10_SELECTOR_CONTRACT,
    DIVERSIFIED_TOP10_SIZE,
    DIVERSIFIED_TOP10_SNAPSHOT_VERSION,
    SEVEN_RED_DIVERSIFIED_TOP10_CONTRACT_V1,
    SEVEN_RED_DIVERSITY_AUDIT_CONTRACT_V1,
    DiversifiedSevenRedTop10Snapshot,
    ExactUtilityComponents,
    PreScoredSevenRedCandidateList,
    RawSevenRedTop10Snapshot,
    ScoredSevenRedCandidate,
    SevenRedCandidate,
    SevenRedDiversificationWeights,
    SevenRedDiversifiedTop10Violation,
    SevenRedDiversityAuditSnapshot,
)
from dehps.seven_red.diversified import (
    EXPOSURE_SQUARE_DENOMINATOR,
    PAIR_COVERAGE_DENOMINATOR,
    SEVEN_RED_DIVERSIFIED_GOLDEN_SUITE,
    SEVEN_RED_DIVERSIFIED_NORMATIVE_DEFINITION,
    TRIPLE_COVERAGE_DENOMINATOR,
)
from dehps.seven_red.domain import expand_seven_red_candidate
from dehps.seven_red.raw_top10 import SEVEN_RED_RAW_TOP10_GOLDEN_SUITE


def scored_row(
    numbers: tuple[int, ...],
    normalized_score: float,
    *,
    source_run_id: str = "diversified-fixture-run-v1",
) -> ScoredSevenRedCandidate:
    candidate = SevenRedCandidate.from_numbers(numbers)
    return ScoredSevenRedCandidate.build(
        candidate=candidate,
        raw_score=normalized_score * 10.0,
        normalized_score=normalized_score,
        source_model="diversified-fixture-model-v1",
        feature_digest=f"{candidate.lex_id + 1:064x}",
        source_run_id=source_run_id,
    )


def golden_rows() -> tuple[ScoredSevenRedCandidate, ...]:
    suite = SEVEN_RED_DIVERSIFIED_GOLDEN_SUITE
    return tuple(
        scored_row(tuple(numbers), score)
        for numbers, score in zip(
            suite["source_candidates"],
            suite["normalized_scores_descending"],
            strict=True,
        )
    )


def golden_audit(
    rows: tuple[ScoredSevenRedCandidate, ...] | None = None,
) -> SevenRedDiversityAuditSnapshot:
    pool = PreScoredSevenRedCandidateList.build(rows or golden_rows())
    raw = RawSevenRedTop10Snapshot.build(pool)
    return SevenRedDiversityAuditSnapshot.build(pool, raw)


def golden_weights() -> SevenRedDiversificationWeights:
    return SevenRedDiversificationWeights.from_mapping(
        SEVEN_RED_DIVERSIFIED_GOLDEN_SUITE["weights"]
    )


def source_ranking(
    audit: SevenRedDiversityAuditSnapshot,
) -> tuple[ScoredSevenRedCandidate, ...]:
    return tuple(
        sorted(
            audit.source_candidate_pool.rows,
            key=lambda row: (-row.ranking_score, row.candidate.lex_id),
        )
    )


def independent_utility(
    selected: tuple[ScoredSevenRedCandidate, ...],
    *,
    audit: SevenRedDiversityAuditSnapshot,
    weights: SevenRedDiversificationWeights,
) -> tuple[Fraction, tuple[Fraction, Fraction, Fraction, Fraction]]:
    ranked = source_ranking(audit)
    ranks = {
        row.candidate.candidate_id: rank
        for rank, row in enumerate(ranked, start=1)
    }
    source_count = len(ranked)
    quality = weights.source_quality_weight * sum(
        (
            Fraction(source_count - ranks[row.candidate.candidate_id] + 1, source_count)
            for row in selected
        ),
        start=Fraction(0),
    ) / DIVERSIFIED_TOP10_SIZE
    pairs = {
        core
        for row in selected
        for core in combinations(row.candidate.sorted_red_numbers, 2)
    }
    triples = {
        core
        for row in selected
        for core in combinations(row.candidate.sorted_red_numbers, 3)
    }
    counts = Counter(
        number for row in selected for number in row.candidate.sorted_red_numbers
    )
    pair_component = Fraction(
        weights.pair_coverage_weight * len(pairs),
        PAIR_COVERAGE_DENOMINATOR,
    )
    triple_component = Fraction(
        weights.triple_coverage_weight * len(triples),
        TRIPLE_COVERAGE_DENOMINATOR,
    )
    exposure = Fraction(
        -weights.exposure_balance_weight * sum(value * value for value in counts.values()),
        EXPOSURE_SQUARE_DENOMINATOR,
    )
    components = (quality, pair_component, triple_component, exposure)
    return sum(components, start=Fraction(0)), components


def expansion_ids(row: ScoredSevenRedCandidate) -> frozenset[str]:
    return frozenset(
        expansion.six_red.combination_id
        for expansion in expand_seven_red_candidate(row.candidate)
    )


def test_contract_binds_diversity_audit_and_has_no_default_configuration() -> None:
    definition = SEVEN_RED_DIVERSIFIED_NORMATIVE_DEFINITION

    assert DIVERSIFIED_TOP10_SIZE == 10
    assert DIVERSIFIED_TOP10_SNAPSHOT_VERSION.endswith("snapshot.v1")
    assert DIVERSIFIED_TOP10_SELECTOR_CONTRACT.endswith("unique70.v1")
    assert SEVEN_RED_DIVERSIFIED_TOP10_CONTRACT_V1.family == (
        "seven-red-diversified-top10"
    )
    assert definition["dependencies"]["seven_red_diversity_audit"] == (
        SEVEN_RED_DIVERSITY_AUDIT_CONTRACT_V1.normative_identity()
    )
    assert definition["configuration"]["default"] == "absent"
    assert definition["configuration"]["recommendation"] == "absent"
    assert definition["greedy_selection"]["global_optimality"] == "not_claimed"
    assert SEVEN_RED_DIVERSIFIED_TOP10_CONTRACT_V1.normative_digest == (
        "e7118cfd74402fe87de50b954a3c89d84c4465af692fc5a57f8a9b941b10f6cc"
    )


@pytest.mark.parametrize(
    ("values", "code"),
    [
        ((True, 0, 0, 0), "seven_red_diversified_weight_invalid"),
        ((-1, 0, 0, 0), "seven_red_diversified_weight_invalid"),
        ((1.0, 0, 0, 0), "seven_red_diversified_weight_invalid"),
        ((0, 0, 0, 0), "seven_red_diversified_weight_vector_zero"),
        ((2, 4, 0, 0), "seven_red_diversified_weight_vector_nonprimitive"),
    ],
)
def test_weight_vector_rejects_ambiguous_or_noncanonical_values(
    values: tuple[object, object, object, object],
    code: str,
) -> None:
    with pytest.raises(SevenRedDiversifiedTop10Violation) as error:
        SevenRedDiversificationWeights(*values)  # type: ignore[arg-type]
    assert error.value.code == code


def test_weight_mapping_rejects_missing_or_unknown_fields() -> None:
    valid = dict(SEVEN_RED_DIVERSIFIED_GOLDEN_SUITE["weights"])
    missing = dict(valid)
    missing.pop("pair_coverage_weight")
    unexpected = {**valid, "secret_default": 1}

    with pytest.raises(SevenRedDiversifiedTop10Violation) as missing_error:
        SevenRedDiversificationWeights.from_mapping(missing)
    assert missing_error.value.code == "seven_red_diversified_weight_fields_invalid"
    assert missing_error.value.context["missing"] == ["pair_coverage_weight"]

    with pytest.raises(SevenRedDiversifiedTop10Violation) as unexpected_error:
        SevenRedDiversificationWeights.from_mapping(unexpected)
    assert unexpected_error.value.code == "seven_red_diversified_weight_fields_invalid"
    assert unexpected_error.value.context["unexpected"] == ["secret_default"]

    with pytest.raises(SevenRedDiversifiedTop10Violation) as non_text_error:
        SevenRedDiversificationWeights.from_mapping({**valid, 7: 1})
    assert non_text_error.value.code == "seven_red_diversified_weight_fields_invalid"
    assert non_text_error.value.context["unexpected"] == [7]


def test_weight_configuration_is_immutable_and_digest_addressed() -> None:
    first = golden_weights()
    second = SevenRedDiversificationWeights(1, 1, 1, 1)

    assert first == second
    assert first.configuration_digest == second.configuration_digest
    assert first.as_dict()["default_policy"] is None
    with pytest.raises(FrozenInstanceError):
        first.source_quality_weight = 2  # type: ignore[misc]


def test_golden_selector_is_deterministic_and_freezes_all_identities() -> None:
    audit = golden_audit()
    weights = golden_weights()
    snapshot = DiversifiedSevenRedTop10Snapshot.build(audit, weights)
    golden = SEVEN_RED_DIVERSIFIED_GOLDEN_SUITE

    assert [step.scored_candidate.candidate.lex_id for step in snapshot.steps] == (
        golden["expected_selected_lex_ids"]
    )
    assert weights.configuration_digest == golden["expected_configuration_digest"]
    assert snapshot.snapshot_digest == golden["expected_snapshot_digest"]
    assert [step.diversified_rank for step in snapshot.steps] == list(range(1, 11))
    assert snapshot.final_metrics.candidate_count == 10


def test_selection_replays_across_source_input_permutations() -> None:
    rows = golden_rows()
    first = DiversifiedSevenRedTop10Snapshot.build(golden_audit(rows), golden_weights())
    second = DiversifiedSevenRedTop10Snapshot.build(
        golden_audit(tuple(reversed(rows))),
        golden_weights(),
    )
    rotated = DiversifiedSevenRedTop10Snapshot.build(
        golden_audit((*rows[5:], *rows[:5])),
        golden_weights(),
    )

    assert first == second == rotated
    assert first.as_dict() == second.as_dict() == rotated.as_dict()
    assert first.snapshot_digest == second.snapshot_digest == rotated.snapshot_digest


def test_every_step_is_independently_the_exact_best_feasible_choice() -> None:
    audit = golden_audit()
    weights = golden_weights()
    snapshot = DiversifiedSevenRedTop10Snapshot.build(audit, weights)
    ranked = source_ranking(audit)
    ranks = {
        row.candidate.candidate_id: rank
        for rank, row in enumerate(ranked, start=1)
    }
    selected: tuple[ScoredSevenRedCandidate, ...] = ()
    used_expansions: set[str] = set()
    before_total, _ = independent_utility(selected, audit=audit, weights=weights)

    for step in snapshot.steps:
        choices = []
        for row in ranked:
            if row in selected or expansion_ids(row) & used_expansions:
                continue
            after_total, _ = independent_utility(
                (*selected, row),
                audit=audit,
                weights=weights,
            )
            quality = Fraction(
                len(ranked) - ranks[row.candidate.candidate_id] + 1,
                len(ranked),
            )
            choices.append(
                (
                    after_total - before_total,
                    quality,
                    -row.candidate.lex_id,
                    row,
                )
            )
        expected = max(choices, key=lambda item: item[:3])[3]
        assert step.scored_candidate == expected
        selected = (*selected, expected)
        used_expansions.update(expansion_ids(expected))
        before_total, _ = independent_utility(
            selected,
            audit=audit,
            weights=weights,
        )


def test_score_only_axis_retains_highest_feasible_source_ranks() -> None:
    audit = golden_audit()
    weights = SevenRedDiversificationWeights(1, 0, 0, 0)
    snapshot = DiversifiedSevenRedTop10Snapshot.build(audit, weights)

    assert [step.source_rank for step in snapshot.steps] == [1, 5, 6, 7, 8, 9, 10, 11, 12, 13]
    assert all(step.marginal_utility.pair_coverage == 0 for step in snapshot.steps)
    assert all(step.marginal_utility.triple_coverage == 0 for step in snapshot.steps)
    assert all(step.marginal_utility.exposure_penalty == 0 for step in snapshot.steps)


@pytest.mark.parametrize(
    ("weights", "nonzero_field"),
    [
        (SevenRedDiversificationWeights(0, 1, 0, 0), "pair_coverage"),
        (SevenRedDiversificationWeights(0, 0, 1, 0), "triple_coverage"),
        (SevenRedDiversificationWeights(0, 0, 0, 1), "exposure_penalty"),
    ],
)
def test_each_structural_coefficient_axis_is_explicit(
    weights: SevenRedDiversificationWeights,
    nonzero_field: str,
) -> None:
    snapshot = DiversifiedSevenRedTop10Snapshot.build(golden_audit(), weights)

    for step in snapshot.steps:
        components = step.marginal_utility
        assert components.source_quality == 0
        for field_name in ("pair_coverage", "triple_coverage", "exposure_penalty"):
            value = getattr(components, field_name)
            if field_name == nonzero_field:
                assert value != 0
            else:
                assert value == 0


def test_equal_marginal_utility_uses_higher_source_quality_tie_break() -> None:
    audit = golden_audit()
    exposure_only = SevenRedDiversificationWeights(0, 0, 0, 1)
    snapshot = DiversifiedSevenRedTop10Snapshot.build(audit, exposure_only)

    assert snapshot.steps[0].source_rank == 1
    assert snapshot.steps[0].source_quality == 1


def test_selected_rows_are_unchanged_pool_members_and_raw_control_is_unchanged() -> None:
    audit = golden_audit()
    raw_before = audit.source_raw_top10.as_dict()
    snapshot = DiversifiedSevenRedTop10Snapshot.build(audit, golden_weights())
    source_by_digest = {
        row.row_digest: row for row in audit.source_candidate_pool.rows
    }

    for step in snapshot.steps:
        source = source_by_digest[step.scored_candidate.row_digest]
        assert step.scored_candidate == source
        assert step.scored_candidate.raw_score == source.raw_score
        assert step.scored_candidate.normalized_score == source.normalized_score
        assert step.scored_candidate.source_model == source.source_model
        assert step.scored_candidate.feature_digest == source.feature_digest
        assert step.scored_candidate.source_run_id == source.source_run_id
    assert audit.source_raw_top10.as_dict() == raw_before
    assert snapshot.as_dict()["source_raw_top10_snapshot_digest"] == (
        audit.source_raw_top10.snapshot_digest
    )


def test_final_selection_has_exactly_seventy_unique_expansions() -> None:
    snapshot = DiversifiedSevenRedTop10Snapshot.build(
        golden_audit(),
        golden_weights(),
    )
    metrics = snapshot.final_metrics

    assert sum(step.new_expansion_count for step in snapshot.steps) == 70
    assert metrics.expansion_geometry.total_expansion_slots == 70
    assert metrics.expansion_geometry.unique_expansion_count == 70
    assert metrics.expansion_geometry.duplicate_expansion_slot_count == 0
    assert metrics.expansion_geometry.collisions == ()
    assert metrics.overlap_histogram[6] == 0


def test_step_marginals_telescope_to_cumulative_exact_utility() -> None:
    snapshot = DiversifiedSevenRedTop10Snapshot.build(
        golden_audit(),
        golden_weights(),
    )
    cumulative = ExactUtilityComponents.from_terms(
        source_quality=Fraction(0),
        pair_coverage=Fraction(0),
        triple_coverage=Fraction(0),
        exposure_penalty=Fraction(0),
    )
    for step in snapshot.steps:
        cumulative = ExactUtilityComponents.from_terms(
            source_quality=(
                cumulative.source_quality + step.marginal_utility.source_quality
            ),
            pair_coverage=(
                cumulative.pair_coverage + step.marginal_utility.pair_coverage
            ),
            triple_coverage=(
                cumulative.triple_coverage + step.marginal_utility.triple_coverage
            ),
            exposure_penalty=(
                cumulative.exposure_penalty + step.marginal_utility.exposure_penalty
            ),
        )
        assert cumulative == step.cumulative_utility


def test_infeasible_shared_six_core_pool_fails_without_partial_snapshot() -> None:
    rows = tuple(
        scored_row(
            (1, 2, 3, 4, 5, 6, int(case["extra_red"])),
            float(case["normalized_score"]),
        )
        for case in SEVEN_RED_RAW_TOP10_GOLDEN_SUITE["source_candidates"]
    )
    audit = golden_audit(rows)

    with pytest.raises(SevenRedDiversifiedTop10Violation) as error:
        DiversifiedSevenRedTop10Snapshot.build(audit, golden_weights())
    assert error.value.code == "seven_red_diversified_infeasible_pool"
    assert error.value.context["selected_count"] == 1
    assert error.value.context["required"] == 10


def test_tampered_step_order_or_final_metrics_fail_recomputation() -> None:
    audit = golden_audit()
    weights = golden_weights()
    valid = DiversifiedSevenRedTop10Snapshot.build(audit, weights)

    with pytest.raises(SevenRedDiversifiedTop10Violation) as steps_error:
        DiversifiedSevenRedTop10Snapshot(
            source_audit=audit,
            weights=weights,
            steps=(valid.steps[1], valid.steps[0], *valid.steps[2:]),
            final_metrics=valid.final_metrics,
        )
    assert steps_error.value.code == "seven_red_diversified_steps_mismatch"

    with pytest.raises(SevenRedDiversifiedTop10Violation) as metrics_error:
        DiversifiedSevenRedTop10Snapshot(
            source_audit=audit,
            weights=weights,
            steps=valid.steps,
            final_metrics=audit.raw_top10_metrics,
        )
    assert metrics_error.value.code == "seven_red_diversified_final_metrics_mismatch"


def test_direct_fraction_and_step_tampering_fail_closed() -> None:
    snapshot = DiversifiedSevenRedTop10Snapshot.build(
        golden_audit(),
        golden_weights(),
    )
    first = snapshot.steps[0]

    with pytest.raises(SevenRedDiversifiedTop10Violation) as fraction_error:
        replace(first, source_quality=1.0)  # type: ignore[arg-type]
    assert fraction_error.value.code == "seven_red_diversified_fraction_invalid"

    with pytest.raises(SevenRedDiversifiedTop10Violation) as expansion_error:
        replace(first, new_expansion_count=6)
    assert expansion_error.value.code == (
        "seven_red_diversified_step_expansion_gain_invalid"
    )


def test_snapshot_payload_is_seedless_outcome_blind_and_not_an_optimality_claim() -> None:
    snapshot = DiversifiedSevenRedTop10Snapshot.build(
        golden_audit(),
        golden_weights(),
    )
    payload = json.loads(json.dumps(snapshot.as_dict()))
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["research_only"] is True
    assert payload["deterministic"] is True
    assert payload["seed_policy"] is None
    assert payload["outcome_inputs"] is None
    assert payload["global_optimality_claim"] is False
    assert payload["selection_status"].endswith("not_trained_configuration")
    assert payload["utility_contract"] == {
        "arithmetic": "exact_fraction",
        "budget": 10,
        "pair_coverage_denominator": 210,
        "triple_coverage_denominator": 350,
        "exposure_square_denominator": 4900,
        "expansion_constraint": "each_step_adds_exactly_7_new_six_red_tickets",
        "tie_breaks": ["higher_source_quality", "lower_lex_id"],
    }
    assert "created_at" not in serialized
    assert "actual_red" not in serialized
    assert "target_draw" not in serialized
    assert "settlement" not in serialized
    assert "recommended_weight" not in serialized
