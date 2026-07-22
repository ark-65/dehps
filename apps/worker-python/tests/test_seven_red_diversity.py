from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from itertools import combinations
from math import comb

import pytest

from dehps.seven_red import (
    RAW_TOP10_SIZE,
    RESEARCH_ONLY,
    SEVEN_RED_DIVERSITY_AUDIT_CONTRACT_V1,
    SEVEN_RED_DIVERSITY_AUDIT_VERSION,
    SEVEN_RED_DIVERSITY_METRIC_CONTRACT,
    SEVEN_RED_DOMAIN_CONTRACT_V1,
    SEVEN_RED_RAW_TOP10_CONTRACT_V1,
    PreScoredSevenRedCandidateList,
    RawSevenRedTop10Snapshot,
    ScoredSevenRedCandidate,
    SevenRedCandidate,
    SevenRedDiversityAuditSnapshot,
    SevenRedDiversityAuditViolation,
    SevenRedGeometryMetrics,
)
from dehps.seven_red.diversity import (
    SEVEN_RED_DIVERSITY_GOLDEN_SUITE,
    SEVEN_RED_DIVERSITY_NORMATIVE_DEFINITION,
)
from dehps.seven_red.raw_top10 import SEVEN_RED_RAW_TOP10_GOLDEN_SUITE


def scored_candidate(
    numbers: tuple[int, ...],
    normalized_score: float,
    *,
    source_run_id: str = "diversity-fixture-run-v1",
) -> ScoredSevenRedCandidate:
    candidate = SevenRedCandidate.from_numbers(numbers)
    return ScoredSevenRedCandidate.build(
        candidate=candidate,
        raw_score=normalized_score * 10.0,
        normalized_score=normalized_score,
        source_model="diversity-fixture-model-v1",
        feature_digest=f"{candidate.lex_id + 1:064x}",
        source_run_id=source_run_id,
    )


def golden_rows() -> tuple[ScoredSevenRedCandidate, ...]:
    return tuple(
        scored_candidate(
            (1, 2, 3, 4, 5, 6, int(case["extra_red"])),
            float(case["normalized_score"]),
        )
        for case in SEVEN_RED_RAW_TOP10_GOLDEN_SUITE["source_candidates"]
    )


def golden_sources() -> tuple[
    PreScoredSevenRedCandidateList,
    RawSevenRedTop10Snapshot,
]:
    pool = PreScoredSevenRedCandidateList.build(golden_rows())
    return pool, RawSevenRedTop10Snapshot.build(pool)


def no_collision_candidates() -> tuple[SevenRedCandidate, ...]:
    return tuple(
        SevenRedCandidate.from_numbers((1, 2, 3, 4, 5, extra, extra + 1))
        for extra in range(6, 26, 2)
    )


def brute_overlap_histogram(
    candidates: tuple[SevenRedCandidate, ...],
) -> tuple[int, ...]:
    histogram = [0] * 7
    for left, right in combinations(candidates, 2):
        overlap = (left.red_mask & right.red_mask).bit_count()
        histogram[overlap] += 1
    return tuple(histogram)


def test_contract_is_research_only_and_binds_both_predecessors_exactly() -> None:
    dependencies = SEVEN_RED_DIVERSITY_NORMATIVE_DEFINITION["dependencies"]

    assert RESEARCH_ONLY is True
    assert SEVEN_RED_DIVERSITY_AUDIT_VERSION.endswith("snapshot.v1")
    assert SEVEN_RED_DIVERSITY_METRIC_CONTRACT.endswith("collision.v1")
    assert SEVEN_RED_DIVERSITY_AUDIT_CONTRACT_V1.family == (
        "seven-red-diversity-audit"
    )
    assert SEVEN_RED_DIVERSITY_AUDIT_CONTRACT_V1.semantic_version == "1.0.0"
    assert dependencies["seven_red_domain"] == (
        SEVEN_RED_DOMAIN_CONTRACT_V1.normative_identity()
    )
    assert dependencies["seven_red_raw_top10"] == (
        SEVEN_RED_RAW_TOP10_CONTRACT_V1.normative_identity()
    )
    assert SEVEN_RED_DIVERSITY_AUDIT_CONTRACT_V1.normative_digest == (
        "9cdc0b3293bfb143412d3715a6b8374fd778f3bc9d007ed2b690d7cffab1e53a"
    )


