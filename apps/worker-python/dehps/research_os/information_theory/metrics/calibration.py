from __future__ import annotations

from math import fsum
from typing import Sequence


def issue_calibration_statistics(
    probabilities: Sequence[float],
    *,
    actual_red_count: int = 6,
) -> dict[str, float | int]:
    predicted_count = fsum(probabilities)
    return {
        "mean_predicted_probability": predicted_count / 33,
        "predicted_red_count": predicted_count,
        "actual_red_count": actual_red_count,
        "red_count_error": predicted_count - actual_red_count,
    }
