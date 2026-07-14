import pytest

from dehps.experiments.ranking_disagreement.windows import build_issue_windows, history_before_issue
from ranking_disagreement_fixtures import small_history


def test_windows_fail_closed_on_insufficient_history_and_do_not_overlap() -> None:
    with pytest.raises(ValueError, match="insufficient"):
        build_issue_windows(small_history(5), search_issue_count=3, frozen_issue_count=2, minimum_training_issues=3)

    windows = build_issue_windows(small_history(10), search_issue_count=3, frozen_issue_count=2, minimum_training_issues=3)

    assert not set(windows.search_issues) & set(windows.frozen_issues)
    assert len(history_before_issue(small_history(10), windows.search_issues[0])) >= 3
