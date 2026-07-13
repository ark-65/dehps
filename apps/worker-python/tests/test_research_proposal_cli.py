import json

from typer.testing import CliRunner

from dehps import cli
from dehps.research_autonomy.proposal_engine import AutonomousHypothesisProposalEngine
from research_autonomy_fixtures import make_context


runner = CliRunner()


class Builder:
    def build(self):
        return make_context()


def test_generate_is_stable_json_dry_run_and_does_not_open_agent_context(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_research_context_builder", lambda: Builder())
    monkeypatch.setattr(cli, "_agent_context", lambda: (_ for _ in ()).throw(AssertionError("write path used")))
    result = runner.invoke(cli.app, ["research-proposal", "generate", "--max-candidates", "10"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert len(payload["result"]["candidates"]) == 10
    assert payload["result"]["selected"]["mechanism"] == "ranking_model_disagreement"
    assert result.stdout == json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def test_context_build_serializes_explicit_artifact_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli, "_research_context_builder", lambda: Builder())
    output = tmp_path / "context.json"
    result = runner.invoke(cli.app, ["research-context", "build", "--context-output", str(output)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["context_output"] == output.as_posix()
    assert output.is_file()


def test_validate_reports_success_without_execution(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_research_context_builder", lambda: Builder())
    result = runner.invoke(cli.app, ["research-proposal", "validate"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["validation"]["valid"] is True


def test_research_proposal_cli_has_no_experiment_or_hypothesis_creation_command() -> None:
    result = runner.invoke(cli.app, ["research-proposal", "--help"])
    assert result.exit_code == 0
    assert "experiment-run" not in result.stdout
    assert "hypothesis-create" not in result.stdout
