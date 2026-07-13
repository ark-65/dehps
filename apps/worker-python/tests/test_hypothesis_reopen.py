from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from dehps.research.errors import ReopenError
from dehps.research.models import Hypothesis
from dehps.research.service import ResearchHypothesisService
from dehps.research.status import HypothesisStatus, RejectionScope


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def rejected_hypothesis() -> Hypothesis:
    return Hypothesis(
        id=7,
        hypothesis_key="hypothesis-rejected",
        family_id=1,
        parent_hypothesis_id=None,
        title="Rejected hypothesis",
        statement="statement",
        mechanism="mechanism",
        null_hypothesis="null",
        minimal_non_null="minimal",
        invariants=["frozen"],
        baseline_definition={"baseline": "frozen"},
        metric_definition={"metric": "objective"},
        failure_condition={"condition": "no lift"},
        self_deception_risk=["seed"],
        status=HypothesisStatus.REJECTED,
        rejection_scope=RejectionScope.PARAMETER_REGION,
        rejection_reason="failed",
        reopen_condition="new feature family or causal state variable",
        created_at=NOW,
        updated_at=NOW,
        preregistered_at=NOW,
        started_at=NOW,
        resolved_at=NOW,
    )


class ReopenRepository:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def reopen_hypothesis(self, **kwargs):
        self.calls.append(kwargs)
        return replace(
            rejected_hypothesis(),
            id=8,
            hypothesis_key=kwargs["new_hypothesis_key"],
            parent_hypothesis_id=7,
            status=HypothesisStatus.PROPOSED,
            rejection_scope=RejectionScope.NONE,
            rejection_reason=None,
            resolved_at=None,
        )


def test_reopen_rejects_parameter_only_changes() -> None:
    repository = ReopenRepository()
    service = ResearchHypothesisService(repository)  # type: ignore[arg-type]

    with pytest.raises(ReopenError, match="new_data, feature_family"):
        service.reopen(
            "hypothesis-rejected",
            new_hypothesis_key="hypothesis-v2",
            reopen_reason="try another seed and more epochs",
            decided_by="human:test",
            changed_basis={"seed": 9, "epochs": 500},
        )

    assert repository.calls == []


def test_reopen_creates_a_new_child_version_without_mutating_rejection() -> None:
    repository = ReopenRepository()
    service = ResearchHypothesisService(repository)  # type: ignore[arg-type]

    reopened = service.reopen(
        "hypothesis-rejected",
        new_hypothesis_key="hypothesis-v2",
        reopen_reason="new causal state variable is now available",
        decided_by="human:test",
        changed_basis={"causal_variable": "draw-regime-state-v1"},
    )

    assert reopened.hypothesis_key == "hypothesis-v2"
    assert reopened.parent_hypothesis_id == 7
    assert reopened.status == HypothesisStatus.PROPOSED
    assert rejected_hypothesis().status == HypothesisStatus.REJECTED
    assert repository.calls[0]["hypothesis_key"] == "hypothesis-rejected"
