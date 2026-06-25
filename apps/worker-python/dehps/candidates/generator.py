from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from heapq import nsmallest
from typing import Iterable

from dehps.domain.combination import iter_ssq_red_combinations, normalize_red_numbers
from dehps.scoring.strategy import StrategyConfig, keep_by_baseline, score_numbers


@dataclass(frozen=True)
class Candidate:
    rank: int
    numbers: tuple[int, ...]
    score: float
    anomaly_penalty: float
    structure_naturalness_score: float
    pattern_complexity_score: float
    tie_breaker: str

    @property
    def numbers_text(self) -> str:
        return " ".join(f"{number:02d}" for number in self.numbers)


def stable_tie_breaker(numbers: tuple[int, ...], seed: str) -> str:
    payload = f"{seed}:{','.join(map(str, numbers))}"
    return sha256(payload.encode("utf-8")).hexdigest()


def generate_candidates(
    limit: int,
    seed: str,
    history: list[tuple[str, tuple[int, ...]]] | None = None,
    config: StrategyConfig | None = None,
    universe: Iterable[tuple[int, ...]] | None = None,
) -> list[Candidate]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    cfg = config or StrategyConfig()
    historical_numbers = {normalize_red_numbers(numbers) for _, numbers in history or []}
    seen_numbers: set[tuple[int, ...]] = set()
    ranked: list[tuple[float, float, str, tuple[int, ...], dict[str, float]]] = []

    for raw_numbers in universe or iter_ssq_red_combinations():
        numbers = normalize_red_numbers(raw_numbers)
        if numbers in seen_numbers:
            continue
        seen_numbers.add(numbers)
        if numbers in historical_numbers:
            continue
        if not keep_by_baseline(numbers, cfg):
            continue
        scored = score_numbers(numbers)
        ranked.append(
            (
                -scored["score"],
                scored["anomaly_penalty"],
                stable_tie_breaker(numbers, seed),
                numbers,
                scored,
            ),
        )

    candidates: list[Candidate] = []
    for rank, (_, _, tie_breaker, numbers, scored) in enumerate(nsmallest(limit, ranked), start=1):
        candidates.append(
            Candidate(
                rank=rank,
                numbers=numbers,
                score=scored["score"],
                anomaly_penalty=scored["anomaly_penalty"],
                structure_naturalness_score=scored["structure_naturalness_score"],
                pattern_complexity_score=scored["pattern_complexity_score"],
                tie_breaker=tie_breaker[:12],
            ),
        )
    return candidates


def render_candidate_report(
    *,
    candidate_key: str,
    seed: str,
    latest_issue: str | None,
    next_issue_hint: str | None,
    candidates: list[Candidate],
    null_summary: dict[str, float | int],
    leakage_checks: list[dict[str, str]],
) -> str:
    rows = "\n".join(
        (
            f"| {candidate.rank} | `{candidate.numbers_text}` | {candidate.score:.6f} | "
            f"{candidate.anomaly_penalty:.4f} | {candidate.tie_breaker} |"
        )
        for candidate in candidates
    )
    checks = "\n".join(
        f"- {check['name']}: {check['status']} - {check['detail']}" for check in leakage_checks
    )
    return f"""# DEHPS Candidate Report

- Candidate key: `{candidate_key}`
- Latest known issue: {latest_issue or "N/A"}
- Next issue hint: {next_issue_hint or "N/A"}
- Frozen seed: `{seed}`

## Protocol

- Generate legal 双色球 red-ball combinations only.
- Exclude exact historical red-ball combinations already present in local history.
- Keep combinations accepted by `baseline_v1`.
- Rank by DEHPS score descending, anomaly penalty ascending, and deterministic seed hash.
- Do not use future draw outcomes, blue balls, or post-result threshold tuning.

## Candidates

| Rank | Red numbers | Score | Anomaly penalty | Tie hash |
| --- | --- | --- | --- | --- |
{rows}

## Null Model

- random_sets: {null_summary["random_sets"]}
- candidate_count: {null_summary["candidate_count"]}
- mean_score: {null_summary["mean_score"]}
- max_score: {null_summary["max_score"]}
- min_score: {null_summary["min_score"]}

## Leakage Checks

{checks}

## Risk Note

Every legal red-ball combination has the same mathematical probability before the draw. These candidates are transparent structural hypotheses for later verification, not guaranteed predictions or betting advice.
"""
