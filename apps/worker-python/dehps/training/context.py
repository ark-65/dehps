from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from dehps.advisors.protocol import AdvisorContext
from dehps.evaluation.models import EvaluationResult


@dataclass(frozen=True)
class FrozenTrainingContext:
    advisor_context: AdvisorContext
    current_best: EvaluationResult | None = None
    values: Mapping[str, object] | None = None
