from __future__ import annotations

from collections import Counter
from typing import Iterable

from dehps.domain.combination import normalize_red_numbers
from dehps.pattern_discovery.models import (
    DEFAULT_PATTERN_GENERATOR_VERSION,
    LEGAL_UNIVERSE_FINGERPRINT,
    PatternCandidate,
    history_fingerprint,
    pattern_key,
)


DrawRecord = tuple[str, tuple[int, ...]]


class TemporalPatternExtractor:
    def __init__(self, *, generator_version: str = DEFAULT_PATTERN_GENERATOR_VERSION) -> None:
        self.generator_version = generator_version

    def extract_draw_patterns(self, draws: Iterable[DrawRecord], *, max_patterns: int = 20) -> tuple[PatternCandidate, ...]:
        normalized = tuple((str(issue), normalize_red_numbers(numbers)) for issue, numbers in draws)
        if not normalized:
            return ()
        last_seen: dict[int, int] = {}
        omission_buckets: Counter[str] = Counter()
        for index, (_, numbers) in enumerate(normalized):
            for n in range(1, 34):
                age = index - last_seen.get(n, -1)
                if n in numbers:
                    bucket = "fresh" if age <= 3 else "stale" if age >= 15 else "middle"
                    omission_buckets[bucket] += 1
                    last_seen[n] = index
        return tuple(self._candidate(bucket, count, normalized) for bucket, count in omission_buckets.most_common(max_patterns))

    def _candidate(self, bucket: str, count: int, draws: tuple[DrawRecord, ...]) -> PatternCandidate:
        expected = len(draws) * 6 / 3
        payload = {"bucket": bucket, "history": history_fingerprint(draws), "generator": self.generator_version}
        return PatternCandidate(
            pattern_key=pattern_key("pattern-temporal", payload),
            pattern_family="temporal_omission",
            pattern_type="omission_age_bucket",
            description=f"Omission age bucket {bucket} appears {count} times.",
            input_boundary={"domain": "ssq_red_ball", "uses_history_order": True},
            formula={"operator": "omission_age_bucket", "bucket": bucket},
            parameters={"bucket": bucket},
            observed_support=float(count),
            expected_support=float(expected),
            effect_size=(count - expected) / max(1, len(draws) * 6),
            stability_score=0.5,
            novelty_score=1.0,
            complexity_score=0.35,
            search_issue_range={"start": draws[0][0], "end": draws[-1][0]},
            history_fingerprint=history_fingerprint(draws),
            legal_universe_fingerprint=LEGAL_UNIVERSE_FINGERPRINT,
            null_definition={"primary": "random_history_permutation", "matched": {"random_history_permutation": expected / max(1, len(draws) * 6)}},
            failure_condition={"frozen": "permutation_adjusted_p_value >= 0.05"},
            leakage_risks=("future_issue_leakage", "order_dependent_split_leakage"),
            source_artifacts=(),
            multiplicity_family="temporal_omission",
            generator_version=self.generator_version,
            metadata={"sample_count": len(draws)},
        )
