from __future__ import annotations

from collections import Counter
from itertools import combinations
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


class CooccurrencePatternExtractor:
    def __init__(self, *, generator_version: str = DEFAULT_PATTERN_GENERATOR_VERSION) -> None:
        self.generator_version = generator_version

    def extract_draw_patterns(self, draws: Iterable[DrawRecord], *, max_patterns: int = 20) -> tuple[PatternCandidate, ...]:
        normalized = tuple((str(issue), normalize_red_numbers(numbers)) for issue, numbers in draws)
        pair_counts: Counter[tuple[int, int]] = Counter()
        triple_counts: Counter[tuple[int, int, int]] = Counter()
        for _, numbers in normalized:
            pair_counts.update(combinations(numbers, 2))
            triple_counts.update(combinations(numbers, 3))
        candidates: list[PatternCandidate] = []
        for pair, count in pair_counts.most_common(max(1, max_patterns // 2)):
            candidates.append(self._candidate("pair_cooccurrence_lift", pair, count, normalized, expected_per_draw=15 / 528))
        for triple, count in triple_counts.most_common(max(1, max_patterns // 2)):
            candidates.append(self._candidate("triple_cooccurrence_lift", triple, count, normalized, expected_per_draw=20 / 5456))
        return tuple(candidates[:max_patterns])

    def _candidate(self, kind: str, values: tuple[int, ...], count: int, draws: tuple[DrawRecord, ...], *, expected_per_draw: float) -> PatternCandidate:
        expected = len(draws) * expected_per_draw
        payload = {"kind": kind, "values": values, "history": history_fingerprint(draws), "generator": self.generator_version}
        return PatternCandidate(
            pattern_key=pattern_key("pattern-cooccur", payload),
            pattern_family="cooccurrence_graph",
            pattern_type=kind,
            description=f"{kind} for {values} appears {count} times.",
            input_boundary={"domain": "ssq_red_ball", "red_count": 6},
            formula={"operator": "contains_all", "values": values},
            parameters={"values": values},
            observed_support=float(count),
            expected_support=float(expected),
            effect_size=(count - expected) / max(1, len(draws)),
            stability_score=0.5,
            novelty_score=1.0,
            complexity_score=0.4,
            search_issue_range={"start": draws[0][0], "end": draws[-1][0]} if draws else {},
            history_fingerprint=history_fingerprint(draws),
            legal_universe_fingerprint=LEGAL_UNIVERSE_FINGERPRINT,
            null_definition={"primary": "random_history_permutation", "matched": {"legal_universe": expected_per_draw}},
            failure_condition={"frozen": "family_adjusted_p_value >= 0.05"},
            leakage_risks=("multiplicity_under_counting", "post_hoc_pair_selection"),
            source_artifacts=tuple(issue for issue, numbers in draws if set(values).issubset(numbers)),
            multiplicity_family=kind,
            generator_version=self.generator_version,
            metadata={"sample_count": len(draws)},
        )
