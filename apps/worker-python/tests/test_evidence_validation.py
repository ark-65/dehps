from dehps.experiments.ranking_disagreement.models import FROZEN_HYPOTHESIS_KEY, FROZEN_PLAN_FINGERPRINT
from dehps.research_evidence.artifact_reader import Round24ArtifactReader
from round25_fixtures import make_round24_artifacts


def test_artifact_reader_validates_hashes_fingerprints_and_windows(tmp_path) -> None:
    artifact_dir = make_round24_artifacts(tmp_path)

    report = Round24ArtifactReader().read(
        artifact_dir,
        expected_hypothesis_key=FROZEN_HYPOTHESIS_KEY,
        expected_plan_fingerprint=FROZEN_PLAN_FINGERPRINT,
    )

    assert report.valid is True
    assert report.hypothesis_key == FROZEN_HYPOTHESIS_KEY


def test_artifact_reader_invalidates_hash_mismatch(tmp_path) -> None:
    artifact_dir = make_round24_artifacts(tmp_path)
    (artifact_dir / "statistics.json").write_text("{}", encoding="utf-8")

    report = Round24ArtifactReader().read(artifact_dir)

    assert report.valid is False
    assert any("statistics.json hash" in reason for reason in report.failure_reasons)
