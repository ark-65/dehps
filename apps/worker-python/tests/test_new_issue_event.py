from dehps.draw_sync.models import new_issue_event_key


def test_new_issue_event_key_is_deterministic_and_idempotent() -> None:
    kwargs = {
        "previous_issue": "2026079",
        "new_issue": "2026080",
        "history_fingerprint": "history-fp",
        "audit_report_hash": "audit-hash",
        "source": "zhcw",
    }

    assert new_issue_event_key(**kwargs) == new_issue_event_key(**kwargs)
    assert new_issue_event_key(**kwargs).startswith("draw-issue-2026080-")


def test_new_issue_event_key_changes_with_fingerprint() -> None:
    base = {
        "previous_issue": "2026079",
        "new_issue": "2026080",
        "audit_report_hash": "audit-hash",
        "source": "zhcw",
    }

    assert new_issue_event_key(**base, history_fingerprint="a") != new_issue_event_key(
        **base, history_fingerprint="b"
    )
