from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from dehps.seven_red import (
    LINE_KEY,
    RAW_TOP10_RANKING_CONTRACT,
    RAW_TOP10_SIZE,
    RESEARCH_ONLY,
    SEVEN_RED_DOMAIN_CONTRACT_V1,
    SEVEN_RED_RAW_TOP10_CONTRACT_V1,
    PreScoredSevenRedCandidateList,
    RawSevenRedTop10Entry,
    RawSevenRedTop10Snapshot,
    ScoredSevenRedCandidate,
    SevenRedCandidate,
    SevenRedRawTop10Violation,
)
from dehps.seven_red.raw_top10 import (
    SEVEN_RED_RAW_TOP10_GOLDEN_SUITE,
    SEVEN_RED_RAW_TOP10_NORMATIVE_DEFINITION,
)


def scored_row(
    extra_red: int,
    normalized_score: object,
    *,
    raw_score: object | None = None,
    feature_digest: str | None = None,
    source_model: str = "fixture-model-v1",
    source_run_id: str = "fixture-run-v1",
) -> ScoredSevenRedCandidate:
    return ScoredSevenRedCandidate.build(
        candidate=SevenRedCandidate.from_numbers((1, 2, 3, 4, 5, 6, extra_red)),
        raw_score=(1.0 - float(normalized_score)) if raw_score is None else raw_score,
        normalized_score=normalized_score,
        source_model=source_model,
        feature_digest=feature_digest or f"{extra_red:064x}",
        source_run_id=source_run_id,
    )


def golden_rows() -> tuple[ScoredSevenRedCandidate, ...]:
    return tuple(
        scored_row(case["extra_red"], case["normalized_score"])
        for case in SEVEN_RED_RAW_TOP10_GOLDEN_SUITE["source_candidates"]
    )


def test_contract_is_research_only_and_binds_milestone_one_exactly() -> None:
    assert LINE_KEY == "seven_red_compound_top10"
    assert RESEARCH_ONLY is True
    assert RAW_TOP10_SIZE == 10
    assert RAW_TOP10_RANKING_CONTRACT.endswith("normalized_round8_desc_lex_id_asc.v1")
    assert SEVEN_RED_RAW_TOP10_CONTRACT_V1.family == "seven-red-raw-top10"
    assert (
        SEVEN_RED_RAW_TOP10_CONTRACT_V1.semantic_version
        == SEVEN_RED_DOMAIN_CONTRACT_V1.semantic_version
        == "1.0.0"
    )
    assert SEVEN_RED_RAW_TOP10_NORMATIVE_DEFINITION["dependencies"][
        "seven_red_domain"
    ] == SEVEN_RED_DOMAIN_CONTRACT_V1.normative_identity()
    assert (
        SEVEN_RED_RAW_TOP10_CONTRACT_V1.normative_digest
        == "cae99a1a4a834de93ba805153f82878c1ef3857e3c4856a1ae371e83785c1a65"
    )


def test_scored_row_preserves_scores_and_has_stable_digest() -> None:
    first = scored_row(7, Decimal("0.123456789"), raw_score=Decimal("9.87654321"))
    second = scored_row(7, 0.123456789, raw_score=9.87654321)

    assert first == second
    assert type(first.raw_score) is float
    assert type(first.normalized_score) is float
    assert first.raw_score == 9.87654321
    assert first.normalized_score == 0.123456789
    assert first.ranking_score == 0.12345679
    assert first.row_digest == second.row_digest
    assert json.loads(json.dumps(first.as_dict()))["row_digest"] == first.row_digest
    with pytest.raises(FrozenInstanceError):
        first.normalized_score = 1.0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("raw_score", True),
        ("raw_score", float("nan")),
        ("raw_score", float("inf")),
        ("raw_score", "0.5"),
        ("normalized_score", False),
        ("normalized_score", float("-inf")),
        ("normalized_score", object()),
    ],
)
def test_scored_row_rejects_non_finite_or_ambiguous_scores(field: str, value: object) -> None:
    values = {"raw_score": 0.4, "normalized_score": 0.6}
    values[field] = value
    with pytest.raises(SevenRedRawTop10Violation) as error:
        ScoredSevenRedCandidate.build(
            candidate=SevenRedCandidate.from_numbers((1, 2, 3, 4, 5, 6, 7)),
            raw_score=values["raw_score"],
            normalized_score=values["normalized_score"],
            source_model="model-v1",
            feature_digest="a" * 64,
            source_run_id="run-v1",
        )
    assert error.value.code == "seven_red_scored_candidate_score_invalid"
    assert error.value.context["field"] == field


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("source_model", "", "seven_red_scored_candidate_metadata_invalid"),
        ("source_model", " model", "seven_red_scored_candidate_metadata_invalid"),
        ("source_model", "model\nname", "seven_red_scored_candidate_metadata_invalid"),
        ("source_run_id", "run ", "seven_red_scored_candidate_metadata_invalid"),
        ("feature_digest", "A" * 64, "seven_red_raw_top10_digest_invalid"),
        ("feature_digest", "a" * 63, "seven_red_raw_top10_digest_invalid"),
    ],
)
def test_scored_row_rejects_malformed_provenance(
    field: str,
    value: object,
    expected_code: str,
) -> None:
    values: dict[str, object] = {
        "source_model": "model-v1",
        "feature_digest": "a" * 64,
        "source_run_id": "run-v1",
    }
    values[field] = value
    with pytest.raises(SevenRedRawTop10Violation) as error:
        ScoredSevenRedCandidate.build(
            candidate=SevenRedCandidate.from_numbers((1, 2, 3, 4, 5, 6, 7)),
            raw_score=0.4,
            normalized_score=0.6,
            source_model=values["source_model"],
            feature_digest=values["feature_digest"],
            source_run_id=values["source_run_id"],
        )
    assert error.value.code == expected_code


