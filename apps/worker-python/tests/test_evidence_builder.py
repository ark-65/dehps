from dehps.research_evidence.artifact_reader import Round24ArtifactReader
from dehps.research_evidence.evidence_builder import EvidenceBuilder
from dehps.research_evidence.metrics_loader import MetricsLoader
from round25_fixtures import make_round24_artifacts


def test_evidence_builder_creates_one_record_per_statistical_comparison(tmp_path) -> None:
    report = Round24ArtifactReader().read(make_round24_artifacts(tmp_path))
    observations = MetricsLoader().load(report)
    records = EvidenceBuilder().build(report=report, observations=observations)

    assert len(observations) == 12
    assert len(records) == 12
    first = records[0]
    assert first.metric == "paired_target_hit_lift"
    assert first.content_hash
    assert first.supports_null is True
    assert first.supports_alternative is False
