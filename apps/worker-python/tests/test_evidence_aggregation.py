from datetime import datetime, timezone

from dehps.research.models import HypothesisEvidence
from dehps.research.status import EvidenceDirection
from dehps.research_evidence.decision_builder import SequentialEvidenceAggregator
from dehps.research_evidence.models import EvidenceStrength


NOW = datetime(2026, 7, 14, tzinfo=timezone.utc)


def evidence(idx: int, direction: EvidenceDirection, stage: str = "frozen_validation", effect: float = 0.0):
    return HypothesisEvidence(
        id=idx,
        hypothesis_id=1,
        experiment_id=2,
        evidence_type="round25_metric",
        direction=direction,
        summary="summary",
        metrics={"effect_size": effect, "stage": stage},
        artifact_path="data/output/a.json",
        content_hash=f"h{idx}",
        observed_at=NOW,
        created_at=NOW,
        metadata={"evidence_key": f"e{idx}", "stage": stage},
    )


def test_evidence_aggregator_tracks_direction_consistency_and_forward_coverage() -> None:
    aggregation = SequentialEvidenceAggregator().aggregate(
        "hypothesis-1",
        [
            evidence(1, EvidenceDirection.NEUTRAL),
            evidence(2, EvidenceDirection.NEUTRAL, stage="forward_validation"),
        ],
    )

    assert aggregation.evidence_count == 2
    assert aggregation.forward_coverage == 1
    assert aggregation.evidence_strength == EvidenceStrength.WEAK