def test_direct_stored_representations_fail_closed() -> None:
    candidate = SevenRedCandidate.from_numbers((1, 2, 3, 4, 5, 6, 7))
    with pytest.raises(SevenRedRawTop10Violation) as score_error:
        ScoredSevenRedCandidate(
            candidate=candidate,
            raw_score=1,  # type: ignore[arg-type]
            normalized_score=0.5,
            source_model="model-v1",
            feature_digest="a" * 64,
            source_run_id="run-v1",
        )
    assert score_error.value.code == "seven_red_scored_candidate_stored_score_invalid"

    with pytest.raises(SevenRedRawTop10Violation) as list_error:
        PreScoredSevenRedCandidateList(rows=list(golden_rows()))  # type: ignore[arg-type]
    assert list_error.value.code == "seven_red_candidate_list_invalid"


def test_candidate_list_identity_is_independent_of_input_order() -> None:
    rows = golden_rows()
    first = PreScoredSevenRedCandidateList.build(rows)
    reversed_input = PreScoredSevenRedCandidateList.build(tuple(reversed(rows)))
    rotated_input = PreScoredSevenRedCandidateList.build((*rows[5:], *rows[:5]))

    assert first == reversed_input == rotated_input
    assert first.artifact_digest == reversed_input.artifact_digest == rotated_input.artifact_digest
    assert [row.candidate.lex_id for row in first.rows] == sorted(
        row.candidate.lex_id for row in rows
    )
    assert first.as_dict() == reversed_input.as_dict() == rotated_input.as_dict()
    serialized = json.dumps(first.as_dict(), sort_keys=True, separators=(",", ":"))
    assert "seed" not in serialized
    assert "created_at" not in serialized


def test_candidate_list_digest_changes_with_score_or_provenance_content() -> None:
    base = golden_rows()
    changed_score = (
        scored_row(7, 0.81),
        *base[1:],
    )
    changed_provenance = (
        scored_row(7, 0.80, source_run_id="fixture-run-v2"),
        *base[1:],
    )

    baseline = PreScoredSevenRedCandidateList.build(base)
    assert (
        PreScoredSevenRedCandidateList.build(changed_score).artifact_digest
        != baseline.artifact_digest
    )
    assert (
        PreScoredSevenRedCandidateList.build(changed_provenance).artifact_digest
        != baseline.artifact_digest
    )


def test_candidate_list_rejects_empty_duplicate_and_noncanonical_storage() -> None:
    with pytest.raises(SevenRedRawTop10Violation) as empty:
        PreScoredSevenRedCandidateList.build(())
    assert empty.value.code == "seven_red_candidate_list_invalid"

    row = scored_row(7, 0.5)
    with pytest.raises(SevenRedRawTop10Violation) as duplicate:
        PreScoredSevenRedCandidateList.build((row, row))
    assert duplicate.value.code == "seven_red_candidate_list_duplicate"

    rows = golden_rows()
    with pytest.raises(SevenRedRawTop10Violation) as order:
        PreScoredSevenRedCandidateList(rows=tuple(reversed(rows)))
    assert order.value.code == "seven_red_candidate_list_order_noncanonical"


