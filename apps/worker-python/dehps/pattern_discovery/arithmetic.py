from __future__ import annotations

from collections import Counter
from functools import lru_cache
from itertools import combinations
from math import comb
from typing import Iterable

from dehps.domain.combination import iter_ssq_red_combinations, normalize_red_numbers
from dehps.pattern_discovery.models import (
    DEFAULT_PATTERN_GENERATOR_VERSION,
    LEGAL_UNIVERSE_FINGERPRINT,
    PatternCandidate,
    history_fingerprint,
    pattern_key,
    stable_hash,
)


APSignature = tuple[int, int, int]  # (length, start, difference)
DrawRecord = tuple[str, tuple[int, ...]]


def ap_numbers(signature: APSignature) -> tuple[int, ...]:
    length, start, difference = signature
    return tuple(start + difference * idx for idx in range(length))


def ap_subsequences(numbers: Iterable[int], *, min_length: int = 3) -> tuple[APSignature, ...]:
    normalized = normalize_red_numbers(numbers)
    signatures: set[APSignature] = set()
    for length in range(min_length, len(normalized) + 1):
        for subsequence in combinations(normalized, length):
            diffs = [b - a for a, b in zip(subsequence, subsequence[1:])]
            if diffs and len(set(diffs)) == 1:
                signatures.add((length, subsequence[0], diffs[0]))
    return tuple(sorted(signatures))


def count_signature_in_combination(numbers: Iterable[int], signature: APSignature) -> int:
    required = set(ap_numbers(signature))
    return int(required.issubset(set(normalize_red_numbers(numbers))))


def legal_universe_probability(signature: APSignature) -> float:
    length, start, difference = signature
    values = ap_numbers(signature)
    if length < 3 or length > 6 or difference < 1 or min(values) < 1 or max(values) > 33:
        return 0.0
    return comb(33 - length, 6 - length) / comb(33, 6)


@lru_cache(maxsize=4096)
def _matched_null_probability(
    signature: APSignature,
    *,
    sum_value: int | None = None,
    span_value: int | None = None,
    odd_count: int | None = None,
) -> float:
    required = set(ap_numbers(signature))
    if sum_value is not None:
        total = _combination_count_by_sum(sum_value)
        matched = _completion_count_by_sum(tuple(sorted(required)), sum_value - sum(required))
    elif span_value is not None:
        total = _combination_count_by_span(span_value)
        matched = _completion_count_by_span(tuple(sorted(required)), span_value)
    elif odd_count is not None:
        total = _combination_count_by_odd_count(odd_count)
        matched = _completion_count_by_odd_count(tuple(sorted(required)), odd_count)
    else:
        total = comb(33, 6)
        matched = comb(33 - len(required), 6 - len(required))
    return 0.0 if total == 0 else matched / total


@lru_cache(maxsize=256)
def _combination_count_by_sum(sum_value: int) -> int:
    return _count_choose_sum(tuple(range(1, 34)), 6, sum_value)


@lru_cache(maxsize=4096)
def _count_choose_sum(values: tuple[int, ...], choose: int, target_sum: int) -> int:
    if choose == 0:
        return int(target_sum == 0)
    if choose < 0 or target_sum < 0 or len(values) < choose:
        return 0
    head, *tail = values
    tail_tuple = tuple(tail)
    return _count_choose_sum(tail_tuple, choose - 1, target_sum - head) + _count_choose_sum(
        tail_tuple, choose, target_sum
    )


@lru_cache(maxsize=256)
def _combination_count_by_span(span_value: int) -> int:
    if span_value < 5 or span_value > 32:
        return 0
    return sum(comb(span_value - 1, 4) for start in range(1, 34 - span_value))


@lru_cache(maxsize=16)
def _combination_count_by_odd_count(odd_count: int) -> int:
    if odd_count < 0 or odd_count > 6:
        return 0
    return comb(17, odd_count) * comb(16, 6 - odd_count)


@lru_cache(maxsize=4096)
def _completion_count_by_sum(required: tuple[int, ...], remaining_sum: int) -> int:
    remaining_values = tuple(n for n in range(1, 34) if n not in set(required))
    return _count_choose_sum(remaining_values, 6 - len(required), remaining_sum)


