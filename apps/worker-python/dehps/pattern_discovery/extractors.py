from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from dehps.domain.combination import normalize_red_numbers
from dehps.pattern_discovery.arithmetic import ArithmeticProgressionExtractor
from dehps.pattern_discovery.cooccurrence import CooccurrencePatternExtractor
from dehps.pattern_discovery.models import PatternCandidate, PatternSearchBudget
from dehps.pattern_discovery.modular import ModularPatternExtractor
from dehps.pattern_discovery.residual import ResidualPatternExtractor
from dehps.pattern_discovery.spacing import SpacingPatternExtractor
from dehps.pattern_discovery.structural import StructuralPatternExtractor
from dehps.pattern_discovery.temporal import TemporalPatternExtractor


DrawRecord = tuple[str, tuple[int, ...]]


@dataclass(frozen=True)
class PatternExtractionResult:
    patterns: tuple[PatternCandidate, ...]
    family_counts: dict[str, int]
    stopped_by_budget: bool


class PatternExtractorSuite:
    def __init__(self) -> None:
        self.extractors = (
            ArithmeticProgressionExtractor(),
            SpacingPatternExtractor(),
            ModularPatternExtractor(),
            StructuralPatternExtractor(),
            TemporalPatternExtractor(),
            CooccurrencePatternExtractor(),
            ResidualPatternExtractor(),
        )

    def extract(
        self,
        draws: Iterable[DrawRecord],
        *,
        budget: PatternSearchBudget | None = None,
        residuals: dict[str, float] | None = None,
    ) -> PatternExtractionResult:
        budget = budget or PatternSearchBudget()
        normalized = tuple((str(issue), normalize_red_numbers(numbers)) for issue, numbers in draws)
        patterns: list[PatternCandidate] = []
        family_counts: dict[str, int] = {}
        stopped = False
        for extractor in self.extractors:
            if len(family_counts) >= budget.families:
                stopped = True
                break
            if isinstance(extractor, ResidualPatternExtractor):
                extracted = extractor.extract_draw_patterns(normalized, residuals=residuals, max_patterns=budget.patterns_per_family)
            else:
                extracted = extractor.extract_draw_patterns(normalized, max_patterns=budget.patterns_per_family)
            for pattern in extracted:
                family_count = family_counts.get(pattern.pattern_family, 0)
                if family_count >= budget.patterns_per_family:
                    continue
                if len(family_counts) >= budget.families and pattern.pattern_family not in family_counts:
                    stopped = True
                    break
                family_counts[pattern.pattern_family] = family_count + 1
                patterns.append(pattern)
                if len(patterns) >= budget.families * budget.patterns_per_family:
                    stopped = True
                    break
            if stopped:
                break
        return PatternExtractionResult(tuple(patterns), family_counts, stopped)
