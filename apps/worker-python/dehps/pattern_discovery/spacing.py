from __future__ import annotations

from collections import Counter
from statistics import mean
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


class SpacingPatternExtractor:
    def __init__(self, *, generator_version: str = DEFAULT_PATTERN_GENERATOR_VERSION) -> None:
        self.generator_version = generator_version

    def extract_draw_patterns(self, draws: Iterable[DrawRecord], *, max_patterns: int = 20) -> tuple[PatternCandidate, ...]:
        normalized = tuple((str(issue), normalize_red_numbers(numbers)) for issue, numbers in draws)
        if not normalized:
            return ()
        min_gap_counts: Counter[int] = Counter()
        max_gap_counts: Counter[int] = Counter()
        span_counts: Counter[int] = Counter()
        for _, numbers in normalized:
            gaps = tuple(b - a for a, b in zip(numbers, numbers[1:]))
            min_gap_counts[min(gaps)] += 1
            max_gap_counts[max(gaps)] += 1
            span_counts[numbers[-1] - numbers[0]] += 1
        candidates: list[PatternCandidate] = []
        for kind, counts in (("minimum_gap", min_gap_counts), ("maximum_gap", max_gap_counts), ("span_bucket", span_counts)):
            for value, count in counts.most_common(max(1, max_patterns // 3)):
                candidates.append(self._candidate(kind, value, count, normalized))
        return tuple(candidates[:max_patterns])

    def _candidate(self, kind: str, value: int, observed_count: int, draws: tuple[DrawRecord, ...]) -> PatternCandidate:
        family = "arithmetic_spacing" if "gap" in kind else "sum_span"
        payload = {"kind": kind, "value": value, "history": history_fingerprint(draws), "generator": self.generator_version}
        expected_count = len(draws) / max(1, len(set(range(1, 33))))
        return PatternCandidate(
            pattern_key=pattern_key("pattern-spacing", payload),
            pattern_family=family,
            pattern_type=kind,
            description=f"{kind} equals {value} in {observed_count} draw(s).",
            input_boundary={"domain": "ssq_red_ball", "red_count": 6, "red_min": 1, "red_max": 33},
            formula={"operator": kind, "value": value},
            parameters={"value": value},
            observed_support=float(observed_count),
            expected_support=float(expected_count),
            effect_size=(observed_count - expected_count) / len(draws),
            stability_score=0.5 + min(0.5, abs(observed_count / len(draws) - mean([observed_count / len(draws)]))),
            novelty_score=1.0,
            complexity_score=0.2,
            search_issue_range={"start": draws[0][0], "end": draws[-1][0]},
            history_fingerprint=history_fingerprint(draws),
            legal_universe_fingerprint=LEGAL_UNIVERSE_FINGERPRINT,
            null_definition={"primary": "legal_universe", "matched": {"legal_universe": expected_count / len(draws)}},
            failure_condition={"frozen": "family_adjusted_p_value >= 0.05 or direction != positive"},
            leakage_risks=("post_hoc_bucket_selection",),
            source_artifacts=tuple(issue for issue, numbers in draws if self._matches(kind, value, numbers)),
            multiplicity_family=kind,
            generator_version=self.generator_version,
            metadata={"sample_count": len(draws)},
        )

    @staticmethod
    def _matches(kind: str, value: int, numbers: tuple[int, ...]) -> bool:
        gaps = tuple(b - a for a, b in zip(numbers, numbers[1:]))
        if kind == "minimum_gap":
            return min(gaps) == value
        if kind == "maximum_gap":
            return max(gaps) == value
        return numbers[-1] - numbers[0] == value