@lru_cache(maxsize=4096)
def _completion_count_by_span(required: tuple[int, ...], span_value: int) -> int:
    required_set = set(required)
    choose = 6 - len(required)
    if choose < 0:
        return 0
    total = 0
    for extra in combinations((n for n in range(1, 34) if n not in required_set), choose):
        combo = tuple(sorted((*required, *extra)))
        if combo[-1] - combo[0] == span_value:
            total += 1
    return total


@lru_cache(maxsize=4096)
def _completion_count_by_odd_count(required: tuple[int, ...], odd_count: int) -> int:
    required_odd = sum(1 for n in required if n % 2)
    need_odd = odd_count - required_odd
    choose = 6 - len(required)
    if choose < 0 or need_odd < 0 or need_odd > choose:
        return 0
    remaining_odd = len([n for n in range(1, 34) if n % 2 and n not in set(required)])
    remaining_even = len([n for n in range(1, 34) if n % 2 == 0 and n not in set(required)])
    need_even = choose - need_odd
    if need_even < 0 or need_even > remaining_even or need_odd > remaining_odd:
        return 0
    return comb(remaining_odd, need_odd) * comb(remaining_even, need_even)


def matched_nulls_for_signature(signature: APSignature, draws: tuple[DrawRecord, ...]) -> dict[str, float]:
    probabilities = [legal_universe_probability(signature)]
    same_sum: list[float] = []
    same_span: list[float] = []
    same_odd_even: list[float] = []
    for _, numbers in draws:
        normalized = normalize_red_numbers(numbers)
        same_sum.append(_matched_null_probability(signature, sum_value=sum(normalized)))
        same_span.append(_matched_null_probability(signature, span_value=normalized[-1] - normalized[0]))
        same_odd_even.append(_matched_null_probability(signature, odd_count=sum(1 for n in normalized if n % 2)))
    return {
        "legal_universe": probabilities[0],
        "same_sum": sum(same_sum) / len(same_sum) if same_sum else probabilities[0],
        "same_span": sum(same_span) / len(same_span) if same_span else probabilities[0],
        "same_odd_even": sum(same_odd_even) / len(same_odd_even) if same_odd_even else probabilities[0],
        "random_history_permutation": probabilities[0],
    }


