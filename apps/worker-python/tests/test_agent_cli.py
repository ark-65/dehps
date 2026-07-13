import json

from typer.testing import CliRunner

from dehps import cli


runner = CliRunner()


def test_authorize_is_database_free_stable_json_dry_run(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_agent_context", lambda: (_ for _ in ()).throw(AssertionError("DB used")))
    result = runner.invoke(
        cli.app,
        ["agent", "authorize", "--role", "engineering", "--action", "modify_code",
         "--request-type", "engineering_implementation", "--request-status", "approved",
         "--environment", "development"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["authorization"]["allowed"] is True
    assert result.stdout == json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def test_unauthorized_cli_dry_run_returns_exit_code_two() -> None:
    result = runner.invoke(
        cli.app,
        ["agent", "authorize", "--role", "research", "--action", "modify_code"],
    )
    assert result.exit_code == 2
    assert json.loads(result.stdout)["authorization"]["allowed"] is False


def test_agent_cli_exposes_no_shell_git_or_supervisor_execution_command() -> None:
    result = runner.invoke(cli.app, ["agent", "--help"])
    assert result.exit_code == 0
    for forbidden in ("shell", "git-commit", "git-push", "supervisor-start"):
        assert forbidden not in result.stdout
