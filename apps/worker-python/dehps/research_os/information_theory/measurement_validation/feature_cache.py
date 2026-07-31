from __future__ import annotations

from collections import OrderedDict
from hashlib import sha256

import orjson

from dehps.research_os.information_theory.walk_forward.contracts import (
    BlindTestFeatureView,
    SyntheticDataset,
    TrainFeatureView,
    TrainingDatasetView,
)
from dehps.research_os.information_theory.walk_forward.errors import (
    WalkForwardError,
)
from dehps.research_os.information_theory.walk_forward.feature_view import (
    FEATURE_MANIFEST_DIGEST,
    FEATURE_NAMES,
)

_TRAIN_FEATURE_VIEW_DOMAIN = "dehps.m4.walk-forward.train-feature-view.v1"
_BLIND_FEATURE_VIEW_DOMAIN = "dehps.m4.walk-forward.blind-feature-view.v1"


def _exact_feature_digest(value: object, *, domain: str) -> str:
    """Serialize the internal ASCII primitive tree with canonical JSON bytes."""

    serialized = orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
    return sha256(domain.encode("ascii") + b"\x00" + serialized).hexdigest()


class StrictPriorFeatureCache:
    """Incremental, target-gated equivalent of the accepted P2.3 feature builder.

    The cache never reads a target through ``SyntheticDataset``. New rows enter
    the cache only through a ``TrainingDatasetView`` whose access boundary has
    already advanced past that issue. Blind rows are derived from accumulated
    prior state before the current target is exposed.
    """

    def __init__(self, dataset: SyntheticDataset) -> None:
        self._dataset_digest = dataset.artifact_digest
        self._issue_count = dataset.issue_count
        self._revealed_through = 0
        self._counts = [0] * 33
        self._last_seen = [0] * 33
        self._previous_target = [0] * 33
        self._rows: dict[int, tuple[tuple[float, ...], ...]] = {}
        self._targets: dict[int, tuple[int, ...]] = {}
        self._training_views: OrderedDict[
            tuple[int, ...],
            TrainFeatureView,
        ] = OrderedDict()

    @property
    def revealed_through_issue(self) -> int:
        return self._revealed_through

    def reveal_training_history(
        self,
        dataset: TrainingDatasetView,
        *,
        through_issue: int,
    ) -> None:
        if (
            dataset.artifact_digest != self._dataset_digest
            or through_issue > dataset.available_through_issue
            or through_issue >= self._issue_count
            or through_issue < self._revealed_through
        ):
            raise WalkForwardError(
                "target_access_boundary_violation",
                "feature cache may advance only through an authorized training view",
            )
        for issue_index in range(self._revealed_through + 1, through_issue + 1):
            history_count = issue_index - 1
            rows: list[tuple[float, ...]] = []
            for offset, red_number in enumerate(range(1, 34)):
                gap = (
                    history_count - self._last_seen[offset] + 1
                    if self._last_seen[offset] > 0
                    else history_count
                )
                rows.append(
                    (
                        float(self._previous_target[offset]),
                        (
                            self._counts[offset] / history_count
                            if history_count
                            else 0.0
                        ),
                        float(gap),
                        red_number / 33.0,
                    )
                )
            target = dataset.issue(issue_index).target_vector
            self._rows[issue_index] = tuple(rows)
            self._targets[issue_index] = target
            for offset, value in enumerate(target):
                if value:
                    self._counts[offset] += 1
                    self._last_seen[offset] = issue_index
            self._previous_target = list(target)
            self._revealed_through = issue_index

    def build_train_feature_view(
        self,
        dataset: TrainingDatasetView,
        issue_ids: tuple[int, ...],
    ) -> TrainFeatureView:
        if (
            not issue_ids
            or tuple(sorted(set(issue_ids))) != issue_ids
            or dataset.artifact_digest != self._dataset_digest
            or max(issue_ids) > self._revealed_through
            or max(issue_ids) > dataset.available_through_issue
        ):
            raise WalkForwardError(
                "target_access_boundary_violation",
                "cached train rows must be ordered and already revealed",
            )
        cached = self._training_views.get(issue_ids)
        if cached is not None:
            self._training_views.move_to_end(issue_ids)
            return cached
        red_numbers = tuple(
            red_number for _issue_id in issue_ids for red_number in range(1, 34)
        )
        rows = tuple(row for issue_id in issue_ids for row in self._rows[issue_id])
        targets = tuple(
            value for issue_id in issue_ids for value in self._targets[issue_id]
        )
        availability = tuple((issue_id, issue_id - 1) for issue_id in issue_ids)
        identity = {
            "dataset_digest": dataset.artifact_digest,
            "issue_ids": issue_ids,
            "available_through_by_issue": availability,
            "construction_start_issue": 1,
            "construction_end_issue": issue_ids[-1] - 1,
            "feature_manifest_digest": FEATURE_MANIFEST_DIGEST,
            "feature_names": FEATURE_NAMES,
            "values": rows,
            "target_access": "outer_training_targets_only",
        }
        view = TrainFeatureView(
            issue_ids=issue_ids,
            red_numbers=red_numbers,
            feature_names=FEATURE_NAMES,
            values=rows,
            targets=targets,
            available_through_by_issue=availability,
            construction_start_issue=1,
            construction_end_issue=issue_ids[-1] - 1,
            feature_manifest_digest=FEATURE_MANIFEST_DIGEST,
            feature_view_digest=_exact_feature_digest(
                identity,
                domain=_TRAIN_FEATURE_VIEW_DOMAIN,
            ),
        )
        self._training_views[issue_ids] = view
        self._training_views.move_to_end(issue_ids)
        while len(self._training_views) > 32:
            self._training_views.popitem(last=False)
        return view

    def build_blind_test_feature_view(
        self,
        *,
        target_issue: int,
    ) -> BlindTestFeatureView:
        if (
            target_issue != self._revealed_through + 1
            or target_issue > self._issue_count
        ):
            raise WalkForwardError(
                "target_access_boundary_violation",
                "blind feature cache must be exactly one issue ahead",
            )
        history_count = target_issue - 1
        rows: list[tuple[float, ...]] = []
        for offset, red_number in enumerate(range(1, 34)):
            gap = (
                history_count - self._last_seen[offset] + 1
                if self._last_seen[offset] > 0
                else history_count
            )
            rows.append(
                (
                    float(self._previous_target[offset]),
                    (self._counts[offset] / history_count if history_count else 0.0),
                    float(gap),
                    red_number / 33.0,
                )
            )
        values = tuple(rows)
        red_numbers = tuple(range(1, 34))
        identity = {
            "dataset_digest": self._dataset_digest,
            "target_issue": target_issue,
            "available_through_issue": history_count,
            "construction_start_issue": 1,
            "construction_end_issue": history_count,
            "feature_manifest_digest": FEATURE_MANIFEST_DIGEST,
            "feature_names": FEATURE_NAMES,
            "red_numbers": red_numbers,
            "values": values,
            "target_access": "forbidden",
        }
        return BlindTestFeatureView(
            target_issue=target_issue,
            red_numbers=red_numbers,
            feature_names=FEATURE_NAMES,
            values=values,
            available_through_issue=history_count,
            construction_start_issue=1,
            construction_end_issue=history_count,
            feature_manifest_digest=FEATURE_MANIFEST_DIGEST,
            feature_view_digest=_exact_feature_digest(
                identity,
                domain=_BLIND_FEATURE_VIEW_DOMAIN,
            ),
        )
