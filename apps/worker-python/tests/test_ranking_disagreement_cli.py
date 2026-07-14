from typer.testing import CliRunner

from dehps.experiments.ranking_disagreement.artifacts import ArtifactWriter
from dehps.experiments.ranking_disagreement.cli import app


def test_cli_validate_artifacts_is_stable_json(tmp_path) -> None:
    writer = ArtifactWriter(
        base_directory=tmp_path,
        history_fingerprint="history",
        legal_universe_fingerprint="universe",
    )
    writer.write_json("validation_report.json", {"valid": True})
    writer.write_manifest()

    result = CliRunner().invoke(app, ["validate-artifacts", str(tmp_path)])

    assert result.exit_code == 0
    assert '"valid":true' in result.output
