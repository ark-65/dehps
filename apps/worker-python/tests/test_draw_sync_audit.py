from dehps.draw_sync.audit import DrawDatabaseAuditor


def test_draw_audit_accepts_legal_ordered_history() -> None:
    report = DrawDatabaseAuditor().audit(
        (
            ("2026079", (1, 2, 3, 4, 5, 6), 7),
            ("2026080", (3, 8, 12, 18, 25, 33), 16),
        )
    )

    assert report.passed is True
    assert report.latest_issue == "2026080"
    assert report.history_fingerprint


def test_draw_audit_rejects_illegal_or_unordered_history() -> None:
    report = DrawDatabaseAuditor().audit(
        (
            ("2026080", (1, 1, 3, 4, 5, 34), 17),
            ("2026079", (1, 2, 3), 1),
        )
    )

    assert report.passed is False
    assert report.invalid_red_length_count == 1
    assert report.red_out_of_range_count == 1
    assert report.duplicate_red_numbers_count == 1
    assert report.blue_out_of_range_count == 1
    assert report.issue_order_ok is False
