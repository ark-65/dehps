from __future__ import annotations

from dehps.pattern_discovery.arithmetic import APSignature, count_signature_in_combination


def window_stability(
    draws: tuple[tuple[str, tuple[int, ...]], ...],
    signature: APSignature,
    *,
    window_count: int = 3,
) -> float:
    if not draws or window_count < 1:
        return 0.0
    size = max(1, len(draws) // window_count)
    rates: list[float] = []
    for index in range(0, len(draws), size):
        window = draws[index:index + size]
        if not window:
            continue
        rates.append(sum(count_signature_in_combination(numbers, signature) for _, numbers in window) / len(window))
    if len(rates) < 2:
        return 0.5
    return max(0.0, 1.0 - (max(rates) - min(rates)))
