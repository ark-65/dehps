from __future__ import annotations

from collections import Counter
from typing import Iterable

from dehps.domain.combination import normalize_red_numbers

YANG_LINE = "—"
YIN_LINE = "- -"
QIAN_PATTERN = "111111"
KUN_PATTERN = "000000"


def qian_kun_bits(numbers: tuple[int, ...] | list[int]) -> tuple[int, int, int, int, int, int]:
    nums = normalize_red_numbers(numbers)
    return (
        nums[0] % 2,
        nums[1] % 2,
        nums[2] % 2,
        nums[3] % 2,
        nums[4] % 2,
        nums[5] % 2,
    )


def qian_kun_pattern(numbers: tuple[int, ...] | list[int]) -> str:
    return "".join(str(bit) for bit in qian_kun_bits(numbers))


def qian_kun_lines_from_pattern(pattern: str) -> list[str]:
    return [YANG_LINE if bit == "1" else YIN_LINE for bit in pattern]


def qian_kun_label(pattern: str) -> str:
    if pattern == QIAN_PATTERN:
        return "乾卦"
    if pattern == KUN_PATTERN:
        return "坤卦"
    yang_count = pattern.count("1")
    return f"{pattern} 阳{yang_count}/阴{6 - yang_count}"


def qian_kun_similarity(left: str, right: str) -> float:
    if len(left) != 6 or len(right) != 6:
        return 0.0
    return sum(left_bit == right_bit for left_bit, right_bit in zip(left, right, strict=True)) / 6


def qian_kun_distribution(
    history: Iterable[tuple[str, tuple[int, ...]]],
    *,
    recent_window: int = 100,
) -> dict:
    rows = list(history)
    counts = Counter(qian_kun_pattern(numbers) for _, numbers in rows)
    recent_counts = Counter(qian_kun_pattern(numbers) for _, numbers in rows[-recent_window:])
    total = len(rows)
    recent_total = min(recent_window, total)
    latest_issue = rows[-1][0] if rows else ""
    latest_numbers = rows[-1][1] if rows else ()
    latest_pattern = qian_kun_pattern(latest_numbers) if latest_numbers else ""

    all_patterns = sorted(set(counts) | set(recent_counts) | {QIAN_PATTERN, KUN_PATTERN})
    distribution = [
        {
            "pattern": pattern,
            "label": qian_kun_label(pattern),
            "lines": qian_kun_lines_from_pattern(pattern),
            "count": counts.get(pattern, 0),
            "rate": counts.get(pattern, 0) / total if total else 0,
            "recent_count": recent_counts.get(pattern, 0),
            "recent_rate": recent_counts.get(pattern, 0) / recent_total if recent_total else 0,
        }
        for pattern in all_patterns
    ]
    distribution.sort(key=lambda item: (item["count"], item["recent_count"], item["pattern"]), reverse=True)

    return {
        "total_draws": total,
        "recent_window": recent_total,
        "latest_issue": latest_issue,
        "latest_numbers": list(latest_numbers),
        "latest_pattern": latest_pattern,
        "latest_label": qian_kun_label(latest_pattern) if latest_pattern else "",
        "latest_lines": qian_kun_lines_from_pattern(latest_pattern) if latest_pattern else [],
        "qian_count": counts.get(QIAN_PATTERN, 0),
        "kun_count": counts.get(KUN_PATTERN, 0),
        "patterns": distribution,
    }
