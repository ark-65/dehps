from __future__ import annotations

from dataclasses import dataclass, field

from dehps.advisors.protocol import AdvisorContext
from dehps.advisors.registry import AdvisorRegistry
from dehps.advisors.weight_kdj_adapter import WeightKdjAdvisorAdapter
from dehps.evaluation.models import BaselineComparison, EvaluationResult, LeakageReport
from dehps.evaluation.promotion import PromotionGate
from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.training.context import FrozenTrainingContext
from dehps.training.dependencies import TrainingDependencies
from dehps.training.models import (
    CandidateProposal,
    CandidateSummary,
    EvaluatedRound,
    TrainingRoundRequest,
)
from dehps.training.round_runner import TrainingRoundRunner
from dehps.training.runtime_round_executor import (
    RuntimeRoundOutcome,
    RuntimeRoundRequest,
    RuntimeTrainingState,
)


def _evaluation(objective: float, top_10000_hits: int) -> EvaluationResult:
    return EvaluationResult(
        objective=objective,
        top_100_hits=0,
        top_1000_hits=0,
        top_10000_hits=top_10000_hits,
        median_rank=400_000,
        p95_rank=700_000,
        worst_rank=700_000,
        tail_risk=1.0,
        tail_over_750000_count=0,
        tail_over_900000_count=0,
        tail_over_1000000_count=0,
        baseline_comparison=BaselineComparison(),
        leakage_report=LeakageReport(),
    )


@dataclass
class FakeRepository:
    context: FrozenTrainingContext
    calls: list[str] = field(default_factory=list)
    saved_result: object | None = None

    def load_context(self, request: TrainingRoundRequest) -> FrozenTrainingContext:
        self.calls.append("load")
        return self.context

    def save_round(self, request: TrainingRoundRequest, result: object) -> None:
        self.calls.append("save")
        self.saved_result = result


@dataclass
class FakeSearch:
    calls: list[str]

    def propose(self, request: TrainingRoundRequest, context: FrozenTrainingContext) -> tuple[CandidateProposal, ...]:
        self.calls.append("search")
        return (
            CandidateProposal(FrequencyRankerConfig(frequency_weight=0.4), "exploration", "search_v1"),
        )


@dataclass
class FakeEvaluator:
    calls: list[str]

    def evaluate(self, request, context, candidates) -> EvaluatedRound:
        self.calls.append("evaluate")
        summaries = tuple(
            CandidateSummary(
                config_hash=f"hash-{index}",
                source_key=candidate.source_key,
                protocol_version=candidate.protocol_version,
                metrics={"order": index},
            )
            for index, candidate in enumerate(candidates)
        )
        return EvaluatedRound(summaries, _evaluation(12.0, 1))


@dataclass
class FakeWriter:
    calls: list[str]

    def write(self, request, evaluated, decision):
        self.calls.append("artifact")
        return ("round.json",)


@dataclass
class FakePublisher:
    calls: list[str]

    def publish(self, request, result) -> None:
        self.calls.append("event")


def test_training_round_runner_is_independently_testable_and_dependency_injected() -> None:
    calls: list[str] = []
    repository = FakeRepository(
        FrozenTrainingContext(
            advisor_context=AdvisorContext(FrequencyRankerConfig()),
            current_best=_evaluation(10.0, 0),
            values={"advisor_budgets": {"weight_kdj": 1}},
        ),
        calls,
    )
    registry = AdvisorRegistry.build(
        (
            WeightKdjAdvisorAdapter(
                lambda context, budget: (FrequencyRankerConfig(frequency_weight=0.5),)[:budget]
            ),
        )
    )
    runner = TrainingRoundRunner(
        TrainingDependencies(
            repository=repository,
            candidate_search=FakeSearch(calls),
            advisor_registry=registry,
            evaluator=FakeEvaluator(calls),
            promotion_gate=PromotionGate(),
            event_publisher=FakePublisher(calls),
            artifact_writer=FakeWriter(calls),
        )
    )
    request = TrainingRoundRequest(
        run_id="run-1",
        round_index=1,
        as_of_issue="2026067",
        history_fingerprint="history",
        objective_policy_version="rank_objective_v1",
        objective_policy_hash="policy-hash",
        candidate_budget=2,
        random_seed=17,
    )

    result = runner.run(request)

    assert [summary.source_key for summary in result.candidate_summaries] == ["exploration", "weight_kdj"]
    assert [summary.protocol_version for summary in result.candidate_summaries] == ["search_v1", "weight_kdj_advisor_v1"]
    assert result.promotion_decision.accepted is True
    assert result.artifacts == ("round.json",)
    assert result.warnings == ()
    assert calls == ["load", "search", "evaluate", "artifact", "save", "event"]
    assert repository.saved_result is result


def test_production_round_runner_executes_explicit_requests_without_generator_adapter() -> None:
    request = RuntimeRoundRequest(
        TrainingRoundRequest(
            run_id="run-1",
            round_index=1,
            as_of_issue="2026067",
            history_fingerprint="history",
            objective_policy_version="rank_objective_v1",
            objective_policy_hash="policy-hash",
            candidate_budget=2,
            random_seed=17,
        )
    )

    class Executor:
        def execute(self, actual_request, state):
            assert actual_request is request
            state.completed_rounds += 1
            return RuntimeRoundOutcome(
                request=actual_request,
                result={"run_id": "run-1", "rounds": [{"round": 1}], "status": "running"},
            )

    class Session:
        state = RuntimeTrainingState()
        executor = Executor()

        def __init__(self):
            self.pending = [request]

        def next_request(self):
            return self.pending.pop(0) if self.pending else None

        def finish(self, *, status="completed", error=None):
            return {"run_id": "run-1", "rounds": [{"round": 1}], "status": status}

    runner = TrainingRoundRunner.for_production(Session())

    actual_request = runner.next_request()
    assert actual_request is request
    assert runner.run(actual_request)["rounds"] == [{"round": 1}]
    assert runner.next_request() is None
    assert runner.finish()["status"] == "completed"
    assert not hasattr(runner, "run_runtime_round")
