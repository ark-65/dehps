from __future__ import annotations

import dehps.candidates.null_model as null_model
from dehps.candidates.generator import Candidate, generate_candidates, stable_tie_breaker
from dehps.candidates.leakage import audit_candidate_protocol
from dehps.candidates.null_model import generate_null_candidates
from dehps.scoring.strategy import StrategyConfig, score_numbers


def test_generate_candidates_is_seeded_and_excludes_history():
    history = [("2026001", (1, 2, 3, 4, 5, 6))]
    config = StrategyConfig(min_score=0.4, max_anomaly_penalty=0.8)
    universe = [
        (1, 2, 3, 4, 5, 6),
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
        (3, 10, 15, 20, 25, 33),
        (4, 11, 16, 21, 26, 31),
        (5, 12, 17, 22, 27, 32),
        (6, 13, 18, 23, 28, 33),
    ]

    first = generate_candidates(limit=5, seed="2026067", history=history, config=config, universe=universe)
    second = generate_candidates(limit=5, seed="2026067", history=history, config=config, universe=universe)

    assert first == second
    assert len(first) == 5
    assert len({candidate.numbers for candidate in first}) == 5
    assert all(candidate.numbers != (1, 2, 3, 4, 5, 6) for candidate in first)
    assert all(candidate.score >= 0.4 for candidate in first)


def test_generate_candidates_canonicalizes_red_sets_for_history_and_duplicates():
    config = StrategyConfig(min_score=0.0, max_anomaly_penalty=1.0)
    history = [("2026001", (6, 5, 4, 3, 2, 1))]
    universe = [
        (1, 2, 3, 4, 5, 6),
        (31, 23, 18, 13, 8, 1),
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
    ]

    candidates = generate_candidates(limit=5, seed="2026067", history=history, config=config, universe=universe)

    candidate_numbers = [candidate.numbers for candidate in candidates]
    assert (1, 2, 3, 4, 5, 6) not in candidate_numbers
    assert set(candidate_numbers) == {
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
    }


def test_stable_tie_breaker_changes_with_seed():
    numbers = (1, 8, 13, 18, 23, 31)

    assert stable_tie_breaker(numbers, "a") != stable_tie_breaker(numbers, "b")
    assert stable_tie_breaker(numbers, "a") == stable_tie_breaker(numbers, "a")


def test_null_candidates_are_reproducible():
    first = generate_null_candidates(candidate_count=3, random_sets=4, seed="null-seed")
    second = generate_null_candidates(candidate_count=3, random_sets=4, seed="null-seed")

    assert first == second
    assert first.random_sets == 4
    assert first.candidate_count == 3
    assert 0 <= first.min_score <= first.mean_score <= first.max_score <= 1


def test_null_candidates_canonicalize_history_before_exclusion(monkeypatch):
    class FixedRandom:
        def __init__(self, _seed: str):
            self.samples = [
                [6, 5, 4, 3, 2, 1],
                [1, 8, 13, 18, 23, 31],
            ]

        def sample(self, _population: range, _count: int) -> list[int]:
            return self.samples.pop(0)

    monkeypatch.setattr(null_model, "Random", FixedRandom)

    summary = generate_null_candidates(
        candidate_count=1,
        random_sets=1,
        seed="null-seed",
        history=[("2026001", (6, 5, 4, 3, 2, 1))],
    )

    accepted_score = round(score_numbers((1, 8, 13, 18, 23, 31))["score"], 6)
    assert summary.mean_score == accepted_score
    assert summary.min_score == accepted_score
    assert summary.max_score == accepted_score


def test_leakage_audit_flags_history_overlap_and_duplicates():
    candidate = Candidate(
        rank=1,
        numbers=(1, 2, 3, 4, 5, 6),
        score=0.5,
        anomaly_penalty=0.1,
        structure_naturalness_score=0.5,
        pattern_complexity_score=0.5,
        tie_breaker="abc",
    )

    checks = audit_candidate_protocol(
        candidates=[candidate, candidate],
        history=[("2026067", candidate.numbers)],
        latest_issue="2026067",
        seed="2026068",
    )
    statuses = {check.name: check.status for check in checks}

    assert statuses["history_overlap"] == "fail"
    assert statuses["duplicate_candidates"] == "fail"
    assert statuses["future_outcome"] == "warn"


def test_leakage_audit_warns_on_malformed_latest_issue():
    candidate = Candidate(
        rank=1,
        numbers=(1, 2, 3, 4, 5, 6),
        score=0.5,
        anomaly_penalty=0.1,
        structure_naturalness_score=0.5,
        pattern_complexity_score=0.5,
        tie_breaker="abc",
    )

    checks = audit_candidate_protocol(
        candidates=[candidate],
        history=[],
        latest_issue="bad-issue",
        seed="2026068",
    )
    statuses = {check.name: check.status for check in checks}

    assert statuses["future_outcome"] == "warn"


def test_leakage_audit_warns_on_stale_seed_issue():
    candidate = Candidate(
        rank=1,
        numbers=(1, 2, 3, 4, 5, 6),
        score=0.5,
        anomaly_penalty=0.1,
        structure_naturalness_score=0.5,
        pattern_complexity_score=0.5,
        tie_breaker="abc",
    )

    checks = audit_candidate_protocol(
        candidates=[candidate],
        history=[],
        latest_issue="2026068",
        seed="2026067",
    )
    statuses = {check.name: check.status for check in checks}

    assert statuses["future_outcome"] == "warn"


def test_leakage_audit_canonicalizes_red_sets_before_comparison():
    first = Candidate(
        rank=1,
        numbers=(1, 2, 3, 4, 5, 6),
        score=0.5,
        anomaly_penalty=0.1,
        structure_naturalness_score=0.5,
        pattern_complexity_score=0.5,
        tie_breaker="abc",
    )
    second = Candidate(
        rank=2,
        numbers=(6, 5, 4, 3, 2, 1),
        score=0.5,
        anomaly_penalty=0.1,
        structure_naturalness_score=0.5,
        pattern_complexity_score=0.5,
        tie_breaker="def",
    )

    checks = audit_candidate_protocol(
        candidates=[first, second],
        history=[("2026067", (6, 5, 4, 3, 2, 1))],
        latest_issue="2026067",
        seed="2026067",
    )
    statuses = {check.name: check.status for check in checks}

    assert statuses["history_overlap"] == "fail"
    assert statuses["duplicate_candidates"] == "fail"
