from __future__ import annotations

from dehps.contracts import canonical_digest

from .contracts import (
    BlindTestFeatureView,
    OuterFold,
    SyntheticDataset,
    TrainingDatasetView,
    TrainFeatureView,
)
from .errors import WalkForwardError


FEATURE_NAMES = (
    "previous_issue_hit",
    "expanding_frequency",
    "periods_since_seen",
    "red_number_unit",
)
FEATURE_CONTRACT = {
    "feature_view_id": "FV1_SYNTHETIC_HISTORY_STATE",
    "feature_names": list(FEATURE_NAMES),
    "availability": "strictly_before_target_issue",
    "previous_issue_hit": "target[t-1, red_number]",
    "expanding_frequency": "count_before_t/(t-1), zero when no history",
    "periods_since_seen": "issues since latest prior hit, t-1 when never seen",
    "red_number_unit": "red_number/33",
}
FEATURE_MANIFEST_DIGEST = canonical_digest(
    FEATURE_CONTRACT, domain="dehps.m4.walk-forward.feature-view.v1"
)


def _feature_rows(
    dataset: SyntheticDataset | TrainingDatasetView,
    issue_ids: tuple[int, ...],
    *,
    include_targets: bool,
) -> tuple[
    tuple[int, ...],
    tuple[tuple[float, ...], ...],
    tuple[int, ...],
    tuple[tuple[int, int], ...],
]:
    red_numbers: list[int] = []
    rows: list[tuple[float, ...]] = []
    targets: list[int] = []
    availability: list[tuple[int, int]] = []
    counts = [0] * 33
    last_seen = [0] * 33
    previous_target = [0] * 33
    next_requested = set(issue_ids)
    for issue_index in range(1, max(issue_ids) + 1):
        if issue_index in next_requested:
            available_through = issue_index - 1
            availability.append((issue_index, available_through))
            for offset, red_number in enumerate(range(1, 34)):
                red_numbers.append(red_number)
                history_count = issue_index - 1
                gap = (
                    history_count - last_seen[offset] + 1
                    if last_seen[offset] > 0
                    else history_count
                )
                rows.append(
                    (
                        float(previous_target[offset]),
                        counts[offset] / history_count if history_count else 0.0,
                        float(gap),
                        red_number / 33.0,
                    )
                )
                if include_targets:
                    targets.append(dataset.issue(issue_index).target_vector[offset])
        if not include_targets and issue_index == max(issue_ids):
            break
        issue_target = dataset.issue(issue_index).target_vector
        for offset, value in enumerate(issue_target):
            if value:
                counts[offset] += 1
                last_seen[offset] = issue_index
        previous_target = list(issue_target)
    return tuple(red_numbers), tuple(rows), tuple(targets), tuple(availability)


def build_train_feature_view(
    dataset: SyntheticDataset | TrainingDatasetView,
    issue_ids: tuple[int, ...],
) -> TrainFeatureView:
    if not issue_ids:
        raise WalkForwardError("insufficient_training_history", "train view is empty")
    if tuple(sorted(set(issue_ids))) != issue_ids:
        raise WalkForwardError(
            "non_chronological_feature_view", "train issues must be ordered and unique"
        )
    red_numbers, rows, targets, availability = _feature_rows(
        dataset, issue_ids, include_targets=True
    )
    if len(rows) != len(issue_ids) * 33:
        raise WalkForwardError(
            "invalid_number_event_rows", "train view requires 33 rows per issue"
        )
    for issue_id, available_through in availability:
        if available_through >= issue_id:
            raise WalkForwardError(
                "future_feature_leakage", "train feature timestamp reached its target"
            )
    view_identity = {
        "dataset_digest": dataset.artifact_digest,
        "issue_ids": list(issue_ids),
        "available_through_by_issue": [list(item) for item in availability],
        "construction_start_issue": 1,
        "construction_end_issue": issue_ids[-1] - 1,
        "feature_manifest_digest": FEATURE_MANIFEST_DIGEST,
        "feature_names": list(FEATURE_NAMES),
        "values": [list(row) for row in rows],
        "target_access": "outer_training_targets_only",
    }
    return TrainFeatureView(
        issue_ids=issue_ids,
        red_numbers=red_numbers,
        feature_names=FEATURE_NAMES,
        values=rows,
        targets=targets,
        available_through_by_issue=availability,
        construction_start_issue=1,
        construction_end_issue=issue_ids[-1] - 1,
        feature_manifest_digest=FEATURE_MANIFEST_DIGEST,
        feature_view_digest=canonical_digest(
            view_identity, domain="dehps.m4.walk-forward.train-feature-view.v1"
        ),
    )