def test_raw_top10_matches_golden_round8_and_lex_id_order_without_score_mutation() -> None:
    source = PreScoredSevenRedCandidateList.build(golden_rows())
    snapshot = RawSevenRedTop10Snapshot.build(source)
    golden = SEVEN_RED_RAW_TOP10_GOLDEN_SUITE

    selected_extra_reds = [
        entry.scored_candidate.candidate.sorted_red_numbers[-1]
        for entry in snapshot.entries
    ]
    assert selected_extra_reds == golden["expected_top10_extra_reds"]
    assert [entry.raw_rank for entry in snapshot.entries] == list(range(1, 11))
    assert [
        entry.scored_candidate.ranking_score for entry in snapshot.entries
    ] == golden["expected_top10_ranking_scores"]
    assert len(snapshot.entries) == golden["expected_size"] == RAW_TOP10_SIZE
    assert source.artifact_digest == golden["expected_candidate_list_digest"]
    assert snapshot.snapshot_digest == golden["expected_snapshot_digest"]
    assert len(
        {entry.scored_candidate.candidate.candidate_id for entry in snapshot.entries}
    ) == RAW_TOP10_SIZE
    source_by_id = {row.candidate.candidate_id: row for row in source.rows}
    for entry in snapshot.entries:
        source_row = source_by_id[entry.scored_candidate.candidate.candidate_id]
        assert entry.scored_candidate.raw_score == source_row.raw_score
        assert entry.scored_candidate.normalized_score == source_row.normalized_score


def test_raw_top10_snapshot_replays_across_input_permutations() -> None:
    rows = golden_rows()
    first = RawSevenRedTop10Snapshot.build(PreScoredSevenRedCandidateList.build(rows))
    second = RawSevenRedTop10Snapshot.build(
        PreScoredSevenRedCandidateList.build(tuple(reversed(rows)))
    )

    assert first == second
    assert first.source_candidate_list_digest == second.source_candidate_list_digest
    assert first.snapshot_digest == second.snapshot_digest
    assert first.as_dict() == second.as_dict()
    payload = json.loads(json.dumps(first.as_dict()))
    assert payload["research_only"] is True
    assert payload["deterministic"] is True
    assert payload["seed_policy"] is None
    assert payload["candidate_count"] == 10
    assert payload["source_candidate_count"] == 12
    assert payload["ranking_contract"] == RAW_TOP10_RANKING_CONTRACT
    assert "diversity" not in json.dumps(payload, sort_keys=True).lower()
    assert "penalty" not in json.dumps(payload, sort_keys=True).lower()
    assert all("red_mask" in entry and "lex_id" in entry for entry in payload["entries"])


def test_round8_ties_use_lex_id_even_when_unrounded_scores_differ() -> None:
    lower_lex = scored_row(8, 0.900000001)
    higher_lex = scored_row(9, 0.900000004)
    fillers = tuple(scored_row(extra, 0.8 - extra / 1000) for extra in range(10, 18))
    snapshot = RawSevenRedTop10Snapshot.build(
        PreScoredSevenRedCandidateList.build((higher_lex, *fillers, lower_lex))
    )

    assert lower_lex.ranking_score == higher_lex.ranking_score == 0.9
    assert snapshot.entries[0].scored_candidate == lower_lex
    assert snapshot.entries[1].scored_candidate == higher_lex
    assert lower_lex.normalized_score != higher_lex.normalized_score


def test_raw_top10_requires_at_least_ten_and_accepts_exactly_ten() -> None:
    nine = tuple(scored_row(extra, float(extra)) for extra in range(7, 16))
    with pytest.raises(SevenRedRawTop10Violation) as insufficient:
        RawSevenRedTop10Snapshot.build(PreScoredSevenRedCandidateList.build(nine))
    assert insufficient.value.code == "seven_red_raw_top10_insufficient_candidates"
    assert insufficient.value.context == {"actual": 9, "required": 10}

    ten = (*nine, scored_row(16, 16.0))
    snapshot = RawSevenRedTop10Snapshot.build(PreScoredSevenRedCandidateList.build(ten))
    assert len(snapshot.entries) == 10
    assert snapshot.source_candidate_count == 10


def test_raw_top10_rejects_tampered_entry_order_or_rank() -> None:
    source = PreScoredSevenRedCandidateList.build(golden_rows())
    valid = RawSevenRedTop10Snapshot.build(source)
    swapped = (valid.entries[1], valid.entries[0], *valid.entries[2:])
    with pytest.raises(SevenRedRawTop10Violation) as order:
        RawSevenRedTop10Snapshot(source=source, entries=swapped)
    assert order.value.code == "seven_red_raw_top10_order_mismatch"

    first = valid.entries[0]
    tampered_rank = (
        RawSevenRedTop10Entry(raw_rank=2, scored_candidate=first.scored_candidate),
        *valid.entries[1:],
    )
    with pytest.raises(SevenRedRawTop10Violation) as rank:
        RawSevenRedTop10Snapshot(source=source, entries=tampered_rank)
    assert rank.value.code == "seven_red_raw_top10_order_mismatch"
