from dehps.research.status import EvidenceDirection
from dehps.research_evidence.models import EvidenceRecord
from dehps.research_evidence.validation import validate_promotion_evidence_sources
from dehps.research_runtime.models import EvidenceSource


def record(source: EvidenceSource) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_key=f"evidence-{source.value}",
        hypothesis_key="hypothesis-1",
        experiment_key="experiment-1",
        metric="top10000",
        value=1.0,
        baseline="baseline",
        lift=1.0,
        effect_size=0.0,
        confidence_interval={},
        p_value=1.0,
        adjusted_p_value=1.0,
        direction=EvidenceDirection.NEUTRAL,
        supports_null=True,
        supports_alternative=False,
        stage="historical",
        stratum="all",
        artifact_path="/tmp/artifact.json",
        content_hash=f"hash-{source.value}",
        summary="test",
        evidence_source=source,
    )


def test_research_evidence_is_not_promotion_evidence() -> None:
    result = validate_promotion_evidence_sources((record(EvidenceSource.RESEARCH),))

    assert result["valid"] is False
    assert "promotion_requires_forward_evidence" in result["failure_reasons"][0]


def test_forward_evidence_can_support_promotion_review() -> None:
    result = validate_promotion_evidence_sources((record(EvidenceSource.FORWARD),))

    assert result["valid"] is True