def build_blind_test_feature_view(
    dataset: SyntheticDataset,
    *,
    target_issue: int,
) -> BlindTestFeatureView:
    red_numbers, rows, _hidden_targets, availability = _feature_rows(
        dataset, (target_issue,), include_targets=False
    )
    view_identity = {
        "dataset_digest": dataset.artifact_digest,
        "target_issue": target_issue,
        "available_through_issue": availability[0][1],
        "construction_start_issue": 1,
        "construction_end_issue": target_issue - 1,
        "feature_manifest_digest": FEATURE_MANIFEST_DIGEST,
        "feature_names": list(FEATURE_NAMES),
        "red_numbers": list(red_numbers),
        "values": [list(row) for row in rows],
        "target_access": "forbidden",
    }
    return BlindTestFeatureView(
        target_issue=target_issue,
        red_numbers=red_numbers,
        feature_names=FEATURE_NAMES,
        values=rows,
        available_through_issue=availability[0][1],
        construction_start_issue=1,
        construction_end_issue=target_issue - 1,
        feature_manifest_digest=FEATURE_MANIFEST_DIGEST,
        feature_view_digest=canonical_digest(
            view_identity, domain="dehps.m4.walk-forward.blind-feature-view.v1"
        ),
    )


def build_fold_views(
    dataset: SyntheticDataset,
    fold: OuterFold,
) -> tuple[TrainFeatureView, BlindTestFeatureView]:
    train = build_train_feature_view(dataset, fold.train_issues)
    blind = build_blind_test_feature_view(dataset, target_issue=fold.test_issue)
    if train.construction_end_issue > fold.train_issues[-1]:
        raise WalkForwardError(
            "global_statistics_leakage", "train features exceed outer training range"
        )
    if blind.available_through_issue != fold.train_issues[-1]:
        raise WalkForwardError(
            "future_feature_leakage", "blind view is not anchored to train_end"
        )
    return train, blind


def illegal_future_feature_canary(
    dataset: SyntheticDataset,
    *,
    target_issue: int,
) -> BlindTestFeatureView:
    legal = build_blind_test_feature_view(dataset, target_issue=target_issue)
    return BlindTestFeatureView(
        target_issue=target_issue,
        red_numbers=legal.red_numbers,
        feature_names=legal.feature_names + ("test_target_canary",),
        values=tuple(
            row + (float(value),)
            for row, value in zip(
                legal.values, dataset.issue(target_issue).target_vector, strict=True
            )
        ),
        available_through_issue=target_issue,
        construction_start_issue=legal.construction_start_issue,
        construction_end_issue=target_issue,
        feature_manifest_digest=canonical_digest(
            {"canary": "target_as_feature"},
            domain="dehps.m4.walk-forward.feature-canary.v1",
        ),
        feature_view_digest=canonical_digest(
            {"canary": "target_as_feature", "target_issue": target_issue},
            domain="dehps.m4.walk-forward.feature-canary-view.v1",
        ),
    )


def fold_feature_view_digest(
    train: TrainFeatureView,
    blind: BlindTestFeatureView,
) -> str:
    return canonical_digest(
        {
            "feature_manifest_digest": train.feature_manifest_digest,
            "train_feature_view_digest": train.feature_view_digest,
            "blind_feature_view_digest": blind.feature_view_digest,
            "train_end_issue": max(train.issue_ids),
            "test_issue": blind.target_issue,
        },
        domain="dehps.m4.walk-forward.fold-feature-view.v1",
    )
