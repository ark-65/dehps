import json
from dataclasses import dataclass

from typer.testing import CliRunner

from dehps import cli
from dehps.agents.requests import AgentRequestStatus, AgentRequestType
from experiment_plan_fixtures import ranking_plan
from test_experiment_plan_agent_requests import request


runner = CliRunner()


class PlanningService:
    def __init__(self) -> None:
        self.plan = ranking_plan()

    def build(self, *, proposal_request_key=None):
        return self.plan, Approved(), Context()

    def validate(self, *, proposal_request_key=None):
        return self.plan, Report(valid=True)

    def show_plan(self, plan_key):
        return {"plan_key": plan_key, "plan": {"plan_key": plan_key}}

    def list_plans(self, *, limit, offset):
        return [{"plan_key": self.plan.plan_key}]

    def materialize(self, *, proposal_request_key):
        return self.plan, Report(valid=True), Materialized(self.plan)

    def create_engineering_request(self, *, plan_key, requested_by):
        return request(
            "engineering-1",
            AgentRequestType.ENGINEERING_EXPERIMENT_TOOL,
            {},
            AgentRequestStatus.SUBMITTED,
        )

    def create_operator_request(self, *, plan_key, requested_by):
        return request(
            "operator-1",
            AgentRequestType.OPERATOR_ISOLATED_RUN,
            {},
            AgentRequestStatus.DRAFT,
        )


class Approved:
    class Request:
        request_key = "research-proposal-1"

    request = Request()


class Context:
    context_fingerprint = "context"
    fingerprint = "context"


@dataclass(frozen=True)
class Report:
    valid: bool
    checks: tuple = ()
    failure_reasons: tuple = ()


@dataclass(frozen=True)
class Materialized:
    plan_key: str
    hypothesis_key: str
    hypothesis_status: str
    experiment_keys: tuple[str, ...]
    preregistered: bool
    execution_started: bool
    evidence_created: bool

    def __init__(self, plan):
        object.__setattr__(self, "plan_key", plan.plan_key)
        object.__setattr__(self, "hypothesis_key", plan.hypothesis_key)
        object.__setattr__(self, "hypothesis_status", "preregistered")
        object.__setattr__(
            self,
            "experiment_keys",
            (
                "ranking_disagreement_feasibility_v1",
                "ranking_disagreement_historical_search_v1",
                "ranking_disagreement_frozen_validation_v1",
                "ranking_disagreement_forward_validation_v1",
            ),
        )
        object.__setattr__(self, "preregistered", True)
        object.__setattr__(self, "execution_started", False)
        object.__setattr__(self, "evidence_created", False)


def test_experiment_plan_build_is_stable_json_dry_run(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_experiment_planning_service", PlanningService)

    result = runner.invoke(cli.app, ["experiment-plan", "build", "--proposal-request-key", "research-proposal-1"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["writes"] == []
    assert payload["plan"]["mechanism"] == "ranking_model_disagreement"
    assert result.stdout == json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def test_experiment_plan_materialize_and_requests_expose_boundaries(monkeypatch) -> None:
    monkeypatch.setattr(cli, "_experiment_planning_service", PlanningService)

    materialized = runner.invoke(
        cli.app,
        ["experiment-plan", "materialize", "--proposal-request-key", "research-proposal-1"],
    )
    engineering = runner.invoke(
        cli.app,
        ["experiment-plan", "engineering-request", "--plan-key", ranking_plan().plan_key],
    )
    operator = runner.invoke(
        cli.app,
        ["experiment-plan", "operator-request", "--plan-key", ranking_plan().plan_key],
    )

    assert materialized.exit_code == 0
    assert json.loads(materialized.stdout)["experiment_execution_started"] is False
    assert engineering.exit_code == 0
    assert json.loads(engineering.stdout)["submitted"] is True
    assert operator.exit_code == 0
    assert json.loads(operator.stdout)["draft"] is True
    assert json.loads(operator.stdout)["executed"] is False
