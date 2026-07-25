from __future__ import annotations

from math import fsum

from .contracts import InnerFold
from .errors import WalkForwardError
from .leakage import guard_inner_boundaries


def expanding_inner_folds(
    outer_train_issues: tuple[int, ...],
    *,
    fold_count: int = 3,
    outer_test_issue: int,
) -> tuple[InnerFold, ...]:
    if fold_count != 3:
        raise WalkForwardError(
            "inner_validation_contract_mismatch", "frozen contract requires three folds"
        )
    if tuple(sorted(set(outer_train_issues))) != outer_train_issues:
        raise WalkForwardError(
            "non_chronological_inner_validation", "outer training is not ordered"
        )
    count = len(outer_train_issues)
    initial = count // 4
    if initial < 1:
        raise WalkForwardError(
            "insufficient_training_history", "not enough history for inner folds"
        )
    remaining = count - initial
    base, extra = divmod(remaining, fold_count)
    folds: list[InnerFold] = []
    validation_start = initial
    for index in range(fold_count):
        block = base + (1 if index < extra else 0)
        validation_end = validation_start + block
        folds.append(
            InnerFold(
                train_issues=outer_train_issues[:validation_start],
                validation_issues=outer_train_issues[
                    validation_start:validation_end
                ],
            )
        )
        validation_start = validation_end
    result = tuple(folds)
    guard_inner_boundaries(
        result,
        outer_train_end=max(outer_train_issues),
        outer_test_issue=outer_test_issue,
    )
    return result


def reject_random_inner_validation(method: str) -> None:
    if method != "three_fold_expanding_blocked_time_series":
        raise WalkForwardError(
            "non_chronological_inner_validation",
            "random, stratified, shuffled, and K-fold validation are forbidden",
        )


def select_inner_candidate(
    candidate_scores: dict[str, tuple[float, ...]],
    *,
    complexity_order: dict[str, int],
) -> tuple[str, dict[str, float]]:
    if not candidate_scores:
        raise WalkForwardError(
            "missing_probe_hyperparameter_contract", "candidate scores are empty"
        )
    summaries = {
        candidate: fsum(scores) / len(scores)
        for candidate, scores in candidate_scores.items()
    }
    selected = min(
        summaries,
        key=lambda item: (
            summaries[item],
            complexity_order[item],
            item,
        ),
    )
    return selected, summaries
