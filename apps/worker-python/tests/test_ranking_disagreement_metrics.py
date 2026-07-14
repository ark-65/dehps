import numpy as np
import pytest

from dehps.experiments.ranking_disagreement.metrics import evaluate_selection


def test_metrics_reject_duplicate_candidates_and_report_required_fields() -> None:
    rank_mean = np.arange(1, 11, dtype=float)
    metrics = evaluate_selection(
        selection_key="s",
        candidate_indices=np.asarray([0, 1, 2], dtype=np.int32),
        rank_mean=rank_mean,
        target_index=1,
        combination_count=10,
    )
    assert metrics["target_hit"] is True
    assert "mean_reciprocal_rank" in metrics
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_selection(
            selection_key="bad",
            candidate_indices=np.asarray([0, 0], dtype=np.int32),
            rank_mean=rank_mean,
            target_index=1,
            combination_count=10,
        )
