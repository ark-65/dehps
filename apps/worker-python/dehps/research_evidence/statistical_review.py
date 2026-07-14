from __future__ import annotations

from dehps.research.status import EvidenceDirection
from dehps.research_evidence.models import EvidenceStrength, MetricObservation, StatisticalAssessment


class StatisticalReviewer:
    def assess(self, observation: MetricObservation) -> StatisticalAssessment:
        adjusted = observation.adjusted_p_value
        effect = observation.effect_size
        lift = observation.lift
        if adjusted <= 0.05 and effect > 0.2 and lift > 0:
            return StatisticalAssessment(
                direction=EvidenceDirection.SUPPORTING,
                supports_null=False,
                supports_alternative=True,
                strength=EvidenceStrength.STRONG if effect >= 0.5 else EvidenceStrength.MODERATE,
                reason="positive lift with adjusted statistical support",
            )
        if adjusted <= 0.05 and effect < -0.2 and lift < 0:
            return StatisticalAssessment(
                direction=EvidenceDirection.CONTRADICTING,
                supports_null=True,
                supports_alternative=False,
                strength=EvidenceStrength.STRONG if effect <= -0.5 else EvidenceStrength.MODERATE,
                reason="negative lift with adjusted statistical support",
            )
        if abs(effect) < 0.1 or adjusted >= 0.20:
            return StatisticalAssessment(
                direction=EvidenceDirection.NEUTRAL,
                supports_null=True,
                supports_alternative=False,
                strength=EvidenceStrength.WEAK,
                reason="effect is small or not statistically distinguishable from the null",
            )
        return StatisticalAssessment(
            direction=EvidenceDirection.NEUTRAL,
            supports_null=False,
            supports_alternative=False,
            strength=EvidenceStrength.INSUFFICIENT,
            reason="mixed or underpowered evidence",
        )
