from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from dehps.research_os.information_theory.walk_forward.contracts import (
    BlindTestFeatureView,
    ProbeState,
)


class PreparedProbe(Protocol):
    state: ProbeState

    def predict(self, view: BlindTestFeatureView) -> tuple[float, ...]: ...


@dataclass(frozen=True)
class ProbePrediction:
    probabilities: tuple[float, ...]
    probability_order: str = "red_numbers_1_to_33"

    def __post_init__(self) -> None:
        if len(self.probabilities) != 33:
            raise ValueError("probe prediction must contain 33 probabilities")