def test_golden_pool_and_raw_top10_have_exact_multi_collision_geometry() -> None:
    pool, raw = golden_sources()
    audit = SevenRedDiversityAuditSnapshot.build(pool, raw)
    golden = SEVEN_RED_DIVERSITY_GOLDEN_SUITE

    for metrics, expected in (
        (audit.pool_metrics, golden["pool"]),
        (audit.raw_top10_metrics, golden["raw_top10"]),
    ):
        assert metrics.candidate_count == expected["candidate_count"]
        assert metrics.pair_count == expected["pair_count"]
        assert list(metrics.overlap_histogram) == (
            expected["overlap_histogram_0_through_6"]
        )
        assert list(metrics.shared_core_pair_counts) == (
            expected["shared_core_pair_counts_1_through_6"]
        )
        assert metrics.expansion_geometry.unique_expansion_count == (
            expected["unique_expansion_count"]
        )
        assert metrics.expansion_geometry.duplicate_expansion_slot_count == (
            expected["duplicate_expansion_slot_count"]
        )

    assert audit.pool_metrics.pair_core_coverage.unique_count == 87
    assert audit.pool_metrics.triple_core_coverage.unique_count == 200
    assert audit.raw_top10_metrics.pair_core_coverage.unique_count == 75
    assert audit.raw_top10_metrics.triple_core_coverage.unique_count == 170
    assert audit.pool_metrics.maximum_number_occurrence == 12
    assert audit.pool_metrics.maximum_numbers == (1, 2, 3, 4, 5, 6)
    assert audit.raw_top10_metrics.maximum_number_occurrence == RAW_TOP10_SIZE
    assert len(audit.pool_metrics.expansion_geometry.collisions) == 1
    assert audit.pool_metrics.expansion_geometry.collisions[0].multiplicity == 12
    assert len(audit.raw_top10_metrics.expansion_geometry.collisions) == 1
    assert audit.raw_top10_metrics.expansion_geometry.collisions[0].multiplicity == 10


def test_no_shared_six_core_produces_all_seventy_unique_expansions() -> None:
    candidates = no_collision_candidates()
    metrics = SevenRedGeometryMetrics.build(candidates)

    assert len(candidates) == RAW_TOP10_SIZE
    assert metrics.overlap_histogram == (0, 0, 0, 0, 0, 45, 0)
    assert metrics.overlap_histogram == brute_overlap_histogram(candidates)
    assert metrics.expansion_geometry.total_expansion_slots == 70
    assert metrics.expansion_geometry.unique_expansion_count == 70
    assert metrics.expansion_geometry.duplicate_expansion_slot_count == 0
    assert metrics.expansion_geometry.maximum_multiplicity == 1
    assert metrics.expansion_geometry.collisions == ()
    assert metrics.expansion_geometry.multiplicity_histogram[1] == 70


def test_one_shared_six_core_produces_exactly_one_duplicate_slot() -> None:
    candidates = (
        SevenRedCandidate.from_numbers((1, 2, 3, 4, 5, 6, 7)),
        SevenRedCandidate.from_numbers((1, 2, 3, 4, 5, 6, 8)),
    )
    metrics = SevenRedGeometryMetrics.build(candidates)
    expansion = metrics.expansion_geometry

    assert metrics.overlap_histogram == (0, 0, 0, 0, 0, 0, 1)
    assert expansion.total_expansion_slots == 14
    assert expansion.unique_expansion_count == 13
    assert expansion.duplicate_expansion_slot_count == 1
    assert expansion.multiplicity_histogram[1] == 12
    assert expansion.multiplicity_histogram[2] == 1
    assert len(expansion.collisions) == 1
    assert expansion.collisions[0].six_red.sorted_red_numbers == (1, 2, 3, 4, 5, 6)
    assert expansion.collisions[0].multiplicity == 2


def test_subset_incidence_inversion_matches_brute_force_on_mixed_geometry() -> None:
    candidates = (
        SevenRedCandidate.from_numbers((1, 2, 3, 4, 5, 6, 7)),
        SevenRedCandidate.from_numbers((1, 2, 3, 4, 5, 6, 8)),
        SevenRedCandidate.from_numbers((1, 2, 3, 4, 5, 9, 10)),
        SevenRedCandidate.from_numbers((1, 2, 3, 11, 12, 13, 14)),
        SevenRedCandidate.from_numbers((15, 16, 17, 18, 19, 20, 21)),
    )
    metrics = SevenRedGeometryMetrics.build(tuple(reversed(candidates)))

    assert metrics.overlap_histogram == brute_overlap_histogram(candidates)
    assert sum(metrics.overlap_histogram) == comb(len(candidates), 2)
    for core_size in range(1, 7):
        assert metrics.shared_core_pair_counts[core_size - 1] == sum(
            comb(overlap, core_size) * metrics.overlap_histogram[overlap]
            for overlap in range(core_size, 7)
        )
    assert metrics.overlap_histogram[6] == sum(
        comb(collision.multiplicity, 2)
        for collision in metrics.expansion_geometry.collisions
    )


def test_geometry_identity_is_independent_of_candidate_input_order() -> None:
    candidates = no_collision_candidates()
    first = SevenRedGeometryMetrics.build(candidates)
    second = SevenRedGeometryMetrics.build(tuple(reversed(candidates)))
    rotated = SevenRedGeometryMetrics.build((*candidates[3:], *candidates[:3]))

    assert first == second == rotated
    assert first.identity_payload() == second.identity_payload()
    assert first.candidate_set_digest == second.candidate_set_digest


