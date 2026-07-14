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
PRIMES = frozenset({2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31})
SQUARES = frozenset({1, 4, 9, 16, 25})
FIBONACCI = frozenset({1, 2, 3, 5, 8, 13, 21})


class StructuralPatternExtractor:
    def __init__(self, *, generator_version: str = DEFAULT_PATTERN_GENERATOR_VERSION) -> None:
        self.generator_version = generator_version

    def extract_draw_patterns(self, draws: Iterable[DrawRecord], *, max_patterns: int = 30) -> tuple[PatternCandidate, ...]:
        normalized = tuple((str(issue), normalize_red_numbers(numbers)) for issue, numbers in draws)
        counters: dict[str, Counter[int | tuple[int, int, int]]] = {
            "prime_count": Counter(),
            "square_number_count": Counter(),
            "fibonacci_number_count": Counter(),
            "odd_even_ratio": Counter(),
            "low_mid_high_zone": Counter(),
            "mirror_pair_count": Counter(),
            "decade_coverage": Counter(),
        }
        for _, numbers in normalized:
            counters["prime_count"][sum(1 for n in numbers if n in PRIMES)] += 1
            counters["square_number_count"][sum(1 for n in numbers if n in SQUARES)] += 1
            counters["fibonacci_number_count"][sum(1 for n in numbers if n in FIBONACCI)] += 1
            counters["odd_even_ratio"][sum(1 for n in numbers if n % 2)] += 1
            counters["low_mid_high_zone"][
                (
                    sum(1 for n in numbers if n <= 11),
                    sum(1 for n in numbers if 12 <= n <= 22),
                    sum(1 for n in numbers if n >= 23),
                )
            ] += 1
            counters["mirror_pair_count"][sum(1 for n in numbers if 34 - n in numbers and n < 17)] += 1
            counters["decade_coverage"][len({(n - 1) // 10 for n in numbers})] += 1
        candidates: list[PatternCandidate] = []
        for kind, counter in counters.items():
            for value, count in counter.most_common(max(1, max_patterns // len(counters))):
                candidates.append(self._candidate(kind, value, count, normalized))
        return tuple(candidates[:max_patterns])

    def _candidate(self, kind: str, value: int | tuple[int, int, int], count: int, draws: tuple[DrawRecord, ...]) -> PatternCandidate:
        family = "prime_number_theory" if kind in {"prime_count", "square_number_count", "fibonacci_number_count"} else "structural"
        if kind == "odd_even_ratio":
            family = "odd_even"
        if kind == "low_mid_high_zone":
            family = "zone"
        expected = len(draws) / 7
        payload = {"kind": kind, "value": value, "history": history_fingerprint(draws), "generator": self.generator_version}
        return PatternCandidate(
            pattern_key=pattern_key("pattern-struct", payload),
            pattern_family=family,
            pattern_type=kind,
            description=f"{kind} equals {value}.",
            input_boundary={"domain": "ssq_red_ball", "red_count": 6},
            formula={"operator": kind, "value": value},
            parameters={"value": value},
            observed_support=float(count),
            expected_support=float(expected),
            effect_size=(count - expected) / max(1, len(draws)),
            stability_score=0.5,
            novelty_score=1.0,
            complexity_score=0.25,
            search_issue_range={"start": draws[0][0], "end": draws[-1][0]} if draws else {},
            history_fingerprint=history_fingerprint(draws),
            legal_universe_fingerprint=LEGAL_UNIVERSE_FINGERPRINT,
            null_definition={"primary": "legal_universe", "matched": {"legal_universe": expected / max(1, len(draws))}},
            failure_condition={"frozen": "family_adjusted_p_value >= 0.05"},
            leakage_risks=("post_hoc_bucket_selection",),
            source_artifacts=(),
            multiplicity_family=kind,
            generator_version=self.generator_version,
            metadata={"sample_count": len(draws)},
        )
