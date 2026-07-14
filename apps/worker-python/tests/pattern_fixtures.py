from __future__ import annotations

from dehps.pattern_discovery.arithmetic import ArithmeticProgressionExtractor
from dehps.pattern_discovery.models import PatternCandidate


HISTORY = [
    ("001", (1, 2, 3, 10, 20, 30)),
    ("002", (4, 8, 12, 16, 22, 33)),
    ("003", (1, 5, 9, 13, 21, 32)),
    ("004", (2, 4, 6, 8, 10, 12)),
    ("005", (3, 6, 9, 12, 15, 18)),
]


def ap_candidate(length: int = 3, start: int = 1, difference: int = 1) -> PatternCandidate:
    patterns = ArithmeticProgressionExtractor().extract_draw_patterns(HISTORY, max_patterns=100)
    for pattern in patterns:
        if pattern.parameters == {"length": length, "start": start, "difference": difference}:
            return pattern
    raise AssertionError("fixture AP candidate not found")
