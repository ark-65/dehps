from __future__ import annotations

from typing import Iterable

from dehps.domain.combination import normalize_red_numbers
from dehps.pattern_discovery.models import (
    DEFAULT_PATTERN_GENERATOR_VERSION,
    LEGAL_UNIVERSE_FINGERPRINT,
    PatternCandidate,
    history_fingerprint,
    pattern_key,
)


DrawRecord = tuple[str, tuple[int, ...]]


class ResidualPatternExtractor:
    """Declarative residual hooks; it reads supplied residual artifacts but never runs a model."""

    def __init__(self, *, generator_version: str = DEFAULT_PATTERN_GENERATOR_VERSION) -> None:
        self.generator_version = generator_version

    def extract_draw_patterns(
        self,
        draws: Iterable[DrawRecord],
        *,
        residuals: dict[str, float] | None = None,
        max_patterns: int = 10,
    ) -> tuple[PatternCandidate, ...]:
        normalized = tuple((str(issue), normalize_red_numbers(numbers)) for issue, numbers in draws)
        residuals = residuals or {}
        if not normalized or not residuals:
            return ()
        selected = sorted(residuals.items(), key=lambda item: (-abs(float(item[1])), item[0]))[:max_patterns]
        return tuple(self._candidate(metric, value, normalized) for metric, value in selected)

    def _candidate(self, metric: str, value: float, draws: tuple[DrawRecord, ...]) -> PatternCandidate:
        payload = {"metric": metric, "value": round(float(value), 6), "history": history_fingerprint(draws), "generator": self.generator_version}
        return PatternCandidate(
            pattern_key=pattern_key("pattern-residual", payload),
            pattern_family="residual_model",
            pattern_type="baseline_rank_residual",
            description=f"Residual metric {metric} has absolute residual {value:.6f}.",
            input_boundary={"domain": "ssq_red_ball", "artifact_only": True},
            formula={"operator": "residual", "metric": metric},
            parameters={"metric": metric, "value": float(value)},
            observed_support=abs(float(value)),
            expected_support=0.0,
            effect_size=float(value),
            stability_score=0.5,
            novelty_score=1.0,
            complexity_score=0.3,
            search_issue_range={"start": draws[0][0], "end": draws[-1][0]},
            history_fingerprint=history_fingerprint(draws),
            legal_universe_fingerprint=LEGAL_UNIVERSE_FINGERPRINT,
            null_definition={"primary": "sequential_null", "matched": {"expected_residual": 0.0}},
            failure_condition={"frozen": "confidence_interval includes zero"},
            leakage_risks=("artifact_boundary_mismatch", "sequential_null_reuse"),
            source_artifacts=(metric,),
            multiplicity_family="residual_model",
            generator_version=self.generator_version,
            metadata={"sample_count": len(draws)},
        )
