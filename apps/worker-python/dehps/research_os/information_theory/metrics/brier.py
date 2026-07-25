from __future__ import annotations


def brier_per_number_event(target: int, clipped_probability: float) -> float:
    return (clipped_probability - target) ** 2
