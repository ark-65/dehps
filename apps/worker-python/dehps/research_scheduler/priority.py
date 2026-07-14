from __future__ import annotations

from typing import Any

from dehps.research_scheduler.budget import BudgetManager
from dehps.research_scheduler.policy import SchedulerPolicy
from dehps.research_scheduler.state import (
    NextResearchAction,
    QueueStatus,
    ROUND26_SCHEMA_VERSION,
    ResearchAction,
    SchedulerState,
)


class ResearchPriorityEngine:
    """Deterministic priority policy for selecting exactly one next action."""

    def __init__(
        self,
        *,
        policy: SchedulerPolicy | None = None,
        budget_manager: BudgetManager | None = None,
    ) -> None:
        self.policy = policy or SchedulerPolicy()
        self.budget_manager = budget_manager or BudgetManager()

    def next_action(self, state: SchedulerState) -> NextResearchAction:
        budget_stop = self.budget_manager.stop_if_exhausted()
        if budget_stop is not None:
            return self._action(
                state,
                ResearchAction.STOP,
                QueueStatus.BLOCKED,
                "budget exhausted; scheduler stops",
                {"reason_code": budget_stop.reason_code, "summary": budget_stop.summary},
                priority=0.0,
            )

        if state.open_agent_requests:
            request = sorted(state.open_agent_requests, key=lambda item: item.request_key)[0]
            return self._action(
                state,
                ResearchAction.WAIT_FORWARD,
                QueueStatus.WAITING_FORWARD,
                "open Agent Request exists; scheduler waits for review/execution completion",
                {
                    "reason_code": "open_agent_request",
                    "request_key": request.request_key,
                    "request_type": request.request_type,
                    "request_status": request.status,
                },
                priority=0.2,
                existing_request_key=request.request_key,
            )

        open_queue = tuple(sorted(state.open_queue, key=lambda item: (-item.priority_score, item.queue_key)))
        if open_queue:
            item = open_queue[0]
            return self._action(
                state,
                ResearchAction.CONTINUE_EXISTING,
                item.queue_status,
                "open scheduler queue item exists; continue it before creating new work",
                {
                    "reason_code": "open_queue_item",
                    "queue_key": item.queue_key,
                    "queued_action": item.action.value,
                    "queued_status": item.queue_status.value,
                },
                priority=max(0.3, float(item.priority_score)),
                target_hypothesis_key=item.target_hypothesis_key,
                target_family_key=item.target_family_key,
                target_experiment_key=item.target_experiment_key,
                existing_queue_key=item.queue_key,
                existing_request_key=item.request_key,
            )

        wait = self.policy.waiting_policy.evaluate(state.training_status.forward_evidence_status)
        if not wait.allowed:
            return self._action(
                state,
                ResearchAction.WAIT_FORWARD_PATTERN if state.pattern_discovery.get("enabled") else ResearchAction.WAIT_FORWARD,
                QueueStatus.WAITING_FORWARD,
                wait.summary,
                {"reason_code": wait.reason_code, **wait.details},
                priority=0.1,
            )

        active = list(state.active_hypotheses)
        candidate = self._best_active_hypothesis(active)
        if candidate is not None:
            action, status, summary, priority = self._action_for_hypothesis(candidate, state)
            budget = self.budget_manager.authorize(action)
            if not budget.allowed:
                return self._action(
                    state,
                    ResearchAction.STOP,
                    QueueStatus.BLOCKED,
                    budget.summary,
                    {"reason_code": budget.reason_code, "blocked_action": action.value},
                    priority=0.0,
                    target_hypothesis_key=self._field(candidate, "hypothesis_key"),
                    target_family_key=self._field(candidate, "family_key"),
                )
            return self._action(
                state,
                action,
                status,
                summary,
                {
                    "reason_code": "active_hypothesis_selected",
                    "hypothesis_status": self._field(candidate, "status"),
                    "family_diversity": self._family_diversity(state, candidate),
                    "information_gain": priority,
                    "forward_gate": wait.reason_code,
                },
                priority=priority,
                target_hypothesis_key=self._field(candidate, "hypothesis_key"),
                target_family_key=self._field(candidate, "family_key"),
            )

        pattern_action = self._pattern_action(state, wait_reason=wait.reason_code)
        if pattern_action is not None:
            budget = self.budget_manager.authorize(pattern_action[0])
            if not budget.allowed:
                return self._action(
                    state,
                    ResearchAction.STOP,
                    QueueStatus.BLOCKED,
                    budget.summary,
                    {"reason_code": budget.reason_code, "blocked_action": pattern_action[0].value},
                    priority=0.0,
                    target_family_key="pattern_discovery",
                )
            return self._action(
                state,
                pattern_action[0],
                pattern_action[1],
                pattern_action[2],
                pattern_action[3],
                priority=pattern_action[4],
                target_family_key="pattern_discovery",
            )

        proposal_budget = self.budget_manager.authorize(ResearchAction.CREATE_PROPOSAL_REQUEST)
        if not proposal_budget.allowed:
            return self._action(
                state,
                ResearchAction.STOP,
                QueueStatus.BLOCKED,
                proposal_budget.summary,
                {"reason_code": proposal_budget.reason_code},
                priority=0.0,
            )

        return self._action(
            state,
            ResearchAction.CREATE_PROPOSAL_REQUEST,
            QueueStatus.PROPOSAL,
            "forward gate is ready and no active hypothesis is available; request a new proposal",
            {
                "reason_code": "new_proposal_needed",
                "rejected_family_count": len(state.rejected_families),
                "forward_gate": wait.reason_code,
                "information_gain": 0.65,
                "duplicate_risk": 0.0,
            },
            priority=0.65,
        )

    def _pattern_action(
        self,
        state: SchedulerState,
        *,
        wait_reason: str,
    ) -> tuple[ResearchAction, QueueStatus, str, dict[str, Any], float] | None:
        summary = dict(state.pattern_discovery or {})
        if not summary.get("enabled"):
            return None
        pattern_count = int(summary.get("pattern_count") or 0)
        discovered = int(summary.get("discovered_count") or 0)
        screened = int(summary.get("screened_count") or 0)
        frozen_supported = int(summary.get("frozen_supported_count") or 0)
        forward_pending = int(summary.get("forward_pending_count") or 0)
        features = int(summary.get("feature_count") or 0)
        strategies = int(summary.get("strategy_count") or 0)
        reason = {
            "reason_code": "pattern_discovery_sequence",
            "pattern_summary": summary,
            "forward_gate": wait_reason,
            "production_impact": "none",
        }
        if pattern_count == 0:
            return (
                ResearchAction.DISCOVER_PATTERNS,
                QueueStatus.PROPOSAL,
                "no pending pattern exists; discover bounded historical patterns",
                {**reason, "next_stage": "discover_patterns"},
                0.7,
            )
        if discovered > 0:
            return (
                ResearchAction.SCREEN_PATTERNS,
                QueueStatus.PLANNING,
                "discovered patterns need significance and novelty screening",
                {**reason, "next_stage": "screen_patterns"},
                0.74,
            )
        if screened > 0 and features == 0:
            return (
                ResearchAction.SYNTHESIZE_FEATURES,
                QueueStatus.PLANNING,
                "screened patterns need declarative feature synthesis",
                {**reason, "next_stage": "synthesize_features"},
                0.72,
            )
        if features > 0 and strategies == 0:
            return (
                ResearchAction.SYNTHESIZE_STRATEGIES,
                QueueStatus.PLANNING,
                "synthesized features need allow-listed strategy synthesis",
                {**reason, "next_stage": "synthesize_strategies"},
                0.71,
            )
        if strategies > 0:
            return (
                ResearchAction.SUBMIT_PATTERN_HYPOTHESIS,
                QueueStatus.PROPOSAL,
                "valid pattern strategy exists; submit a Research Proposal Request",
                {**reason, "next_stage": "submit_pattern_hypothesis"},
                0.76,
            )
        if frozen_supported > 0 and forward_pending > 0:
            return (
                ResearchAction.WAIT_FORWARD_PATTERN,
                QueueStatus.WAITING_FORWARD,
                "pattern evidence is waiting for forward coverage",
                {**reason, "next_stage": "wait_forward_pattern"},
                0.1,
            )
        return (
            ResearchAction.WAIT_FORWARD_PATTERN,
            QueueStatus.WAITING_FORWARD,
            "no valid pattern action is available; wait instead of creating speculative work",
            {**reason, "next_stage": "wait_forward_pattern", "reason_code": "no_valid_pattern_action"},
            0.05,
        )

    def _action_for_hypothesis(
        self,
        hypothesis: Any,
        state: SchedulerState,
    ) -> tuple[ResearchAction, QueueStatus, str, float]:
        status = self._field(hypothesis, "status")
        hypothesis_key = self._field(hypothesis, "hypothesis_key")
        experiments = [
            item for item in state.recent_experiments
            if self._field(item, "hypothesis_key") == hypothesis_key
        ]
        evidence = [
            item for item in state.recent_evidence
            if self._field(item, "hypothesis_key") == hypothesis_key
        ]
        if status == "accepted_for_followup":
            return (
                ResearchAction.CREATE_PLANNING_REQUEST,
                QueueStatus.PLANNING,
                "accepted hypothesis needs a follow-up planning request",
                0.92,
            )
        if status in {"preregistered", "proposed"} and experiments:
            return (
                ResearchAction.CREATE_ENGINEERING_REQUEST,
                QueueStatus.ENGINEERING,
                "preregistered hypothesis has a plan and needs an Engineering request",
                0.86,
            )
        if status == "running" and experiments and not evidence:
            return (
                ResearchAction.CREATE_REVIEW_REQUEST,
                QueueStatus.REVIEW,
                "running hypothesis has completed artifacts but lacks formal evidence review",
                0.88,
            )
        return (
            ResearchAction.CREATE_PLANNING_REQUEST,
            QueueStatus.PLANNING,
            "active hypothesis needs deterministic planning before further work",
            0.72,
        )

    @staticmethod
    def _best_active_hypothesis(active: list[Any]) -> Any | None:
        if not active:
            return None
        priority_by_status = {
            "accepted_for_followup": 4,
            "running": 3,
            "preregistered": 2,
            "proposed": 1,
            "inconclusive": 0,
        }
        return sorted(
            active,
            key=lambda item: (
                -priority_by_status.get(ResearchPriorityEngine._field(item, "status"), 0),
                ResearchPriorityEngine._field(item, "hypothesis_key"),
            ),
        )[0]

    @staticmethod
    def _field(value: Any, name: str) -> Any:
        if isinstance(value, dict):
            return value.get(name)
        return getattr(value, name, None)

    @staticmethod
    def _family_diversity(state: SchedulerState, hypothesis: Any) -> float:
        rejected = {ResearchPriorityEngine._field(item, "family_key") for item in state.rejected_families}
        family = ResearchPriorityEngine._field(hypothesis, "family_key")
        return 0.0 if family in rejected else 1.0

    def _action(
        self,
        state: SchedulerState,
        action: ResearchAction,
        status: QueueStatus,
        summary: str,
        reason: dict[str, Any],
        *,
        priority: float,
        target_hypothesis_key: str | None = None,
        target_family_key: str | None = None,
        target_experiment_key: str | None = None,
        existing_queue_key: str | None = None,
        existing_request_key: str | None = None,
    ) -> NextResearchAction:
        return NextResearchAction(
            action=action,
            queue_status=status,
            summary=summary,
            reason=reason,
            priority_score=round(float(priority), 6),
            context_fingerprint=state.context_fingerprint,
            budget=self.budget_manager.budget.snapshot(),
            policy={"schema_version": ROUND26_SCHEMA_VERSION, "priority_engine": "deterministic-v1"},
            target_hypothesis_key=target_hypothesis_key,
            target_family_key=target_family_key,
            target_experiment_key=target_experiment_key,
            existing_queue_key=existing_queue_key,
            existing_request_key=existing_request_key,
        )
