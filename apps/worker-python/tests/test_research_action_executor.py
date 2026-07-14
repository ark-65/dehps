from types import SimpleNamespace

from dehps.research_runtime.executor import PatternDiscoveryActionExecutor
from dehps.research_runtime.models import HistorySnapshot, ResearchRuntimeBudget, ResearchRuntimeQueueItem


class PatternService:
    def __init__(self) -> None:
        self.calls = []
        self.repository = SimpleNamespace(
            load_history=lambda: tuple(
                (f"{index:04d}", (1, 2, 3, 10, 20, 30))
                for index in range(1, 501)
            )
        )

    def cycle(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            cycle_key="pattern-cycle-1",
            status="completed",
            patterns=(object(), object()),
            validations=(object(),),
            features=(object(),),
            strategies=(object(),),
            submitted_request_key="request-1" if kwargs.get("submit") else None,
            writes=("pattern-1", "feature-1"),
            search_issue_range={"start": "0001", "end": "0500"},
        )

    def status(self):
        return {
            "repository": {
                "pattern_count": 2,
                "feature_count": 1,
                "strategy_count": 1,
            }
        }


def test_pattern_discovery_executor_runs_research_cycle_and_reports_writes() -> None:
    service = PatternService()
    lane_calls = []

    def lane_runner(payload):
        lane_calls.append(payload)
        return {
            "executed": True,
            "reason_code": "pattern_lane_executed",
            "lane_key": payload["lane_key"],
            "discovered_count": 2,
            "validation_count": 1,
            "feature_count": 1,
            "strategy_count": 1,
            "submitted_request_key": "request-1" if payload["submit"] else None,
            "writes_count": 2,
        }

    executor = PatternDiscoveryActionExecutor(service, lane_runner=lane_runner)  # type: ignore[arg-type]

    result = executor.execute(
        item=ResearchRuntimeQueueItem(
            queue_key="queue-1",
            action="proposal_generation",
            status="queued",
            snapshot_key="snapshot-1",
            history_fingerprint="fp",
        ),
        snapshot=HistorySnapshot("snapshot-1", "2026079", 1, "fp"),
        budget=ResearchRuntimeBudget(research_cpu=2, research_memory_gb=18),
    )

    assert result["executed"] is True
    assert result["reason_code"] == "parallel_pattern_discovery_executed"
    assert result["parallel_lanes"] == 2
    assert result["max_workers"] == 2
    assert result["discovered_count"] == 4
    assert result["feature_count"] == 2
    assert result["strategy_count"] == 2
    assert result["submitted_request_key"] == "request-1"
    assert result["repository"]["pattern_count"] == 2
    assert len(lane_calls) == 2
    assert [call["submit"] for call in lane_calls] == [True, False]


def test_pattern_discovery_executor_skips_unwired_actions() -> None:
    result = PatternDiscoveryActionExecutor(PatternService()).execute(  # type: ignore[arg-type]
        item=ResearchRuntimeQueueItem(
            queue_key="queue-1",
            action="isolated_experiment",
            status="queued",
            snapshot_key="snapshot-1",
            history_fingerprint="fp",
        ),
        snapshot=HistorySnapshot("snapshot-1", "2026079", 1, "fp"),
        budget=ResearchRuntimeBudget(),
    )

    assert result["executed"] is False
    assert result["reason_code"] == "research_action_not_wired_to_resident_executor"
