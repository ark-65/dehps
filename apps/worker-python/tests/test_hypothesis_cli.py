from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from dehps import cli
from dehps.research.errors import InvalidTransitionError
from dehps.research.models import Hypothesis, HypothesisFamily
from dehps.research.status import HypothesisFamilyStatus, HypothesisStatus, RejectionScope


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)
runner = CliRunner()


def family() -> HypothesisFamily:
    return HypothesisFamily(
        id=1,
        family_key="family-1",
        title="Family",
        description="description",
        mechanism="mechanism",
        status=HypothesisFamilyStatus.ACTIVE,
        rejection_scope=RejectionScope.NONE,
        rejection_reason=None,
        reopen_condition=None,
        created_at=NOW,
        updated_at=NOW,
        resolved_at=None,
    )


def hypothesis(status=HypothesisStatus.PROPOSED) -> Hypothesis:
    return Hypothesis(
        id=2,
        hypothesis_key="hypothesis-1",
        family_id=1,
        parent_hypothesis_id=None,
        title="Hypothesis",
        statement="statement",
        mechanism="mechanism",
        null_hypothesis="null",
        minimal_non_null="minimal",
        invariants=["frozen"],
        baseline_definition={"key": "baseline"},
        metric_definition={"key": "metric"},
        failure_condition={"key": "failure"},
        self_deception_risk=["seed"],
        status=status,
        rejection_scope=RejectionScope.NONE,
        rejection_reason=None,
        reopen_condition=None,
        created_at=NOW,
        updated_at=NOW,
        preregistered_at=None,
        started_at=None,
        resolved_at=None,
    )


class FakeRepository:
    def __init__(self) -> None:
        self.value = hypothesis()
        self.family_value = family()

    def create_family(self, **kwargs):
        return self.family_value

    def list_families(self, **kwargs):
        return [self.family_value]

    def create_hypothesis(self, **kwargs):
        return self.value

    def list_hypotheses(self, **kwargs):
        return [self.value]

    def get_hypothesis(self, key):
        return self.value

    def list_decisions(self, key):
        return []


class FakeService:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository

    def preregister(self, key, **kwargs):
        self.repository.value = replace(self.repository.value, status=HypothesisStatus.PREREGISTERED)
        return self.repository.value

    def start(self, key, **kwargs):
        if self.repository.value.status != HypothesisStatus.PREREGISTERED:
            raise InvalidTransitionError("invalid hypothesis transition")
        self.repository.value = replace(self.repository.value, status=HypothesisStatus.RUNNING)
        return self.repository.value


def install_fake(monkeypatch):
    repository = FakeRepository()
    service = FakeService(repository)
    monkeypatch.setattr(cli, "_registry_context", lambda: (repository, service))
    return repository, service


def write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value))
    return path


def test_cli_lists_stable_json(monkeypatch) -> None:
    install_fake(monkeypatch)

    result = runner.invoke(cli.app, ["hypothesis", "family-list"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["families"][0]["family_key"] == "family-1"
    assert result.stdout == json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def test_cli_reads_complex_hypothesis_json(monkeypatch, tmp_path: Path) -> None:
    install_fake(monkeypatch)
    input_file = write_json(
        tmp_path / "hypothesis.json",
        {
            "hypothesis_key": "hypothesis-1",
            "family_key": "family-1",
            "title": "Hypothesis",
            "mechanism": "mechanism",
            "invariants": ["frozen history"],
            "baseline_definition": {"key": "baseline"},
            "metric_definition": {"key": "objective"},
        },
    )

    result = runner.invoke(cli.app, ["hypothesis", "create", "--input", str(input_file)])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["hypothesis"]["hypothesis_key"] == "hypothesis-1"


def test_cli_lifecycle_and_nonzero_invalid_transition(monkeypatch) -> None:
    install_fake(monkeypatch)

    preregister = runner.invoke(
        cli.app,
        ["hypothesis", "preregister", "hypothesis-1", "--decided-by", "human:test"],
    )
    start = runner.invoke(
        cli.app,
        ["hypothesis", "start", "hypothesis-1", "--decided-by", "human:test"],
    )
    invalid = runner.invoke(
        cli.app,
        ["hypothesis", "start", "hypothesis-1", "--decided-by", "human:test"],
    )

    assert preregister.exit_code == 0
    assert start.exit_code == 0
    assert json.loads(start.stdout)["hypothesis"]["status"] == "running"
    assert invalid.exit_code == 2
    assert "error: invalid hypothesis transition" in invalid.stderr


def test_cli_rejects_non_object_json(monkeypatch, tmp_path: Path) -> None:
    install_fake(monkeypatch)
    input_file = tmp_path / "input.json"
    input_file.write_text("[]")

    result = runner.invoke(cli.app, ["hypothesis", "create", "--input", str(input_file)])

    assert result.exit_code == 2
    assert "JSON input must be an object" in result.stderr
