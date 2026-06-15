from __future__ import annotations

from dehps.domain.combination import normalize_red_numbers


def calculate_red_ball_features(numbers: list[int] | tuple[int, ...]) -> dict[str, int | bool]:
    nums = normalize_red_numbers(numbers)
    gaps = [b - a for a, b in zip(nums, nums[1:])]
    consecutive_pair_count = sum(1 for gap in gaps if gap == 1)

    max_run = 1
    current_run = 1
    for gap in gaps:
        if gap == 1:
            current_run += 1
        else:
            max_run = max(max_run, current_run)
            current_run = 1
    max_run = max(max_run, current_run)

    first_gap = gaps[0]
    is_arithmetic = all(gap == first_gap for gap in gaps)

    return {
        "sum_value": sum(nums),
        "span_value": nums[-1] - nums[0],
        "odd_count": sum(1 for n in nums if n % 2 == 1),
        "even_count": sum(1 for n in nums if n % 2 == 0),
        "small_count": sum(1 for n in nums if n <= 16),
        "big_count": sum(1 for n in nums if n >= 17),
        "zone_1_count": sum(1 for n in nums if 1 <= n <= 11),
        "zone_2_count": sum(1 for n in nums if 12 <= n <= 22),
        "zone_3_count": sum(1 for n in nums if 23 <= n <= 33),
        "consecutive_pair_count": consecutive_pair_count,
        "max_consecutive_run": max_run,
        "min_gap": min(gaps),
        "max_gap": max(gaps),
        "is_arithmetic_sequence": is_arithmetic,
    }

