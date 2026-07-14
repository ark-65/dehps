from __future__ import annotations

from dehps.forward_state.models import ForwardReconcileDecision


class TrainingResumePolicy:
    def authorize(self, decision: ForwardReconcileDecision) -> tuple[bool, str]:
        if not decision.resume_allowed:
            return False, decision.reason_code
        if not decision.event_key:
            return False, "missing_event_key"
        if not decision.observed_issue:
            return False, "missing_observed_issue"
        return True, "resume_authorized"
