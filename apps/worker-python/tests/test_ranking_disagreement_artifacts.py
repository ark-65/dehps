from pathlib import Path

from dehps.experiments.ranking_disagreement.artifacts import ArtifactWriter, validate_manifest


def test_artifacts_are_hashed_and_manifest_validates(tmp_path: Path) -> None:
    writer = ArtifactWriter(
        base_directory=tmp_path,
        history_fingerprint="history",
        legal_universe_fingerprint="universe",
    )
    writer.write_json("feasibility.json", {"ok": True})
    writer.write_jsonl("per_issue_results.jsonl", [{"issue": "1"}])
    writer.write_manifest()

    assert validate_manifest(tmp_path / "manifest.json")["valid"] is True
