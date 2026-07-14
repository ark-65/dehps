from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason_code: str
    summary: str
    details: dict[str, Any]


class WaitingPolicy:
    """Forward evidence gate: if future/forward coverage is insufficient, wait."""

    def evaluate(self, forward_status: dict[str, Any]) -> PolicyDecision:
        paired = int(forward_status.get("paired_issue_count") or 0)
        minimum = int(forward_status.get("min_paired_issues") or 20)
        review_ready = bool(forward_status.get("review_ready", False))
        blockers = tuple(str(item) for item in forward_status.get("blockers", ()))
        if review_ready and paired >= minimum:
            return PolicyDecision(
                True,
                "forward_ready",
                "forward evidence is ready for the next research action",
                {"paired_issue_count": paired, "min_paired_issues": minimum, "blockers": blockers},
            )
        return PolicyDecision(
            False,
            "forward_evidence_insufficient",
            "forward evidence is not ready; scheduler must wait instead of spending compute",
            {"paired_issue_count": paired, "min_paired_issues": minimum, "blockers": blockers},
        )


class StopConditionPolicy:
    def no_work(self, *, active_count: int, open_request_count: int, open_queue_count: int) -> PolicyDecision:
        if active_count or open_request_count or open_queue_count:
            return PolicyDecision(
                True,
                "work_exists",
                "research work exists",
                {
                    "active_hypotheses": active_count,
                    "open_requests": open_request_count,
                    "open_queue": open_queue_count,
                },
            )
        return PolicyDecision(
            False,
            "no_research_work_available",
            "no active hypothesis, queue item, or request is available",
            {
                "active_hypotheses": active_count,
                "open_requests": open_request_count,
                "open_queue": open_queue_count,
            },
        )


class SchedulerPolicy:
    def __init__(
        self,
        waiting_policy: WaitingPolicy | None = None,
        stop_policy: StopConditionPolicy | None = None,
    ) -> None:
        self.waiting_policy = waiting_policy or WaitingPolicy()
        self.stop_policy = stop_policy or StopConditionPolicy()
