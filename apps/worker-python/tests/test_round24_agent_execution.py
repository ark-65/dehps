import pytest

from dehps.agents.errors import AgentRequestValidationError
from dehps.agents.handoffs import validate_engineering_result
from dehps.experiments.ranking_disagreement.cli import _reject_production_database
from dehps.experiments.ranking_disagreement.models import FROZEN_PLAN_FINGERPRINT


def test_round24_engineering_result_contract_accepts_plan_and_artifact_fields() -> None:
    validate_engineering_result(
        {
            "implementation_commit": "abc123",
            "implemented_plan_fingerprint": FROZEN_PLAN_FINGERPRINT,
            "interfaces": {"cli": "dehps ranking-disagreement run-isolated"},
            "test_commands": ["pytest -q"],
            "test_results": {"passed": 1},
            "artifact_paths": [],
            "artifact_contract": {"schema": "ranking-disagreement-artifacts-v1"},
            "interface_contract": {},
            "known_limitations": [],
            "production_impact": "none",
        }
    )


def test_run_isolated_rejects_default_production_database(monkeypatch) -> None:
    monkeypatch.setenv("DB_NAME", "dehps")
    with pytest.raises(ValueError, match="refuses"):
        _reject_production_database()

    monkeypatch.setenv("DB_NAME", "dehps_round24_smoke")
    _reject_production_database()