def test_audit_replays_and_preserves_the_frozen_raw_entries_unchanged() -> None:
    rows = golden_rows()
    pool = PreScoredSevenRedCandidateList.build(rows)
    raw = RawSevenRedTop10Snapshot.build(pool)
    first = SevenRedDiversityAuditSnapshot.build(pool, raw)
    permuted_pool = PreScoredSevenRedCandidateList.build(tuple(reversed(rows)))
    permuted_raw = RawSevenRedTop10Snapshot.build(permuted_pool)
    second = SevenRedDiversityAuditSnapshot.build(permuted_pool, permuted_raw)

    assert first == second
    assert first.snapshot_digest == second.snapshot_digest
    assert first.as_dict() == second.as_dict()
    assert first.as_dict()["source_raw_top10_entries"] == [
        entry.as_dict() for entry in raw.entries
    ]
    for before, after in zip(
        raw.entries,
        first.as_dict()["source_raw_top10_entries"],
        strict=True,
    ):
        assert after["raw_rank"] == before.raw_rank
        assert after["candidate_id"] == before.scored_candidate.candidate.candidate_id
        assert after["raw_score"] == before.scored_candidate.raw_score
        assert after["normalized_score"] == before.scored_candidate.normalized_score
        assert after["row_digest"] == before.scored_candidate.row_digest


def test_audit_payload_is_outcome_blind_seedless_and_observational() -> None:
    pool, raw = golden_sources()
    audit = SevenRedDiversityAuditSnapshot.build(pool, raw)
    payload = json.loads(json.dumps(audit.as_dict()))
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["research_only"] is True
    assert payload["deterministic"] is True
    assert payload["seed_policy"] is None
    assert payload["outcome_inputs"] is None
    assert payload["interpretation"] == "observational_only"
    assert payload["threshold_policy"] is None
    assert "created_at" not in serialized
    assert "actual_red" not in serialized
    assert "target_draw" not in serialized
    assert "settlement" not in serialized
    assert "selector" not in serialized


def test_audit_rejects_mismatched_raw_source_and_recomputed_metric_tampering() -> None:
    pool, raw = golden_sources()
    changed_rows = tuple(
        scored_candidate(
            row.candidate.sorted_red_numbers,
            row.normalized_score,
            source_run_id="diversity-fixture-run-v2",
        )
        for row in pool.rows
    )
    changed_pool = PreScoredSevenRedCandidateList.build(changed_rows)
    changed_raw = RawSevenRedTop10Snapshot.build(changed_pool)
    valid = SevenRedDiversityAuditSnapshot.build(pool, raw)

    with pytest.raises(SevenRedDiversityAuditViolation) as source_error:
        SevenRedDiversityAuditSnapshot(
            source_candidate_pool=pool,
            source_raw_top10=changed_raw,
            pool_metrics=valid.pool_metrics,
            raw_top10_metrics=valid.raw_top10_metrics,
        )
    assert source_error.value.code == "seven_red_diversity_source_binding_mismatch"

    with pytest.raises(SevenRedDiversityAuditViolation) as pool_metrics_error:
        SevenRedDiversityAuditSnapshot(
            source_candidate_pool=pool,
            source_raw_top10=raw,
            pool_metrics=valid.raw_top10_metrics,
            raw_top10_metrics=valid.raw_top10_metrics,
        )
    assert pool_metrics_error.value.code == "seven_red_diversity_pool_metrics_mismatch"


def test_direct_noncanonical_or_inconsistent_metric_storage_fails_closed() -> None:
    metrics = SevenRedGeometryMetrics.build(no_collision_candidates())

    with pytest.raises(SevenRedDiversityAuditViolation) as pair_count:
        replace(metrics, pair_count=44)
    assert pair_count.value.code == "seven_red_diversity_pair_count_mismatch"

    malformed_histogram = list(metrics.overlap_histogram)
    malformed_histogram[5] -= 1
    malformed_histogram[4] += 1
    with pytest.raises(SevenRedDiversityAuditViolation) as incidence:
        replace(metrics, overlap_histogram=tuple(malformed_histogram))
    assert incidence.value.code == "seven_red_diversity_incidence_identity_failed"

    with pytest.raises(FrozenInstanceError):
        metrics.candidate_count = 11  # type: ignore[misc]


def test_golden_digests_are_frozen() -> None:
    pool, raw = golden_sources()
    audit = SevenRedDiversityAuditSnapshot.build(pool, raw)
    golden = SEVEN_RED_DIVERSITY_GOLDEN_SUITE

    assert audit.pool_metrics.candidate_set_digest == (
        golden["expected_pool_candidate_set_digest"]
    )
    assert audit.raw_top10_metrics.candidate_set_digest == (
        golden["expected_raw_candidate_set_digest"]
    )
    assert audit.snapshot_digest == golden["expected_audit_digest"]
