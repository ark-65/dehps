from __future__ import annotations

from typing import Any

from dehps.forward_state.reconciler import ForwardStateReconciler
from dehps.training_resume.launcher import SupervisorTrainingLauncher, TrainingLauncher
from dehps.training_resume.lock import training_resume_lock
from dehps.training_resume.policy import TrainingResumePolicy
from dehps.training_resume.repository import TrainingResumeRepository


class TrainingResumeController:
    def __init__(
        self,
        *,
        reconciler: ForwardStateReconciler | None = None,
        repository: TrainingResumeRepository | None = None,
        launcher: TrainingLauncher | None = None,
        policy: TrainingResumePolicy | None = None,
    ) -> None:
        self.reconciler = reconciler or ForwardStateReconciler()
        self.repository = repository or TrainingResumeRepository()
        self.launcher = launcher or SupervisorTrainingLauncher()
        self.policy = policy or TrainingResumePolicy()

    def check(self, *, event_key: str | None = None) -> dict[str, Any]:
        decision = self.reconciler.reconcile(event_key=event_key)
        allowed, reason = self.policy.authorize(decision)
        return {"dry_run": True, "allowed": allowed, "reason_code": reason, "decision": decision}

    def execute(self, *, event_key: str | None = None) -> dict[str, Any]:
        self.repository.ensure_schema()
        decision = self.reconciler.reconcile(event_key=event_key)
        allowed, reason = self.policy.authorize(decision)
        if not allowed:
            attempt_key = self.repository.record_attempt(
                event_key=decision.event_key,
                decision="wait",
                reason_code=reason,
                old_run_id=decision.old_run_id,
                new_run_id=None,
                result={"decision": decision},
            )
            return {"executed": False, "attempt_key": attempt_key, "reason_code": reason, "decision": decision}
        # A separate resume lock prevents two independent resume services from launching twice.
        with training_resume_lock(timeout_seconds=0, context={"resume_event_key": decision.event_key}):
            claimed = self.repository.claim_event(decision.event_key)
            if claimed is None:
                attempt_key = self.repository.record_attempt(
                    event_key=decision.event_key,
                    decision="wait",
                    reason_code="event_already_claimed_or_consumed",
                    old_run_id=decision.old_run_id,
                    new_run_id=None,
                    result={"decision": decision},
                )
                return {
                    "executed": False,
                    "attempt_key": attempt_key,
                    "reason_code": "event_already_claimed_or_consumed",
                    "decision": decision,
                }
            try:
                launch = self.launcher.launch(as_of_issue=decision.observed_issue)
            except Exception as exc:
                self.repository.mark_event_failed(
                    event_key=decision.event_key,
                    reason={"type": type(exc).__name__, "message": str(exc)},
                )
                attempt_key = self.repository.record_attempt(
                    event_key=decision.event_key,
                    decision="failed",
                    reason_code="launcher_failed",
                    old_run_id=decision.old_run_id,
                    new_run_id=None,
                    result={"error": {"type": type(exc).__name__, "message": str(exc)}, "decision": decision},
                )
                return {"executed": False, "attempt_key": attempt_key, "reason_code": "launcher_failed"}
            self.repository.mark_event_consumed(event_key=decision.event_key, run_id=launch.run_id)
            attempt_key = self.repository.record_attempt(
                event_key=decision.event_key,
                decision="launched",
                reason_code="launched",
                old_run_id=decision.old_run_id,
                new_run_id=launch.run_id,
                result={"launch": launch, "decision": decision},
            )
            return {
                "executed": True,
                "attempt_key": attempt_key,
                "reason_code": "launched",
                "new_run_id": launch.run_id,
                "launch": launch,
            }
