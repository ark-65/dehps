from __future__ import annotations

from dataclasses import dataclass
from random import Random

from dehps.domain.combination import normalize_red_numbers
from dehps.scoring.strategy import score_numbers


@dataclass(frozen=True)
class NullCandidateSummary:
    random_sets: int
    candidate_count: int
    mean_score: float
    min_score: float
    max_score: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "random_sets": self.random_sets,
            "candidate_count": self.candidate_count,
            "mean_score": self.mean_score,
            "min_score": self.min_score,
            "max_score": self.max_score,
        }


def generate_null_candidates(
    *,
    candidate_count: int,
    random_sets: int,
    seed: str,
    history: list[tuple[str, tuple[int, ...]]] | None = None,
) -> NullCandidateSummary:
    if candidate_count < 1:
        raise ValueError("candidate_count must be at least 1")
    if random_sets < 1:
        raise ValueError("random_sets must be at least 1")

    rng = Random(seed)
    historical_numbers = {normalize_red_numbers(numbers) for _, numbers in history or []}
    scores: list[float] = []
    for _ in range(random_sets):
        generated: set[tuple[int, ...]] = set()
        while len(generated) < candidate_count:
            numbers = normalize_red_numbers(rng.sample(range(1, 34), 6))
            if numbers in historical_numbers:
                continue
            generated.add(numbers)
        scores.extend(score_numbers(numbers)["score"] for numbers in generated)

    return NullCandidateSummary(
        random_sets=random_sets,
        candidate_count=candidate_count,
        mean_score=round(sum(scores) / len(scores), 6),
        min_score=round(min(scores), 6),
        max_score=round(max(scores), 6),
    )