class ArithmeticProgressionExtractor:
    def __init__(self, *, generator_version: str = DEFAULT_PATTERN_GENERATOR_VERSION) -> None:
        self.generator_version = generator_version

    def extract_draw_patterns(
        self,
        draws: Iterable[DrawRecord],
        *,
        search_issue_range: dict[str, object] | None = None,
        max_patterns: int = 80,
    ) -> tuple[PatternCandidate, ...]:
        normalized = tuple((str(issue), normalize_red_numbers(numbers)) for issue, numbers in draws)
        if not normalized:
            return ()
        counts: Counter[APSignature] = Counter()
        supporting_issues: dict[APSignature, list[str]] = {}
        for issue, numbers in normalized:
            for signature in ap_subsequences(numbers):
                counts[signature] += 1
                supporting_issues.setdefault(signature, []).append(issue)
        selected = sorted(counts.items(), key=lambda item: (-item[0][0], -item[1], item[0][2], item[0][1]))[:max_patterns]
        return tuple(
            self._candidate(signature, count, normalized, search_issue_range, supporting_issues.get(signature, ()))
            for signature, count in selected
        )

    def extract_combination_patterns(
        self,
        combinations_: Iterable[Iterable[int]],
        *,
        search_issue_range: dict[str, object] | None = None,
        max_patterns: int = 80,
    ) -> tuple[PatternCandidate, ...]:
        draws = tuple((f"combination-{index:04d}", normalize_red_numbers(numbers)) for index, numbers in enumerate(combinations_, start=1))
        return self.extract_draw_patterns(draws, search_issue_range=search_issue_range, max_patterns=max_patterns)

    def extract_temporal_patterns(
        self,
        draws: Iterable[DrawRecord],
        *,
        windows: tuple[int, ...] = (20, 50, 100),
        search_issue_range: dict[str, object] | None = None,
    ) -> tuple[PatternCandidate, ...]:
        normalized = tuple((str(issue), normalize_red_numbers(numbers)) for issue, numbers in draws)
        if len(normalized) < 2:
            return ()
        output: list[PatternCandidate] = []
        global_counts = Counter(signature for _, numbers in normalized for signature in ap_subsequences(numbers))
        for window in windows:
            if len(normalized) < window:
                continue
            latest = normalized[-window:]
            window_counts = Counter(signature for _, numbers in latest for signature in ap_subsequences(numbers))
            for signature, observed in sorted(window_counts.items(), key=lambda item: (-item[1], item[0]))[:5]:
                expected = max(1.0, global_counts.get(signature, 0) * (window / len(normalized)))
                residual = (observed - expected) / window
                candidate = self._candidate(
                    signature,
                    observed,
                    latest,
                    search_issue_range or {"start": latest[0][0], "end": latest[-1][0], "window": window},
                    [issue for issue, numbers in latest if count_signature_in_combination(numbers, signature)],
                    pattern_type=f"temporal_arithmetic_progression_len_{signature[0]}",
                    metadata={"window": window, "global_count": global_counts.get(signature, 0), "residual": residual},
                )
                output.append(candidate)
        return tuple(output)

    def compare_to_matched_nulls(
        self,
        signature: APSignature,
        draws: Iterable[DrawRecord],
    ) -> dict[str, float]:
        return matched_nulls_for_signature(signature, tuple((str(issue), normalize_red_numbers(numbers)) for issue, numbers in draws))

    def _candidate(
        self,
        signature: APSignature,
        observed_count: int,
        draws: tuple[DrawRecord, ...],
        search_issue_range: dict[str, object] | None,
        supporting_issues: Iterable[str],
        *,
        pattern_type: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> PatternCandidate:
        length, start, difference = signature
        nulls = matched_nulls_for_signature(signature, draws)
        expected_probability = nulls["legal_universe"]
        expected_count = expected_probability * len(draws)
        effect = observed_count - expected_count
        payload = {
            "family": "arithmetic_spacing",
            "type": pattern_type or f"arithmetic_progression_len_{length}",
            "length": length,
            "start": start,
            "difference": difference,
            "history": history_fingerprint(draws),
            "generator": self.generator_version,
        }
        return PatternCandidate(
            pattern_key=pattern_key("pattern-ap", payload),
            pattern_family="arithmetic_spacing",
            pattern_type=pattern_type or f"arithmetic_progression_len_{length}",
            description=(
                f"{length}-term arithmetic progression starting at {start} with difference {difference}; "
                f"observed in {observed_count} draw(s)."
            ),
            input_boundary={
                "domain": "ssq_red_ball",
                "red_min": 1,
                "red_max": 33,
                "red_count": 6,
                "search_issue_range": search_issue_range or {"start": draws[0][0], "end": draws[-1][0]},
            },
            formula={"operator": "contains_arithmetic_progression", "length": length, "start": start, "difference": difference},
            parameters={"length": length, "start": start, "difference": difference},
            observed_support=float(observed_count),
            expected_support=float(expected_count),
            effect_size=0.0 if len(draws) == 0 else float(effect / len(draws)),
            stability_score=self._stability(signature, draws),
            novelty_score=1.0,
            complexity_score=min(1.0, 0.15 + (length - 3) * 0.15),
            search_issue_range=search_issue_range or {"start": draws[0][0], "end": draws[-1][0]},
            history_fingerprint=history_fingerprint(draws),
            legal_universe_fingerprint=LEGAL_UNIVERSE_FINGERPRINT,
            null_definition={
                "primary": "legal_universe",
                "matched": nulls,
                "requires": ("legal_universe", "same_sum", "same_span", "same_odd_even", "random_history_permutation"),
            },
            failure_condition={
                "frozen": "family_adjusted_p_value >= 0.05 or effect_size <= 0",
                "forward": "forward_adjusted_p_value >= 0.05 or direction != search_direction",
            },
            leakage_risks=("post_hoc_parameter_selection", "multiplicity_under_counting", "future_issue_leakage"),
            source_artifacts=tuple(supporting_issues),
            multiplicity_family=f"arithmetic_progression_len_{length}",
            generator_version=self.generator_version,
            metadata={
                "sample_count": len(draws),
                "ap_numbers": ap_numbers(signature),
                "signature_hash": stable_hash(signature),
                **(metadata or {}),
            },
        )

    @staticmethod
    def _stability(signature: APSignature, draws: tuple[DrawRecord, ...]) -> float:
        if len(draws) < 4:
            return 0.5
        midpoint = len(draws) // 2
        left = sum(count_signature_in_combination(numbers, signature) for _, numbers in draws[:midpoint]) / midpoint
        right = sum(count_signature_in_combination(numbers, signature) for _, numbers in draws[midpoint:]) / (len(draws) - midpoint)
        return max(0.0, 1.0 - abs(left - right))
