from dehps.research_scheduler.policy import WaitingPolicy


def test_wait_policy_blocks_when_forward_evidence_is_insufficient() -> None:
    decision = WaitingPolicy().evaluate(
        {
            "paired_issue_count": 0,
            "min_paired_issues": 20,
            "review_ready": False,
            "blockers": ["incomplete_forward_pairs"],
        }
    )

    assert decision.allowed is False
    assert decision.reason_code == "forward_evidence_insufficient"


def test_wait_policy_allows_when_forward_gate_is_ready() -> None:
    decision = WaitingPolicy().evaluate(
        {
            "paired_issue_count": 20,
            "min_paired_issues": 20,
            "review_ready": True,
            "blockers": [],
        }
    )

    assert decision.allowed is True
    assert decision.reason_code == "forward_ready"
